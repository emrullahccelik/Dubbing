"""Adım 4: ses klonlama. Her segmentin çevirisi, orijinal konuşmacının sesiyle OmniVoice'ta seslendirilir.

1. Referanslar: her konuşmacının en uzun segmentleri ~10 sn olana kadar orijinal sesten kesilip aralarına kısa
   sessizlik konarak birleştirilir; transkripti ASR'dan gelir. Tek segment 14 sn'yi aşıyorsa kelime
   zaman damgalarından (mümkünse cümle sonunda) kesilir.
2. Seslendirme: her segment, orijinal süresi hedef verilerek üretilir (yerel testte EN → TR/DE/FR'de süre
   oranı medyan 1.02, segmentlerin %94–100'ü ±%15 içinde).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from dub.common import load_audio

REF_SR = 24000
REF_TARGET_SEC = 10.0   # konuşmacı referansının hedef uzunluğu
REF_MAX_SEC = 14.0      # referansın üst sınırı
REF_MIN_SEG_SEC = 1.5   # referansa alınacak segmentin en kısa süresi
REF_GAP_SEC = 0.25      # referansta segmentler arasına konan sessizlik


def _trim_by_words(seg: dict, words: list[dict], max_sec: float) -> dict:
    """Uzun bir segmenti başından itibaren max_sec'i aşmayan son kelimede (mümkünse cümle sonunda) keser."""
    inside = [w for w in words if w["start"] >= seg["start"] - 0.05 and w["end"] <= seg["end"] + 0.05]
    kept = [w for w in inside if w["end"] - seg["start"] <= max_sec] or inside[:1]
    for i in range(len(kept) - 1, 0, -1):
        if kept[i]["word"].rstrip()[-1:] in ".?!" and kept[i]["end"] - seg["start"] >= max_sec * 0.5:
            kept = kept[:i + 1]
            break
    return {**seg, "end": kept[-1]["end"], "text": " ".join(w["word"] for w in kept)}


def _pick_ref_segments(segs: list[dict], words: list[dict]) -> list[dict]:
    cands = sorted((s for s in segs if s["duration"] >= REF_MIN_SEG_SEC), key=lambda s: -s["duration"])
    cands = cands or sorted(segs, key=lambda s: -s["duration"])[:1]
    chosen, total = [], 0.0
    for s in cands:
        if s["duration"] > REF_MAX_SEC:
            if chosen:
                continue
            s = _trim_by_words(s, words, REF_MAX_SEC)
        dur = s["end"] - s["start"]
        if chosen and total + REF_GAP_SEC + dur > REF_MAX_SEC:
            continue
        chosen.append(s)
        total += dur + (REF_GAP_SEC if len(chosen) > 1 else 0)
        if total >= REF_TARGET_SEC:
            break
    return sorted(chosen, key=lambda s: s["start"])


def build_refs(source: Path, segments: list[dict], words: list[dict], out_dir: Path) -> dict:
    """Konuşmacı başına referans ses (out_dir/<konuşmacı>.wav) ve transkripti."""
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = load_audio(source, REF_SR)
    gap = np.zeros(int(REF_GAP_SEC * REF_SR), dtype=np.float32)
    refs = {}
    for spk in sorted({s["speaker"] for s in segments}):
        chosen = _pick_ref_segments([s for s in segments if s["speaker"] == spk], words)
        parts = []
        for i, s in enumerate(chosen):
            if i:
                parts.append(gap)
            parts.append(audio[int(s["start"] * REF_SR):int((s["end"] + 0.05) * REF_SR)])
        pcm = np.concatenate(parts)
        sf.write(out_dir / f"{spk}.wav", pcm, REF_SR)
        refs[spk] = {"wav": f"{out_dir.name}/{spk}.wav", "text": " ".join(s["text"] for s in chosen),
                     "duration": round(len(pcm) / REF_SR, 2), "segment_ids": [s["id"] for s in chosen]}
    return refs


class OmniVoiceTTS:
    """k2-fsa/OmniVoice (0.6B, fp16). 4 GB'lık kartta tepe ~2.3 GB VRAM."""

    hf_id = "k2-fsa/OmniVoice"

    def __init__(self, device: str = "cuda:0"):
        self.device = device
        self.model = None

    @property
    def sr(self) -> int:
        return self.model.sampling_rate

    def load(self) -> float:
        import torch
        from omnivoice import OmniVoice

        t0 = time.time()
        self.model = OmniVoice.from_pretrained(self.hf_id, device_map=self.device, dtype=torch.float16)
        return round(time.time() - t0, 1)

    def unload(self) -> None:
        import torch

        self.model = None
        torch.cuda.empty_cache()

    def synthesize(self, segments: list[dict], lang: str, refs: dict, job_dir: Path, out_dir: Path,
                   on_segment: Callable[[int, int, dict], None] | None = None) -> dict:
        """segments: [{"id", "speaker", "duration", "translation"}] → out_dir/seg_###.wav ve özet."""
        import torch

        loaded_here = self.model is None
        load_sec = self.load() if loaded_here else 0.0
        torch.cuda.reset_peak_memory_stats()
        out_dir.mkdir(parents=True, exist_ok=True)
        # Referans her çağrıda dosyadan verilir: create_voice_clone_prompt ile hazırlanan prompt bu kartta
        # segment başına ~20 kat yavaş üretti (1.6 sn'lik segment 99 sn'ye karşı 5 sn).
        voices = {spk: {"ref_audio": str(job_dir / r["wav"]), "ref_text": r["text"]} for spk, r in refs.items()}

        results = []
        for n, s in enumerate(segments, 1):
            t0 = time.time()
            row = {"id": s["id"], "speaker": s["speaker"], "start": s["start"], "target_sec": s["duration"]}
            try:
                wav = self.model.generate(text=s["translation"], language=lang, duration=s["duration"],
                                          **voices[s["speaker"]])[0]
                wav = np.asarray(wav, dtype=np.float32).squeeze()
                if not wav.size:
                    raise ValueError("boş çıktı")
                name = f"seg_{s['id']:03d}.wav"
                sf.write(out_dir / name, wav, self.sr)
                row.update(wav=f"{out_dir.name}/{name}", audio_sec=round(len(wav) / self.sr, 3),
                           duration_ratio=round(len(wav) / self.sr / s["duration"], 3))
            except Exception as e:  # tek segment hatası bütün işi durdurmasın
                row["error"] = f"{type(e).__name__}: {e}"
            row["gen_sec"] = round(time.time() - t0, 2)
            results.append(row)
            if on_segment:
                on_segment(n, len(segments), row)

        ok = [r for r in results if "wav" in r]
        run = {"model": self.hf_id, "sample_rate": self.sr, "language": lang, "load_sec": load_sec,
               "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
               "segments": len(results), "failed": len(results) - len(ok),
               "total_gen_sec": round(sum(r["gen_sec"] for r in results), 1),
               "total_audio_sec": round(sum(r["audio_sec"] for r in ok), 1), "results": results}
        run["rtf"] = round(run["total_gen_sec"] / max(run["total_audio_sec"], 1e-6), 3)
        if loaded_here:
            self.unload()
        return run
