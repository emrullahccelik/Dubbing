"""Adım 5: arka plan sesi. Orijinal ses Demucs (htdemucs_ft, MIT) ile konuşma ve geri kalan olarak ayrılır.

Gülüşme, alkış gibi insan kaynaklı sesler çoğunlukla konuşma kanalına düşüyor. Bu yüzden dublajın altına
konacak arka plan (bed.wav) şöyle kurulur: konuşma dışı kanal + konuşma kanalının segmentler DIŞINDA kalan
kısmı. Segment içinde konuşma kanalı sessize alınır (kenarlarda kısa geçişle), çünkü orada orijinal
konuşmacının sesi var.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import soundfile as sf

from dub.common import load_audio

SR = 44100
PAD_SEC = 0.10   # segment sınırlarının etrafında da konuşmayı sustur (zaman damgası kayması için)
FADE_SEC = 0.08  # susturma kenarlarındaki geçiş süresi


def speech_mask(segments: list[dict], n: int) -> np.ndarray:
    """Segment içinde 0, dışında 1 olan, kenarları yumuşatılmış kazanç eğrisi."""
    mask = np.ones(n, dtype=np.float32)
    for s in segments:
        mask[max(0, int((s["start"] - PAD_SEC) * SR)):min(n, int((s["end"] + PAD_SEC) * SR))] = 0.0
    k = int(FADE_SEC * SR)
    return np.convolve(mask, np.ones(k, dtype=np.float32) / k, mode="same")


class DemucsSeparator:
    model_name = "htdemucs_ft"

    def __init__(self, device: str = "cuda"):
        self.device = device

    def separate(self, source: Path, segments: list[dict], out_dir: Path) -> dict:
        import torch
        from demucs.apply import apply_model
        from demucs.pretrained import get_model

        t0 = time.time()
        out_dir.mkdir(parents=True, exist_ok=True)
        wav = load_audio(source, SR, channels=2)
        model = get_model(self.model_name)
        x = torch.from_numpy(wav)
        ref = x.mean(0)
        x = (x - ref.mean()) / (ref.std() + 1e-8)
        with torch.no_grad():
            est = apply_model(model, x[None], device=self.device, split=True, overlap=0.25, progress=False)[0]
        est = est * (ref.std() + 1e-8) + ref.mean()
        speech = est[model.sources.index("vocals")].numpy()
        background = wav - speech
        bed = background + speech * speech_mask(segments, wav.shape[1])
        del model, est
        torch.cuda.empty_cache()

        files = {}
        for name, audio in (("speech", speech), ("background", background), ("bed", bed)):
            sf.write(out_dir / f"{name}.wav", audio.T, SR)
            files[name] = f"{out_dir.name}/{name}.wav"
        return {"model": f"demucs/{self.model_name}", "sample_rate": SR, "files": files,
                "seconds": round(time.time() - t0, 1)}
