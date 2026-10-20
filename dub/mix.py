"""Adım 6: miks. Seslendirilen segmentler zaman çizelgesine yerleştirilir, arka planla karıştırılır ve
(girdi videoysa) görüntüyle birleştirilir.

Her segmentin kullanabileceği pencere: kendi başlangıcından sonraki segmentin başlangıcına kadar
(orijinal süre + arkasındaki sessizlik; son segmentte kaydın sonuna kadar). Üretilen ses pencereye
sığıyorsa olduğu gibi konur (kısaysa yavaşlatılmaz). Sığmıyorsa tonu korunarak (ffmpeg atempo)
pencereye sığacak kadar hızlandırılır.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from dub.common import atempo, encode_audio_file, load_audio, mux_video

SR = 44100
MARGIN_SEC = 0.05  # sonraki segmentle arasında bırakılan en az boşluk


def _resample(wav: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return wav
    import torch
    import torchaudio

    return torchaudio.functional.resample(torch.from_numpy(wav), src, dst).numpy()


def mix(tts: dict, job_dir: Path, duration: float, bed: Path | None, source: Path, is_video: bool,
        out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    segs = sorted((r for r in tts["results"] if "wav" in r), key=lambda r: r["start"])
    voice = np.zeros(int((duration + 1) * SR), dtype=np.float32)
    rows = []
    for i, r in enumerate(segs):
        nxt = segs[i + 1]["start"] if i + 1 < len(segs) else duration
        window = max(nxt - r["start"] - MARGIN_SEC, r["target_sec"])
        wav, sr = sf.read(job_dir / r["wav"], dtype="float32")
        sec = len(wav) / sr
        factor = sec / window if sec > window else 1.0
        if factor > 1.0:
            wav = atempo(wav, sr, factor, out_dir)
        wav = _resample(wav, sr, SR)
        a = int(r["start"] * SR)
        voice[a:a + len(wav)] += wav[:max(0, len(voice) - a)]
        rows.append({"id": r["id"], "start": r["start"], "orig_sec": r["target_sec"], "window_sec": round(window, 2),
                     "gen_sec": round(sec, 2), "speedup": round(factor, 3)})

    voice = voice[:int(duration * SR)]
    out = np.stack([voice, voice])
    if bed is not None and bed.exists():
        b = load_audio(bed, SR, channels=2)[:, :out.shape[1]]
        out[:, :b.shape[1]] += b
    peak = float(np.abs(out).max()) if out.size else 0.0
    if peak > 1.0:  # kırpılmayı önlemek için bütün miks orantılı kısılır
        out /= peak
    sf.write(out_dir / "dub.wav", out.T, SR)
    files = {"wav": f"{out_dir.name}/dub.wav"}
    if is_video:
        mux_video(source, out_dir / "dub.wav", out_dir / "dub.mp4")
        files["video"] = f"{out_dir.name}/dub.mp4"
    else:
        encode_audio_file(out_dir / "dub.wav", out_dir / "dub.m4a")
        files["audio"] = f"{out_dir.name}/dub.m4a"
    sped = [r["speedup"] for r in rows if r["speedup"] > 1]
    return {"sample_rate": SR, "background": bed is not None and bed.exists(), "files": files,
            "segments": len(rows), "sped_up": len(sped), "max_speedup": max(sped, default=1.0),
            "normalized_peak": round(peak, 3) if peak > 1.0 else None, "fit": rows}
