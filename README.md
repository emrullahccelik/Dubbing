# Dubbing

Ses tonunu koruyan dublaj hattı üzerine çalışma. Hedeflenen akış:

```
video → ASR (konuşmadan metne, konuşmacı ayrımıyla) → çeviri → ses klonlama → mikslenmiş video
```

Şu an **ASR adımı** tamamlandı: OpenRouter üzerinden 14 model, biri İngilizce biri Türkçe iki test
videosunda karşılaştırıldı. Seçilen model **ElevenLabs Scribe v2**, yedeği **Microsoft MAI-Transcribe 2**.

## Raporlar

- [`reports/stt-test-raporu.md`](reports/stt-test-raporu.md) — 14 ASR modelinin karşılaştırması:
  doğruluk, konuşmacı ayrımı, zaman damgası, hız ve maliyet
- [`reports/model-arastirmasi.md`](reports/model-arastirmasi.md) — açık ve kapalı kaynak model
  araştırması, GPU ve maliyet tahminleri

## Kurulum

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY değerini doldur
```

ffmpeg'in sistemde kurulu olması gerekmiyor; `imageio-ffmpeg` paketiyle geliyor.

## Kullanım

```bash
# ASR: bütün modelleri bir video üzerinde çalıştır
.venv/bin/python -m stt.run_stt --input docs/test_en.mp4
.venv/bin/python -m stt.run_stt --input docs/test_tr.mp4 --language tr --models elevenlabs mai2

# Karşılaştırma: WER, zaman damgası ve konuşmacı etiketi uyumu
.venv/bin/python -m stt.compare --name test_en
.venv/bin/python -m stt.compare --name test_tr --lang tr
```

Model anahtarları `stt/run_stt.py` içindeki `MODELS` listesinde tanımlı.

## Depoda olmayanlar

- `docs/` — test videoları (telifli içerik)
- `outputs/` — koşu çıktıları: ham API yanıtları, dökümler, klonlamaya hazır dublaj manifestleri
- `.env` — API anahtarı

## Dizinler

| Yol | İçerik |
| --- | --- |
| `stt/` | ASR koşucusu, ortak yardımcılar ve karşılaştırma aracı |
| `reports/` | Test raporları ve model araştırması |
| `outputs/stt/<job>/<model>/` | Her modelin ham yanıtı, `transcript.json` ve okunabilir dökümü |
| `outputs/dubbing/<job>.json` | Klonlama adımına hazır manifest: konuşmacı, zaman aralığı, orijinal ve çevrilmiş metin |
