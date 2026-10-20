"""Adım 1: konuşmadan metne. ElevenLabs Scribe (OpenRouter üzerinden), kelime zaman damgası ve konuşmacı ayrımıyla.

ElevenLabs konuşma dışı sesleri metnin içine özel işaretle yazıyor: [güler], [laughter], [upbeat music] gibi.
Bunlar kelime listesinden ve metinden ayıklanır, seslendirilecek metne girmez; zaman damgalarıyla birlikte
ayrı bir `events` listesinde saklanır.
"""
from __future__ import annotations

import base64
import re
import subprocess
import time
import wave
from pathlib import Path

import requests

from dub.common import FFMPEG, load_api_key

API_URL = "https://openrouter.ai/api/v1/audio/transcriptions"

# [güler], [laughter], [laughs], [music] gibi köşeli parantezli işaretler
EVENT_TAG = re.compile(r"\[[^\]]*\]")
# ElevenLabs dili ISO 639-3 ile döndürüyor (eng, tur); hattın geri kalanı iki harfli kodu kullanıyor
ISO3 = {"eng": "en", "tur": "tr", "deu": "de", "fra": "fr", "spa": "es", "ita": "it", "por": "pt", "rus": "ru",
        "ara": "ar", "jpn": "ja", "kor": "ko", "cmn": "zh", "zho": "zh", "nld": "nl", "pol": "pl", "hin": "hi"}


def strip_tags(text: str) -> str:
    """Metindeki [işaret]leri siler, boşlukları ve işaretin bıraktığı yalnız noktalamayı toparlar."""
    text = EVENT_TAG.sub(" ", text)
    text = re.sub(r"\s+([,.?!;:])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def words_to_segments(words: list[dict], max_gap: float, max_len: float) -> list[dict]:
    """Kelimeleri konuşmacı değişimi, uzun sessizlik veya (max_len aşılınca) cümle sonunda segmentlere böler."""
    segs: list[dict] = []
    cur: dict | None = None
    for w in words:
        new = (cur is None or w["speaker"] != cur["speaker"] or w["start"] - cur["end"] > max_gap
               or (cur["end"] - cur["start"] > max_len and cur["text"].rstrip()[-1:] in ".?!"))
        if new:
            cur = {"speaker": w["speaker"], "start": w["start"], "end": w["end"], "text": w["word"]}
            segs.append(cur)
        else:
            cur["end"] = w["end"]
            cur["text"] += " " + w["word"]
    for i, s in enumerate(segs, 1):
        s["id"] = i
        s["text"] = re.sub(r"\s+([,.?!;:])", r"\1", s["text"]).strip()
        s["duration"] = round(s["end"] - s["start"], 3)
    return [{k: s[k] for k in ("id", "speaker", "start", "end", "duration", "text")} for s in segs]


class ElevenLabsASR:
    """ElevenLabs Scribe ile döküm. transcribe() ortak şemada sonuç döndürür:

    {"model", "language", "duration_sec", "text", "speakers", "events", "words", "segments", "usage"}
    segments: [{"id", "speaker", "start", "end", "duration", "text"}]
    """

    def __init__(self, model: str = "elevenlabs/scribe-v2", diarize: bool = True,
                 max_gap: float = 0.8, max_len: float = 15.0, api_key: str | None = None,
                 timeout: int = 600, retries: int = 2):
        self.model = model
        self.diarize = diarize
        self.max_gap = max_gap      # bu kadar sessizlikte yeni segment başlar
        self.max_len = max_len      # bu süreyi aşan segment cümle sonunda bölünür
        self.api_key = api_key or load_api_key()
        self.timeout = timeout
        self.retries = retries

    def transcribe(self, wav: Path, language: str | None = None) -> dict:
        with wave.open(str(wav), "rb") as w:
            duration = w.getnframes() / w.getframerate()
        # FLAC kayıpsız ve WAV'ın yarısı boyutunda; uzun seslerde istek gövdesi sınırına takılmamak için
        flac = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(wav), "-f", "flac", "pipe:1"],
                              capture_output=True, check=True).stdout
        body = {"model": self.model, "input_audio": {"data": base64.b64encode(flac).decode(), "format": "flac"},
                "response_format": "verbose_json", "timestamp_granularities": ["word", "segment"],
                "provider": {"options": {"elevenlabs": {"diarize": self.diarize}}}}
        if language:
            body["language"] = language
        t0 = time.time()
        res = self._post(body)
        latency = time.time() - t0

        words, events = [], []
        for w in res.get("words") or []:
            item = {"word": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3),
                    "speaker": w.get("speaker_label") or f"speaker_{w.get('speaker', 0)}",
                    "confidence": w.get("confidence")}
            if w.get("type") == "audio_event" or EVENT_TAG.fullmatch(item["word"]):
                events.append({**item, "label": item.pop("word").strip("[]")})
                continue
            item["word"] = strip_tags(item["word"])
            if item["word"]:
                words.append(item)

        segments = words_to_segments(words, self.max_gap, self.max_len)
        return {
            "model": self.model,
            "language": language or ISO3.get(res.get("language"), res.get("language")),
            "duration_sec": round(duration, 3),
            "latency_sec": round(latency, 2),
            "usage": res.get("usage"),
            "raw_text": res.get("text", ""),
            "text": strip_tags(res.get("text", "")),
            "speakers": sorted({s["speaker"] for s in segments}),
            "events": events,
            "words": words,
            "segments": segments,
        }

    def _post(self, body: dict) -> dict:
        err = None
        for attempt in range(self.retries + 1):
            try:
                r = requests.post(API_URL, headers={"Authorization": f"Bearer {self.api_key}"}, json=body,
                                  timeout=self.timeout)
                if r.status_code == 200:
                    return r.json()
                err = f"HTTP {r.status_code}: {r.text[:500]}"
                if r.status_code not in (429, 500, 502, 503):
                    break
            except requests.RequestException as e:
                err = str(e)
            if attempt < self.retries:
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"ASR başarısız ({self.model}): {err}")
