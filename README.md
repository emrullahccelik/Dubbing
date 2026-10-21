# Dubbing

Bir video ya da ses kaydını başka bir dile, **konuşmacıların kendi sesleriyle** dublajlayan hat.
Konuşma metne çevrilir, bağlamı korunarak tercüme edilir, her cümle orijinal konuşmacının sesi klonlanarak
yeniden seslendirilir ve müzik, gülüşme gibi arka plan sesleriyle birlikte videoya geri yerleştirilir.

Komut satırından ya da web arayüzünden kullanılabilir; Docker ile de çalıştırılabilir.

## Örnek

BBC Learning English'in 2,5 dakikalık bir bölümü (5 konuşmacı), İngilizceden üç dile:

| | Dosya |
| --- | --- |
| Orijinal (İngilizce) | [samples/original_en.mp3](samples/original_en.mp3) |
| Türkçe dublaj | [samples/dub_tr.mp3](samples/dub_tr.mp3) |
| Almanca dublaj | [samples/dub_de.mp3](samples/dub_de.mp3) |
| Fransızca dublaj | [samples/dub_fr.mp3](samples/dub_fr.mp3) |

Örnek bir satır:

| | |
| --- | --- |
| EN | No, I'm not. I've just been with the rest of the team. We're working on a project, and they're just getting everything wrong. |
| TR | Evet, değilim. Az önce ekibin geri kalanıyla birlikteydim. Bir proje üzerinde çalışıyoruz ve her şeyi yanlış yapıyorlar. |
| DE | Nein, bin ich auch nicht. Ich komme gerade vom Team. Wir arbeiten an einem Projekt, und die machen einfach alles falsch. |
| FR | Non, pas vraiment. Je sors d'une réunion avec le reste de l'équipe. On travaille sur un projet, et ils se trompent sur tout. |

## Nasıl çalışır

```
video / ses
   │
   ├─ 1. ASR ─────────── konuşma → metin, kelime zaman damgaları, konuşmacı ayrımı
   ├─ 2. Analiz ──────── konu, üslup, konuşmacılar ve sözlük
   ├─ 3. Çeviri ──────── 20'şerli bloklar hâlinde, bağlam ve sözlükle
   ├─ 4. Ses klonlama ── her cümle orijinal konuşmacının sesiyle, orijinal süresinde
   ├─ 5. Arka plan ───── müzik, ortam sesi ve konuşma arasındaki gülüşmeler ayrıştırılır
   └─ 6. Miks ────────── cümleler zaman çizelgesine yerleşir, arka planla karışır, videoya eklenir
```

**1. ASR** — [ElevenLabs Scribe v2](https://elevenlabs.io/speech-to-text) (OpenRouter üzerinden). Kelimeler
konuşmacı değişiminde, uzun sessizlikte ya da uzun cümlelerin sonunda segmentlere bölünür. `[güler]`,
`[music]` gibi konuşma dışı işaretler seslendirilecek metinden ayıklanır, zamanlarıyla ayrıca saklanır.

**2. Analiz** — Bütün döküm bir kez LLM'e verilir. Model içeriğin ne olduğunu, üslubunu ve konuşmacıları özetler,
bir sözlük çıkarır: özel isimler, marka ve program adları, terimler ve çevrilmeden kalması gereken ifadeler
(örneğin bir İngilizce dersinde öğretilen deyim).

**3. Çeviri** — Segmentler tek tek değil 20'şerli bloklar hâlinde çevrilir. Her blokla birlikte analiz özeti,
sözlük, önceki satırlar (çevirileriyle) ve sonraki satırlar gönderilir; böylece çeviri doğal ve tutarlı olur.
Her satırın konuşma süresi de verilir, çeviri o sürede söylenebilecek uzunlukta tutulur. Model yeni bir terime
karar verirse sözlüğe eklenir ve sonraki bloklarda kullanılır. Varsayılan model `anthropic/claude-sonnet-5.5`;
OpenRouter'daki herhangi bir modelle değiştirilebilir.

**4. Ses klonlama** — [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice). Her cümle orijinal süresi hedef
verilerek üretilir. Referans ses:
- Cümle 3 saniyeden uzunsa **kendi orijinal kaydı**; cümlenin duygusu ve tonlaması da aktarılır.
- Daha kısaysa konuşmacının **ortak referansı**: en uzun cümlelerinden kesilip birleştirilen ~10 saniyelik kayıt.

**5. Arka plan** — [Demucs](https://github.com/adefossez/demucs) (`htdemucs_ft`) orijinal sesi konuşma
ve geri kalan olarak ayırır. Gülüşme, alkış gibi insan sesleri çoğunlukla konuşma tarafına düştüğü için konuşma
kanalının yalnızca cümlelerin dışında kalan kısmı korunur; cümle içinde sessize alınır.

**6. Miks** — Her cümle orijinal başlangıç zamanına yerleşir. Üretilen ses, sonraki cümleye kadar olan boşluğa
sığıyorsa olduğu gibi kalır (kısaysa yavaşlatılmaz); sığmıyorsa tonu korunarak sığacak kadar hızlandırılır.
Sonuç arka planla karıştırılır; girdi videoysa görüntü yeniden kodlanmadan yeni sesle birleştirilir.

## Proje yapısı

```
dub/
├── asr.py          1. ElevenLabs Scribe ile döküm, segmentleme, işaret ayıklama
├── translate.py    2–3. LLM istemcisi (OpenRouter), analiz ve bloklu çeviri
├── tts.py          4. Referans hazırlama ve OmniVoice ile seslendirme
├── separate.py     5. Demucs ile arka plan ayrıştırma
├── mix.py          6. Yerleştirme, hızlandırma, karıştırma, video birleştirme
├── pipeline.py     Adımları sırayla çalıştıran Pipeline sınıfı ve komut satırı
├── common.py       Yollar, API anahtarı, ffmpeg yardımcıları
└── web/
    ├── app.py      FastAPI sunucusu: yükleme, iş sırası, ilerleme, indirme
    └── static/     Tek sayfalık arayüz
samples/            README'deki örnek sesler
data/               Çalışma çıktıları
Dockerfile, docker-compose.yml, requirements.txt
```

## Kurulum

Gereksinimler: Python 3.12, NVIDIA GPU (seslendirme ~2.3 GB VRAM kullanıyor; 4 GB'lık kartta çalışıyor) ve
[OpenRouter](https://openrouter.ai/keys) API anahtarı. ffmpeg ayrıca kurulmaz, `imageio-ffmpeg` paketiyle gelir.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY değerini doldur
```

Model ağırlıkları (OmniVoice, Demucs) ilk çalıştırmada indirilir.

## Kullanım

### Web arayüzü

```bash
.venv/bin/python -m dub.web            # http://localhost:8000
```

Dosyayı sürükleyip bırak, kaynak (ya da otomatik algılama) ve hedef dili seç. Her adımın ilerlemesi ayrı ayrı
görünür; bittiğinde sonuç sayfada oynatılır ve indirilir. Çeviri, orijinaliyle yan yana tablo olarak gösterilir.
İşler GPU'da sırayla çalışır; hata alan bir iş kaldığı yerden yeniden denenebilir.

### Komut satırı

```bash
.venv/bin/python -m dub.pipeline --input video.mp4 --target tr
.venv/bin/python -m dub.pipeline --input kayit.mp3 --source en --target de --llm google/gemini-3.8-flash
```

| Seçenek | Açıklama |
| --- | --- |
| `--target` | Hedef dil (ISO-639-1: `tr`, `en`, `de`, `fr`, `es`, …) |
| `--source` | Kaynak dil; verilmezse ASR algılar |
| `--llm` | Çeviri için OpenRouter model kimliği |
| `--batch` | Tek seferde çevrilen segment sayısı (varsayılan 20) |
| `--ref` | `segment` (varsayılan) ya da `speaker`: her cümle konuşmacının ortak referansıyla |
| `--no-background` | Orijinal arka plan sesini ekleme |
| `--until <adım>` | O adımdan sonra dur (`asr`, `analysis`, `translation`, `tts`, `separation`, `mix`) |
| `--redo <adım>` | O adımı ve sonrakileri baştan çalıştır |
| `--job` | Çıktı klasörünün adı |

### Docker

Ana makinede NVIDIA sürücüsü ve [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) gerekir.

```bash
docker compose up --build              # http://localhost:8000
```

Çıktılar `./data` klasörüne, model ağırlıkları `model-cache` volume'una yazılır. API anahtarı `.env`'den okunur.

## Çıktılar

Her iş kendi klasöründe: komut satırında `data/pipeline/<dosya>_<hedef dil>/`, web arayüzünde `data/web/<id>/`.
Her adımın sonucu JSON olarak kaydedilir; dosyası olan adım tekrar çalıştırılmaz, okunur.

| Dosya | İçerik |
| --- | --- |
| `01_asr.json` | Segmentler, kelimeler, konuşma dışı sesler |
| `02_analysis.json` | Özet, üslup, konuşmacılar, sözlük |
| `03_translation.json` | Orijinal ve çeviri yan yana, son sözlük, LLM kullanımı ve maliyeti |
| `04_tts.json` | Kullanılan referanslar, segment başına üretilen ses ve süre |
| `05_separation.json` | Ayrıştırılan kanallar |
| `06_mix.json` | Segment yerleşimi ve hızlandırma oranları |
| `refs/`, `tts/`, `separation/` | Referans sesler, seslendirilen segmentler, ayrıştırılmış kanallar |
| `final/dub.mp4` · `final/dub.m4a` · `final/dub.wav` | Sonuç: video ya da ses, ve sıkıştırılmamış ses |

## Notlar

- OmniVoice ağırlıkları ticari olmayan kullanım lisanslıdır (CC-BY-NC).
- Kaynak dilden hedef dile geçerken metin çok uzuyorsa (ör. Türkçeden İngilizceye hızlı konuşmalar) cümleler
  belirgin şekilde hızlandırılabilir.
- Uzun kayıtlar ASR'a tek istekte gönderilir.
