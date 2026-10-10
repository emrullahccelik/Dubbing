"""OpenRouter üzerindeki kapalı kaynak STT modellerini aynı ses üzerinde çalıştırır ve çıktıları kaydeder.

Kullanım:
    .venv/bin/python -m stt.run_stt --input docs/test_en.mp4
    .venv/bin/python -m stt.run_stt --input docs/test_tr.mp4 --models elevenlabs fish

Çıktılar: outputs/stt/<girdi_adı>/<model_anahtarı>/
    raw_*.json        API'nin ham yanıtı (parça başına)
    transcript.json   ortak şema: text, words, segments, kullanım/maliyet/süre
    transcript.txt    okunabilir, konuşmacılı ve zaman damgalı döküm
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from stt.common import (ROOT, clean_text, encode_audio, extract_audio, fish_speaker_words, fmt_ts, load_api_key,
                        read_wav, split_on_silence, transcribe, words_to_segments)

VERBOSE = {"response_format": "verbose_json", "timestamp_granularities": ["word", "segment"]}


@dataclass
class ModelSpec:
    key: str
    model: str
    extra: dict = field(default_factory=dict)
    max_sec: float | None = None   # sağlayıcının tek istekte kabul ettiği azami süre
    speakers: str = "none"         # "words" | "fish_tags" | "none"
    audio_format: str = "wav"      # "wav" | "flac"
    note: str = ""


MODELS = [
    ModelSpec("elevenlabs", "elevenlabs/scribe-v2",
              {**VERBOSE, "provider": {"options": {"elevenlabs": {"diarize": True}}}},
              speakers="words", note="diarize=true passthrough; kelime başına speaker"),
    ModelSpec("openai", "openai/gpt-transcribe", {},
              note="verbose_json desteklenmiyor: zaman damgası ve konuşmacı yok"),
    ModelSpec("fish", "fish-audio/transcribe-1-pro", VERBOSE,
              speakers="fish_tags", note="konuşmacı metin içinde <|speaker:N|> etiketiyle"),
    ModelSpec("assemblyai", "assemblyai/universal-3-5-pro",
              {**VERBOSE, "provider": {"options": {"assemblyai": {"speaker_labels": True}}}},
              max_sec=110, note="Sync API 120 sn sınırı: sessizlikten bölünerek gönderilir"),
    ModelSpec("meta", "meta/muse-voice-transcribe-1.0", {},
              note="verbose_json desteklenmiyor: zaman damgası ve konuşmacı yok"),
    ModelSpec("meta_diar", "meta/muse-voice-transcribe-1.0",
              {"provider": {"options": {"meta": {"mode": "DIARIZATION"}}}},
              note="mode=DIARIZATION kabul ediliyor ama OpenRouter konuşmacı etiketlerini döndürmüyor"),
    # --- 2. tur ---
    ModelSpec("grok", "x-ai/grok-stt-1.0",
              {**VERBOSE, "provider": {"options": {"xai": {"diarize": True}}}},
              speakers="words", note="diarize=true passthrough (sağlayıcı anahtarı 'xai')"),
    ModelSpec("deepgram", "deepgram/nova-3",
              {**VERBOSE, "provider": {"options": {"deepgram": {"diarize": True}}}},
              speakers="words", audio_format="flac",
              note="diarize=true passthrough; WAV (4.9 MB) 'large audio' hatası veriyor, FLAC gönderiliyor"),
    ModelSpec("mai2", "microsoft/mai-transcribe-2",
              {**VERBOSE, "provider": {"options": {"azure": {"diarization": {"enabled": True}}}}},
              speakers="words", note="diarization={enabled:true} passthrough (Azure)"),
    ModelSpec("mai15", "microsoft/mai-transcribe-1.5", {},
              note="verbose_json desteklenmiyor: zaman damgası ve konuşmacı yok"),
    ModelSpec("nemotron", "nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b", VERBOSE,
              note="açık ağırlık; konuşmacı ayrımı yok"),
    ModelSpec("qwen17", "qwen/qwen3-asr-1.7b", VERBOSE, note="açık ağırlık; konuşmacı ayrımı yok"),
    ModelSpec("qwen06", "qwen/qwen3-asr-0.6b", VERBOSE, note="açık ağırlık; konuşmacı ayrımı yok"),
    ModelSpec("whisper_turbo", "openai/whisper-large-v3-turbo", VERBOSE, note="açık ağırlık; konuşmacı ayrımı yok"),
    ModelSpec("whisper_v3", "openai/whisper-large-v3", VERBOSE, note="açık ağırlık; konuşmacı ayrımı yok"),
]


def run_model(spec: ModelSpec, key: str, wav: Path, out_dir: Path, language: str | None) -> dict:
    samples, sr = read_wav(wav)
    duration = len(samples) / sr
    chunks = split_on_silence(samples, sr, spec.max_sec) if spec.max_sec else [(0.0, samples)]
    out_dir.mkdir(parents=True, exist_ok=True)

    texts, words, latency, cost, billed, errors, detected_lang = [], [], 0.0, 0.0, 0.0, [], None
    provider_segments: list[dict] = []  # kelime zaman damgası gelmezse yedek olarak kullanılır
    for i, (offset, chunk) in enumerate(chunks):
        extra = dict(spec.extra)
        if language:
            extra["language"] = language
        res = transcribe(key, encode_audio(chunk, sr, spec.audio_format), spec.model, extra, fmt=spec.audio_format)
        (out_dir / f"raw_{i:02d}.json").write_text(json.dumps(
            {"request": res.request, "offset": offset, "status": res.status, "latency": res.latency,
             "response": res.body}, ensure_ascii=False, indent=1))
        latency += res.latency
        if res.status != 200:
            errors.append(f"parça {i}: HTTP {res.status} {res.body.get('error')}")
            continue
        body = res.body
        usage = body.get("usage") or {}
        cost += float(usage.get("cost") or 0)
        billed += float(usage.get("seconds") or 0)
        detected_lang = detected_lang or body.get("language")
        text = body.get("text", "")
        chunk_words = body.get("words") or []
        if spec.speakers == "fish_tags" and chunk_words:
            chunk_words = fish_speaker_words(text, chunk_words)
        for w in chunk_words:
            w = dict(w, word=w["word"].strip())
            w["start"] = round(w["start"] + offset, 3)
            w["end"] = round(w["end"] + offset, 3)
            if spec.speakers == "none":
                w.pop("speaker", None)
                w.pop("speaker_label", None)
            elif w.get("speaker") is not None:
                if len(chunks) > 1:
                    # parçalar arasında konuşmacı kimlikleri eşleşmez
                    w["speaker"] = f"{i}:{w['speaker']}"
                # Sağlayıcı etiket vermediyse (ya da parça öneki eklendiyse) kimlikten üret
                w["speaker_label"] = (w.get("speaker_label") if len(chunks) == 1 and w.get("speaker_label")
                                      else f"speaker_{w['speaker']}")
            words.append(w)
        for s in body.get("segments") or []:
            provider_segments.append({"start": round(s["start"] + offset, 3), "end": round(s["end"] + offset, 3),
                                      "speaker": None, "speaker_label": None, "text": s.get("text", "").strip()})
        texts.append(text)

    raw_text = " ".join(texts).strip()
    # Sağlayıcı kelime zaman damgası vermediyse (yönlendirme sağlayıcıya göre değişiyor) kendi segmentlerini kullan
    segments = words_to_segments(words) if words else provider_segments
    speakers = sorted({str(s["speaker"]) for s in segments if s.get("speaker") is not None})
    speaker_labels = sorted({s["speaker_label"] for s in segments if s.get("speaker_label")})
    turns_per_speaker = {s: sum(1 for x in segments if str(x.get("speaker")) == s) for s in speakers}
    result = {
        "key": spec.key, "model": spec.model, "note": spec.note,
        "audio_seconds": round(duration, 2), "chunks": len(chunks),
        "latency_sec": round(latency, 2), "rtf": round(latency / duration, 3),
        "billed_seconds": billed, "cost_usd": round(cost, 6),
        "cost_per_hour_usd": round(cost / duration * 3600, 3) if duration else None,
        "language": detected_lang,
        "has_word_timestamps": bool(words),
        "segment_source": "words" if words else ("provider" if segments else "none"),
        "has_speakers": bool(speakers),
        "speakers": speakers, "speaker_labels": speaker_labels,
        "speaker_turns": len(segments) if speakers else 0,
        "turns_per_speaker": turns_per_speaker,
        "errors": errors,
        "raw_text": raw_text, "text": clean_text(raw_text),
        "words": words, "segments": segments,
    }
    (out_dir / "transcript.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    (out_dir / "transcript.txt").write_text(render_txt(result))
    return result


def render_txt(r: dict) -> str:
    lines = [f"# {r['model']}  ({r['note']})",
             f"# süre={r['audio_seconds']}s gecikme={r['latency_sec']}s maliyet=${r['cost_usd']} "
             f"konuşmacılar={r.get('speaker_labels') or r['speakers'] or '-'}"
             + (f" turlar={r['turns_per_speaker']}" if r.get("turns_per_speaker") else ""), ""]
    if r["segments"]:
        width = max((len(s.get("speaker_label") or "") for s in r["segments"]), default=0)
        for s in r["segments"]:
            spk = f"[{(s.get('speaker_label') or ''):<{width}}] " if width else ""
            lines.append(f"{fmt_ts(s['start'])} - {fmt_ts(s['end'])} {spk}{s['text']}")
    else:
        lines.append(r["text"])
    if r["errors"]:
        lines += ["", "HATALAR:", *r["errors"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="docs/test_en.mp4")
    ap.add_argument("--models", nargs="*", default=[m.key for m in MODELS])
    ap.add_argument("--language", default=None, help="ISO-639-1; boş bırakılırsa otomatik algılanır")
    args = ap.parse_args()

    src = (ROOT / args.input).resolve()
    name = src.stem
    wav = src if src.suffix == ".wav" else extract_audio(src, ROOT / "outputs" / "audio" / f"{name}_16k.wav")
    base = ROOT / "outputs" / "stt" / name
    key = load_api_key()

    summary = []
    for spec in MODELS:
        if spec.key not in args.models:
            continue
        print(f"→ {spec.model} ...", flush=True)
        r = run_model(spec, key, wav, base / spec.key, args.language)
        print(f"  {r['latency_sec']}s, ${r['cost_usd']}, kelime_zd={r['has_word_timestamps']}, "
              f"konuşmacı={r['speakers']}, hata={r['errors'] or '-'}", flush=True)
        summary.append({k: v for k, v in r.items() if k not in ("words", "segments", "raw_text")})

    # Önceki koşulardan kalan özetleri koru, bu koşudakileri güncelle.
    summary_path = base / "summary.json"
    old = json.loads(summary_path.read_text()) if summary_path.exists() else []
    merged = {s["key"]: s for s in old}
    merged.update({s["key"]: s for s in summary})
    summary_path.write_text(json.dumps(list(merged.values()), ensure_ascii=False, indent=1))
    print(f"Özet: {summary_path}")


if __name__ == "__main__":
    main()
