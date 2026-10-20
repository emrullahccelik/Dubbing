"""Hattın ortak yardımcıları: yollar, API anahtarı, ffmpeg ile ses okuma/yazma ve video birleştirme."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"          # hattın ve web arayüzünün çıktıları
OUT = DATA / "pipeline"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def load_api_key(name: str = "OPENROUTER_API_KEY") -> str:
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == name and value:
                return value.strip().strip("\"'")
    raise RuntimeError(f"{name} bulunamadı: ortam değişkeni olarak ya da .env dosyasında tanımlayın")


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def load_json(path: Path):
    return json.loads(path.read_text())


def rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# --- ffmpeg ------------------------------------------------------------------

def ffmpeg(*args: str) -> None:
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", *args], check=True)


def has_video(path: Path) -> bool:
    """Dosyada görüntü akışı var mı (kapak resmi sayılmaz)."""
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    return any("Video:" in ln and "attached pic" not in ln for ln in err.splitlines())


def media_duration(path: Path) -> float:
    err = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if not m:
        raise ValueError(f"Süre okunamadı: {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def load_audio(path: Path, sr: int, channels: int = 1) -> np.ndarray:
    """Herhangi bir ses/video dosyasından float32 ses. Mono: (T,), çok kanal: (C, T)."""
    raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(path), "-vn", "-ac", str(channels),
                          "-ar", str(sr), "-f", "f32le", "pipe:1"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    return audio.copy() if channels == 1 else audio.reshape(-1, channels).T.copy()


def extract_wav(src: Path, out: Path, sr: int = 16000) -> Path:
    """Mono 16-bit WAV çıkarır (zaten güncelse yeniden üretmez)."""
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    ffmpeg("-i", str(src), "-vn", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", str(out))
    return out


def atempo(wav: np.ndarray, sr: int, factor: float, tmp_dir: Path) -> np.ndarray:
    """Tonu değiştirmeden factor kat hızlandırır (mono). atempo tek adımda en fazla 2.0 kabul ediyor."""
    import soundfile as sf

    steps = []
    while factor > 2.0:
        steps.append(2.0)
        factor /= 2.0
    steps.append(factor)
    src, dst = tmp_dir / "atempo_in.wav", tmp_dir / "atempo_out.wav"
    sf.write(src, wav, sr)
    ffmpeg("-i", str(src), "-filter:a", ",".join(f"atempo={s:.5f}" for s in steps), str(dst))
    out, _ = sf.read(dst, dtype="float32")
    src.unlink()
    dst.unlink()
    return out


def mux_video(video: Path, audio: Path, out: Path) -> None:
    """Videonun görüntüsünü yeni sesle birleştirir; görüntü yeniden kodlanmaz."""
    ffmpeg("-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(out))


def encode_audio_file(audio: Path, out: Path) -> None:
    """Paylaşmak için sıkıştırılmış ses (AAC, .m4a)."""
    ffmpeg("-i", str(audio), "-c:a", "aac", "-b:a", "192k", str(out))
