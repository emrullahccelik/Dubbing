"""OpenRouter STT testleri için ortak yardımcılar: anahtar, ses hazırlama, API çağrısı, normalizasyon."""
from __future__ import annotations

import base64
import os
import re
import subprocess
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def load_api_key() -> str:
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    env = ROOT / ".env"
    if not env.exists():
        raise RuntimeError(".env bulunamadı. Örnek dosyadan kopyala: cp .env.example .env")
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "OPENROUTER_API_KEY":
            return value.strip().strip("\"'")
    raise RuntimeError(".env içinde OPENROUTER_API_KEY satırı yok (bkz. .env.example)")


# --- Ses ---------------------------------------------------------------------

def extract_audio(video: Path, out_wav: Path, sr: int = 16000) -> Path:
    """Videodan mono 16 kHz WAV çıkarır (zaten varsa yeniden üretmez)."""
    if out_wav.exists() and out_wav.stat().st_mtime >= video.stat().st_mtime:
        return out_wav
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video),
                    "-vn", "-ac", "1", "-ar", str(sr), str(out_wav)], check=True)
    return out_wav


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data, sr


def wav_bytes(samples: np.ndarray, sr: int) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(samples.astype(np.int16).tobytes())
    return buf.getvalue()


def encode_audio(samples: np.ndarray, sr: int, fmt: str = "wav") -> bytes:
    """Örnekleri istenen formatta kodlar. FLAC kayıpsızdır ve WAV'ın ~yarısı boyutundadır
    (bazı sağlayıcılar büyük istek gövdelerini reddediyor)."""
    data = wav_bytes(samples, sr)
    if fmt == "wav":
        return data
    return subprocess.run([FFMPEG, "-loglevel", "error", "-f", "wav", "-i", "pipe:0", "-f", fmt, "pipe:1"],
                          input=data, capture_output=True, check=True).stdout


def split_on_silence(samples: np.ndarray, sr: int, max_sec: float) -> list[tuple[float, np.ndarray]]:
    """Sesi max_sec'i aşmayan parçalara böler; kesimi hedef noktaya yakın en sessiz 200 ms'e koyar.

    Döner: [(başlangıç_saniyesi, parça_örnekleri), ...]
    """
    total = len(samples) / sr
    if total <= max_sec:
        return [(0.0, samples)]
    n_chunks = int(np.ceil(total / max_sec))
    target = total / n_chunks
    win = int(0.2 * sr)
    cuts = [0]
    for k in range(1, n_chunks):
        ideal = int(k * target * sr)
        lo = max(cuts[-1] + win, ideal - int(8 * sr))
        hi = min(len(samples) - win, ideal + int(8 * sr), cuts[-1] + int(max_sec * sr) - win)
        best, best_e = ideal, None
        for start in range(lo, hi, win // 2):
            e = float(np.mean(samples[start:start + win].astype(np.float64) ** 2))
            if best_e is None or e < best_e:
                best, best_e = start + win // 2, e
        cuts.append(best)
    cuts.append(len(samples))
    return [(cuts[i] / sr, samples[cuts[i]:cuts[i + 1]]) for i in range(len(cuts) - 1)]


# --- API ---------------------------------------------------------------------

@dataclass
class CallResult:
    status: int
    body: dict
    latency: float
    request: dict = field(default_factory=dict)


def transcribe(key: str, audio: bytes, model: str, extra: dict | None = None,
               timeout: int = 300, retries: int = 2, fmt: str = "wav") -> CallResult:
    body = {"model": model, "input_audio": {"data": base64.b64encode(audio).decode(), "format": fmt}}
    body.update(extra or {})
    logged = {**{k: v for k, v in body.items() if k != "input_audio"}, "audio_format": fmt}
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            r = requests.post(API_URL, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=timeout)
            dt = time.time() - t0
            try:
                j = r.json()
            except ValueError:
                j = {"error": {"message": r.text[:1000], "code": r.status_code}}
        except requests.RequestException as e:
            dt, r, j = time.time() - t0, None, {"error": {"message": str(e), "code": "network"}}
        status = r.status_code if r is not None else 0
        if status in (429, 502, 503, 0) and attempt < retries:
            time.sleep(3 * (attempt + 1))
            continue
        return CallResult(status, j, dt, logged)
    raise AssertionError("unreachable")


# --- Normalizasyon -----------------------------------------------------------

FISH_SPEAKER = re.compile(r"<\|speaker:(\d+)\|>")
CUE = re.compile(r"\[[^\]]*\]")  # [emphasis], [laughter] gibi işaretler


def clean_text(text: str) -> str:
    """Konuşmacı etiketlerini ve [işaret]leri temizler."""
    text = FISH_SPEAKER.sub(" ", text)
    text = CUE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _norm_tok(t: str) -> str:
    return re.sub(r"[^\w']", "", t.lower())


def fish_speaker_words(text: str, words: list[dict]) -> list[dict]:
    """Fish Audio konuşmacıyı sadece metindeki <|speaker:N|> etiketiyle verir.
    Etiketli metni kelime listesine hizalayıp her kelimeye speaker atar."""
    import difflib
    tagged: list[tuple[str, str, int | None]] = []  # (normalize, orijinal_token, speaker)
    speaker = None
    for part in re.split(r"(<\|speaker:\d+\|>)", text):
        m = FISH_SPEAKER.fullmatch(part)
        if m:
            speaker = int(m.group(1))
            continue
        for tok in CUE.sub(" ", part).split():
            tagged.append((_norm_tok(tok), tok, speaker))
    a = [t for t, _, _ in tagged]
    b = [_norm_tok(w["word"]) for w in words]
    out = [dict(w) for w in words]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for blk in sm.get_matching_blocks():
        for i in range(blk.size):
            _, orig, spk = tagged[blk.a + i]
            out[blk.b + i]["speaker"] = spk
            out[blk.b + i]["word"] = orig  # kelime listesinde noktalama yok; metindeki hâlini kullan
    # Eşleşmeyen kelimeler önceki kelimenin konuşmacısını devralır.
    last = None
    for w in out:
        if w.get("speaker") is None:
            w["speaker"] = last
        last = w["speaker"]
    return out


def words_to_segments(words: list[dict], max_gap: float = 0.8, max_len: float = 15.0) -> list[dict]:
    """Kelimeleri konuşmacı değişimi, uzun sessizlik veya cümle sonunda (max_len aşılınca) segmentlere böler."""
    segs: list[dict] = []
    cur: dict | None = None
    for w in words:
        spk = w.get("speaker")
        new = (cur is None or spk != cur["speaker"] or w["start"] - cur["end"] > max_gap
               or (cur["end"] - cur["start"] > max_len and cur["text"].rstrip()[-1:] in ".?!"))
        if new:
            cur = {"start": w["start"], "end": w["end"], "speaker": spk,
                   "speaker_label": w.get("speaker_label") or (None if spk is None else f"speaker_{spk}"),
                   "text": w["word"]}
            segs.append(cur)
        else:
            cur["end"] = w["end"]
            cur["text"] += " " + w["word"]
    for s in segs:
        s["text"] = re.sub(r"\s+([,.?!;:])", r"\1", s["text"]).strip()
        s["start"], s["end"] = round(s["start"], 3), round(s["end"], 3)
    return segs


def fmt_ts(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:06.3f}"
