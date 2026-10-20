"""Dublaj hattı: video/ses → ASR → çeviri → ses klonlama → arka plan → miks. Her adımın çıktısı JSON olarak
kaydedilir.

Kullanım (~/.venvs/dub ortamında, kurulum: requirements.txt):
    ~/.venvs/dub/bin/python -m dub.pipeline --input work/docs/test_en.mp4 --target tr
    ~/.venvs/dub/bin/python -m dub.pipeline --input work/docs/test_tr.mp4 --source tr --target en --llm google/gemini-3.8-flash
    ~/.venvs/dub/bin/python -m dub.pipeline --input work/docs/test_en.mp4 --target tr --redo tts   # klonlamadan itibaren

Çıktı: data/pipeline/<iş>/   (iş = <dosya_adı>_<hedef_dil>, ör. test_en_tr)
    audio.wav            mono 16 kHz ses (ASR girdisi)
    01_asr.json          döküm: segmentler, kelimeler, konuşma dışı sesler (events)
    02_analysis.json     LLM analizi: konu, üslup, konuşmacılar, sözlük
    03_translation.json  çevrilmiş segmentler (+ sözlük, LLM kullanımı)
    04_tts.json          konuşmacı referansları (refs/) ve segment başına üretilen ses (tts/)
    05_separation.json   orijinal sesin ayrıştırılması (separation/): konuşma, arka plan, bed
    06_mix.json          segment yerleşimi ve hızlandırma; final/dub.mp4 (video) ya da final/dub.m4a (ses), dub.wav

Bir adımın dosyası varsa yeniden çalıştırılmaz, okunur. --redo <adım> o adımı ve sonrakileri baştan çalıştırır.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from dub.asr import ElevenLabsASR
from dub.common import OUT, ROOT, extract_wav, has_video, load_json, rel, save_json
from dub.mix import mix
from dub.separate import DemucsSeparator
from dub.translate import LLMTranslator
from dub.tts import OmniVoiceTTS, build_refs

# (anahtar, dosya, arayüzde gösterilen ad, toplam ilerlemedeki ağırlık)
STEPS = [
    ("asr", "01_asr.json", "Konuşma metne çevriliyor", 8),
    ("analysis", "02_analysis.json", "İçerik analiz ediliyor", 5),
    ("translation", "03_translation.json", "Çeviri yapılıyor", 12),
    ("tts", "04_tts.json", "Ses klonlanıyor", 50),
    ("separation", "05_separation.json", "Arka plan sesi ayrıştırılıyor", 17),
    ("mix", "06_mix.json", "Miks ve video hazırlanıyor", 8),
]
STEP_KEYS = [s[0] for s in STEPS]

# progress(adım, adım_içi_oran 0–1, toplam_oran 0–1, mesaj)
Progress = Callable[[str, float, float, str], None]


class Pipeline:
    def __init__(self, asr: ElevenLabsASR, translator: LLMTranslator, tts: OmniVoiceTTS,
                 separator: DemucsSeparator | None = None):
        self.asr = asr
        self.translator = translator
        self.tts = tts
        self.separator = separator  # None ise arka plan eklenmez

    def run(self, source: Path, target: str, source_lang: str | None, out: Path,
            redo: str | None = None, progress: Progress | None = None) -> dict:
        source = source.resolve()
        out.mkdir(parents=True, exist_ok=True)
        redo_from = STEP_KEYS.index(redo) if redo else len(STEPS)
        total_w = sum(s[3] for s in STEPS)

        def report(key: str, frac: float, msg: str = "") -> None:
            i = STEP_KEYS.index(key)
            done_w = sum(s[3] for s in STEPS[:i])
            overall = (done_w + STEPS[i][3] * min(max(frac, 0.0), 1.0)) / total_w
            if progress:
                progress(key, frac, overall, msg or STEPS[i][2])

        def step(key: str, fn: Callable[[Callable[..., None]], dict]) -> dict:
            i = STEP_KEYS.index(key)
            path = out / STEPS[i][1]
            if path.exists() and i < redo_from:
                report(key, 1.0, f"{STEPS[i][2]}: kayıtlı sonuç kullanıldı")
                return load_json(path)
            report(key, 0.0)
            data = fn(lambda frac, msg="": report(key, frac, msg))
            save_json(path, data)
            report(key, 1.0, f"{STEPS[i][2]}: tamamlandı")
            return data

        audio = extract_wav(source, out / "audio.wav")
        asr = step("asr", lambda p: self.asr.transcribe(audio, source_lang))
        src = source_lang or asr["language"]
        if src == target:
            raise ValueError(f"Kaynak ve hedef dil aynı: {src}")
        if not asr["segments"]:
            raise ValueError("Kayıtta konuşma bulunamadı")
        segments = asr["segments"]

        def analyze(p) -> dict:
            self.translator.llm.reset_usage()
            res = self.translator.analyze(segments, src, target)
            return {"model": self.translator.model, "source_language": src, "target_language": target, **res,
                    "llm_usage": dict(self.translator.llm.usage)}

        analysis = step("analysis", analyze)

        def translate(p) -> dict:
            self.translator.llm.reset_usage()
            partial = out / "03_translation.partial.json"

            def on_batch(r):
                save_json(partial, {"translations": r["translations"]})
                p(len(r["translations"]) / len(segments), f"Çeviri: {len(r['translations'])}/{len(segments)} segment")

            res = self.translator.translate(segments, src, target, analysis, on_batch=on_batch)
            partial.unlink(missing_ok=True)
            return {"source_language": src, "target_language": target, "source": rel(source),
                    "asr_model": asr["model"], "llm_model": self.translator.model,
                    "duration_sec": asr["duration_sec"], "speakers": asr["speakers"],
                    "segments": [{**s, "translation": res["translations"][s["id"]]} for s in segments],
                    "glossary": res["glossary"], "batches": res["batches"], "llm_usage": dict(self.translator.llm.usage)}

        translation = step("translation", translate)

        def clone(p) -> dict:
            p(0.0, "Konuşmacı referansları hazırlanıyor")
            refs = build_refs(source, segments, asr["words"], out / "refs")
            p(0.02, "OmniVoice yükleniyor")
            run = self.tts.synthesize(
                translation["segments"], target, refs, out, out / "tts",
                on_segment=lambda n, total, row: p(0.05 + 0.95 * n / total, f"Seslendirme: {n}/{total} segment"))
            return {"refs": refs, **run}

        tts = step("tts", clone)

        sep = None
        if self.separator is not None:
            sep = step("separation", lambda p: self.separator.separate(source, segments, out / "separation"))

        is_video = has_video(source)
        return step("mix", lambda p: mix(tts, out, asr["duration_sec"],
                                         out / sep["files"]["bed"] if sep else None, source, is_video,
                                         out / "final"))


def default_pipeline(llm: str = "anthropic/claude-sonnet-5.5", batch: int = 20, background: bool = True) -> Pipeline:
    return Pipeline(ElevenLabsASR(), LLMTranslator(llm, batch_size=batch), OmniVoiceTTS(),
                    DemucsSeparator() if background else None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="video ya da ses dosyası")
    ap.add_argument("--target", required=True, help="hedef dil (ISO-639-1, ör. tr, en, de)")
    ap.add_argument("--source", default=None, help="kaynak dil; boş bırakılırsa ASR algılar")
    ap.add_argument("--job", default=None, help="çıktı klasörü adı (varsayılan <dosya>_<hedef>)")
    ap.add_argument("--llm", default="anthropic/claude-sonnet-5.5", help="OpenRouter model kimliği")
    ap.add_argument("--batch", type=int, default=20, help="LLM'e tek seferde verilen segment sayısı")
    ap.add_argument("--no-background", action="store_true", help="orijinal arka plan sesini ekleme")
    ap.add_argument("--redo", choices=STEP_KEYS, help="bu adımı ve sonrakileri baştan çalıştır")
    args = ap.parse_args()

    src = (ROOT / args.input).resolve()
    out = OUT / (args.job or f"{src.stem}_{args.target}")
    last = {"key": None}

    def progress(key, frac, overall, msg):
        if key != last["key"] or frac >= 1.0 or "/" in msg:
            print(f"[{overall * 100:5.1f}%] {msg}", flush=True)
            last["key"] = key

    pipe = default_pipeline(args.llm, args.batch, not args.no_background)
    print(f"== {args.input} → {args.target}  ({rel(out)})")
    res = pipe.run(src, args.target, args.source, out, args.redo, progress)
    print(f"Bitti: {', '.join(rel(out / f) for f in res['files'].values())}")


if __name__ == "__main__":
    main()
