# STT Test Raporu - OpenRouter Modelleri

Oct 10, 2026 · @Emrullah Çelik

Dublaj hattının ilk adımı (ASR: konuşmadan metne) için OpenRouter üzerinden **14 model, 15 ayar** ile test edildi. Her model iki ses dosyasında da çalıştırıldı: biri İngilizce (`test_en`), biri Türkçe (`test_tr`). Ölçülenler: metin doğruluğu, **konuşmacı ayrımı (diarization)**, kelime zaman damgası, hız ve maliyet.

Test edilen modeller: ElevenLabs Scribe v2, OpenAI GPT Transcribe, Fish Audio Transcribe 1 Pro, AssemblyAI Universal-3.5 Pro, Meta Muse Voice Transcribe 1.0 (iki ayar), Grok STT 1.0, Deepgram Nova-3, Microsoft MAI-Transcribe 2 ve 1.5, NVIDIA Nemotron 3.5 ASR 0.6B, Qwen3-ASR 1.7B ve 0.6B, Whisper large-v3 ve large-v3-turbo.

## Kısa Sonuç

- **Seçim: ElevenLabs Scribe v2.** İki dilde de en tutarlı model. Konuşmacı ayrımı İngilizcede kusursuz, Türkçede bağlamla uyumlu; zaman damgaları referans kalitesinde.
- **Yedek: Microsoft MAI-Transcribe 2.** Türkçede ElevenLabs'e en yakın model (metinde %13.6 fark, konuşmacı etiketlerinde %95.8 uyum) ve biraz daha ucuz. Ancak İngilizce testte konuşmacıları karıştırdı, yani diarization'ı ElevenLabs kadar güvenilir değil.
- **Konuşmacı ayrımı, model seçimini belirleyen kriter.** 14 modelden yalnızca 5'i OpenRouter üzerinden konuşmacı bilgisi veriyor: ElevenLabs, Grok, Fish, MAI-2, Deepgram. Geri kalanı (AssemblyAI, OpenAI, Meta, MAI-1.5, Whisper, Qwen, Nemotron) hiç vermiyor.
- **Dil, modelleri net şekilde ayırdı.** İngilizce stüdyo kaydında bütün kapalı modeller %0–0.5 hata aralığında toplandı, yani doğruluk ayırt edici olmadı. Türkçe sohbet dilinde fark %13'ten %92'ye çıktı.
- **Grok STT, İngilizcede kusursuzdu ama Türkçede geride kaldı.** "tuvalet eğitimi" → "tuvalete gittim", "onayladınız" → "ona eğlenirsin", "iş hayatın nasıl Tayfun" → "senin kaç golünüz" gibi bariz hatalar var. Konuşmacı değişimini de genellikle bir kelime geç algılıyor.
- **Türkçede elenenler:** Fish Audio (zaman damgaları 12 sn'ye kadar kayıyor, kelimelerin %60'ı sıfır süreli), Qwen3-ASR (zaman damgaları bozuk) ve özellikle **Nemotron 0.6B** (%92 hata, metnin üçte biri kayıp, çıktı büyük ölçüde anlamsız).
- **Whisper large-v3-turbo İngilizcede cümle parçalarını tamamen atladı** (%4.9 hata, iki ayrı koşuda da aynı). Dublajda bu içerik kaybı demek.

## Test Kurulumu

| | İngilizce (`test_en`) | Türkçe (`test_tr`) |
| --- | --- | --- |
| Kaynak | BBC "The English We Speak – Fall on stony ground" | [Rabarba 1638: Anlatanadam ve Tayfun Biçer](https://www.youtube.com/watch?v=aGXL_xdwUhU) (Karnaval), bölümün 10:00–12:30 aralığı |
| Dosya | `docs/test_en.mp4`, 2:34.7 | `docs/test_tr.mp4`, 2:30.0 |
| Konuşmacı | 5 kişi: Feifei, Phil (sunucular) ve sokak röportajındaki 3 kişi | 3 erkek: Mesut Süre, Anlatanadam, Tayfun Biçer |
| Zorluk | Temiz stüdyo kaydı, düzgün sıralı konuşma turları | Hızlı ve kısa turlar, araya girmeler, gülme, günlük konuşma dili, benzer tınıda erkek sesleri |
| `language` | verilmedi (otomatik algılama) | `tr` |

Ortak ayarlar:

| | |
| --- | --- |
| Ses | ffmpeg ile mono 16 kHz WAV. Deepgram'a kayıpsız FLAC olarak gönderildi |
| API | `POST https://openrouter.ai/api/v1/audio/transcriptions`, base64 ses |
| Ortam | `.venv` (Python 3.12), `requirements.txt`. ffmpeg sistemde kurulu değil, `imageio-ffmpeg` paketiyle geliyor |
| Depo | Test videoları (`docs/`) telifli içerik olduğu için, koşu çıktıları (`outputs/`) da boyutu nedeniyle depoya dahil değil. Kodla birlikte kendi videonuzla yeniden üretilebilir |
| Maliyet | İki turun toplamı ~$0.22 |

### Tekrar çalıştırma

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # OPENROUTER_API_KEY değerini doldur

.venv/bin/python -m stt.run_stt --input docs/test_en.mp4                    # tüm modeller
.venv/bin/python -m stt.run_stt --input docs/test_tr.mp4 --language tr
.venv/bin/python -m stt.run_stt --input docs/test_tr.mp4 --models elevenlabs mai2

.venv/bin/python -m stt.compare --name test_en                              # karşılaştırma
.venv/bin/python -m stt.compare --name test_tr --lang tr
```

Model anahtarları: `elevenlabs openai fish assemblyai meta meta_diar grok deepgram mai2 mai15 nemotron qwen17 qwen06 whisper_turbo whisper_v3`

API anahtarı `.env` dosyasındaki `OPENROUTER_API_KEY` satırından okunur (`.env.example` dosyasına bakın). `OPENROUTER_API_KEY` ortam değişkeni varsa o öncelikli.

## Model Özellikleri ve OpenRouter Ayarları

| Model | OpenRouter ID | Sağlayıcı | Kelime zaman damgası | Konuşmacı ayrımı (OpenRouter üzerinden) |
| --- | --- | --- | --- | --- |
| ElevenLabs Scribe v2 | `elevenlabs/scribe-v2` | ElevenLabs | ✅ | ✅ `provider.options.elevenlabs.diarize = true` |
| Grok STT 1.0 | `x-ai/grok-stt-1.0` | xAI | ✅ | ✅ `provider.options.xai.diarize = true` (anahtar `x-ai` olursa sessizce yok sayılıyor) |
| Fish Audio Transcribe 1 Pro | `fish-audio/transcribe-1-pro` | Fish Audio | ✅ (80 ms adım) | ✅ Varsayılan olarak açık; metin içinde `<\|speaker:N\|>` etiketi, kelimelere hizalanarak atandı |
| Microsoft MAI-Transcribe 2 | `microsoft/mai-transcribe-2` | Azure | ✅ | ✅ `provider.options.azure.diarization = {enabled: true}` |
| Deepgram Nova-3 | `deepgram/nova-3` | Deepgram | ✅ | ✅ `provider.options.deepgram.diarize = true` |
| AssemblyAI Universal-3.5 Pro | `assemblyai/universal-3-5-pro` | AssemblyAI | ✅ | ❌ `speaker_labels` kabul edildi ama sonuca yansımadı |
| Meta Muse Voice Transcribe 1.0 | `meta/muse-voice-transcribe-1.0` | Meta | ❌ | ❌ `mode = DIARIZATION` kabul ediliyor ama OpenRouter yanıtta sadece `text` döndürüyor |
| OpenAI GPT Transcribe | `openai/gpt-transcribe` | OpenAI | ❌ | ❌ |
| Microsoft MAI-Transcribe 1.5 | `microsoft/mai-transcribe-1.5` | Azure | ❌ | ❌ |
| Whisper large-v3 | `openai/whisper-large-v3` | DeepInfra / Together / Groq | ⚠️ sağlayıcıya göre değişiyor | ❌ |
| Whisper large-v3-turbo | `openai/whisper-large-v3-turbo` | DeepInfra / Groq | ✅ | ❌ |
| Qwen3-ASR 1.7B / 0.6B | `qwen/qwen3-asr-1.7b`, `qwen/qwen3-asr-0.6b` | DeepInfra | ✅ (çok sayıda sıfır süreli kelime) | ❌ |
| NVIDIA Nemotron 3.5 ASR 0.6B | `nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b` | DeepInfra | ✅ | ❌ |

Whisper, Qwen3-ASR ve Nemotron açık ağırlıklı modeller. Burada OpenRouter'daki barındırılan sürümleri test edildi; yerel GPU'da da çalıştırılabilirler.

**OpenRouter'a özgü notlar:**
- Sağlayıcıya özel parametreler `provider.options.<sağlayıcı>.<parametre>` alanından iletiliyor. Bazı sağlayıcılar (Meta, Azure) bu alanı doğruluyor ve geçersiz değerde 400 dönüyor. Bazıları (AssemblyAI, xAI) bilinmeyen anahtarları sessizce yok sayıyor. Bu yüzden her parametrenin çıktıda gerçekten etkisi olup olmadığı tek tek kontrol edildi.
- `verbose_json` (zaman damgası) OpenAI GPT Transcribe, Meta ve MAI-1.5'te 400 döndürüyor.
- **Aynı model isteği farklı sağlayıcılara yönlendirilebiliyor ve yetenek değişiyor.** Whisper large-v3 İngilizce turda kelime zaman damgası verdi, Türkçe turda yalnızca segment verdi. Kod bu durumda sağlayıcının segmentlerini yedek olarak kullanıyor (`segment_source` alanı hangisinin kullanıldığını gösteriyor).
- **Deepgram 4.9 MB'lık WAV'ı "large audio inputs" hatasıyla reddetti.** Kayıpsız FLAC (2.6 MB) kabul edildi. Uzun videolarda istek boyutu sınırlarına dikkat etmek gerekecek.
- **AssemblyAI Sync API tek istekte en fazla 120 sn ses kabul ediyor.** Ses en sessiz noktadan 2 parçaya bölündü. Parçalar arası konuşmacı kimlikleri eşleşmediği için önek eklenir (`0:1` gibi).
- **Microsoft modellerinin listelenen fiyatı ($0.1 ve $0.36) saat başına.** 3 sn'lik bir klipte ölçülerek doğrulandı.
- Upstream zaman aşımı ~60 sn. Meta 2:30'luk sesi ~46 sn'de işledi; daha uzun sesler bölünmeli.
- **Gecikmeler koşudan koşuya ciddi değişebiliyor.** Nemotron aynı İngilizce sesi bir koşuda 9.6 sn'de, başka bir koşuda 121.6 sn'de işledi.
- **ElevenLabs'e özel kelime/terim listesi (`keyterms`) verilmedi.** API bunu destekliyor (en fazla 1000 terim, %20 ek ücret) ama testlerde kullanılmadı; bütün sonuçlar modellerin ham performansını gösteriyor.

## İngilizce Test (`test_en`)

### Özet tablo

| Model | Konuşmacı | WER | Zaman damgası farkı (ElevenLabs'e göre, ort. / p95) | Gecikme | Saatlik |
| --- | --- | --- | --- | --- | --- |
| **ElevenLabs Scribe v2** | ✅ 5/5 | 0.00% | (referans) | 7.9 sn | $0.11* |
| **Grok STT 1.0** | ✅ 5/5 | 0.26% | 24 / 55 ms | 7.3 sn | $0.10 |
| **Fish Audio Transcribe 1 Pro** | ✅ 5/5 | 0.00% | 83 / 180 ms | 9.5 sn | $0.36 |
| MAI-Transcribe 2 | ⚠️ 5 kimlik, karışık | 0.00% | 31 / 80 ms | 9.5 sn | $0.10 |
| Deepgram Nova-3 | ⚠️ 3 kişi | 0.26% | 67 / 190 ms | 3.5 sn | $0.26 |
| AssemblyAI Universal-3.5 Pro | ❌ | 0.26% | 40 / 102 ms | 5.7 sn | $0.45 |
| Whisper large-v3 | ❌ | 1.03% | 30 / 69 ms | 8.9 sn | $0.09 |
| MAI-Transcribe 1.5 | ❌ | 0.00% | – | 8.0 sn | $0.36 |
| Meta Muse Voice Transcribe | ❌ | 0.26% | – | 44.5 sn | $0.18 |
| OpenAI GPT Transcribe | ❌ | 0.52% | – | 8.9 sn | $0.27 |
| Qwen3-ASR 1.7B | ❌ | 0.52% | 138 / 480 ms | 11.1 sn | $0.027 |
| Qwen3-ASR 0.6B | ❌ | 0.52% | 137 / 480 ms | 10.9 sn | $0.012 |
| Nemotron 3.5 ASR 0.6B | ❌ | 1.55% | 196 / 419 ms | 121.6 sn | $0.012 |
| Whisper large-v3-turbo | ❌ | **4.90%** | 162 / 430 ms | 8.3 sn | $0.012 |

\* ElevenLabs uç noktası OpenRouter'da `discount: 0.5` ile listeleniyor. İndirim kalkarsa fiyat ~$0.22/saat olur.

Saatlik fiyatlar bu testte ölçülen gerçek maliyetten hesaplandı.

### Metin doğruluğu

Resmi birebir döküm yok: BBC'nin yayımladığı metin dolgu seslerini içermiyor. Bu yüzden ElevenLabs çıktısı **uzlaşı referansı** olarak alındı. ElevenLabs, Fish, MAI-2 ve MAI-1.5'in çıktıları birebir aynı. Bütün farklar elle kontrol edildi. Yazım farkları ("Fei Fei", "Faye Faye" / "Feifei", "programme" / "program") ve büyük/küçük harf hata sayılmadı.

| Model | Referanstan farklar |
| --- | --- |
| ElevenLabs, Fish, MAI-2, MAI-1.5 | yok |
| AssemblyAI, Grok, Deepgram, Meta | "um" atlandı |
| OpenAI GPT Transcribe | "um" ve tekrarlanan "I" atlandı (temizlenmiş döküm) |
| Qwen3-ASR 1.7B / 0.6B | "the expression **fall** on stony ground" → "for"; "um" atlandı |
| Whisper large-v3 | "fall" → "for"; fazladan "ground" eklendi; "um" ve "I" atlandı |
| Nemotron | "Feifei" → "Feife", "pay cut" → "paycup", "fall" → "for"; "um" ve "I" atlandı |
| Whisper large-v3-turbo | **"That fell on stony ground. He" ve "We hope that this program is fertile ground for your" tamamen atlandı.** "fall" → "for"; fazladan "and" eklendi. İki ayrı koşuda da aynı sonuç |

Kapalı modeller içerikte birebir aynı noktada buluşuyor; bu klipte doğruluk ayırt edici değil. Dublaj açısından dolgu seslerini koruyan modeller (ElevenLabs, Fish, MAI-2) daha iyi, çünkü konuşmacının ritmi ve segment süresi daha doğru yansıyor. Whisper-turbo'nun cümle parçası atlaması dublajda içerik kaybı demek; bu model elenmeli.

### Konuşmacı ayrımı

Doğru dağılım: Feifei, Phil, Röportaj-1 ("I told my son..."), Röportaj-2 ("A school near me..."), Röportaj-3 ("I, I really wanted...").

| Model | Bulunan | ElevenLabs ile uyum | Ayrıntı |
| --- | --- | --- | --- |
| ElevenLabs | 5 | (referans) | ✅ Bütün turlar doğru |
| Grok | 5 | %100 | ✅ Bütün turlar doğru |
| Fish Audio | 5 | %100 | ✅ Turlar doğru. Tek kusur: Röportaj-1'in ilk kelimesi "I" 3.6 sn erkene kaymış |
| MAI-Transcribe 2 | 5 kimlik | %88.4 | ❌ Feifei iki kimliğe bölünmüş. Röportaj-3, Feifei'nin ikinci kimliğiyle birleştirilmiş |
| Deepgram Nova-3 | 3 | %89.6 | ❌ Röportaj-1 Phil sanılmış. Röportaj-2 ve 3 tek kişi olarak birleştirilmiş |
| Diğerleri | – | – | Bilgi yok |

Konuşmacı bilgisi olmayınca neler bozulduğuna AssemblyAI iyi bir örnek. Feifei'nin "Like your ideas, Phil." cümlesi, Phil'in "Don't remind me..." cümlesiyle aynı segmente düştü. Klonlama adımında bu, yanlış sesle seslendirme demek.

### Kelime zaman damgası uyumu

ElevenLabs referansına göre kelime başlangıç farkı:

| Model | Ortalama | p95 | Sıfır süreli kelime |
| --- | --- | --- | --- |
| Grok | 24 ms | 55 ms | 0 |
| Whisper large-v3 | 30 ms | 69 ms | 0 |
| MAI-Transcribe 2 | 31 ms | 80 ms | 0 |
| AssemblyAI | 40 ms | 102 ms | 0 |
| Deepgram | 67 ms | 190 ms | 0 |
| Fish Audio | 83 ms | 180 ms | 9 |
| Qwen3-ASR 0.6B / 1.7B | 137 / 138 ms | 480 ms | 48 / 50 |
| Whisper large-v3-turbo | 162 ms | 430 ms | 0 |
| Nemotron | 196 ms | 419 ms | 0 |

ElevenLabs, Grok, MAI-2 ve Whisper large-v3 birbirine 30 ms içinde uyuyor. Ses kesimi için güvenilir olanlar bunlar. Qwen'in zaman damgaları zayıf: kelimelerin ~%13'ü sıfır süreli.

## Türkçe Test (`test_tr`)

Elde birebir döküm yok. Bu yüzden değerlendirme iki yoldan yapıldı: modellerin birbirleriyle uyumu ölçüldü, ayrışılan yerler dilbilgisi ve bağlam açısından elle okundu.

Türkçe normalizasyon (`--lang tr`): İ/ı dönüşümü doğru yapıldı ve rakamlar okunuşa çevrildi ("1500" → "bin beş yüz"). Böylece yazım biçimi farkları hata sayılmadı.

### Özet tablo

Sıralama: ElevenLabs'ten metin farkı (WER) düşük olandan yükseğe.

| Model | Konuşmacı | ElevenLabs'ten metin farkı | Zaman damgası farkı (ort. / p95) | Sıfır süreli kelime | Gecikme | Saatlik |
| --- | --- | --- | --- | --- | --- | --- |
| **ElevenLabs Scribe v2** | ✅ 3 | (referans) | (referans) | 5 / 387 | 11.4 sn | $0.11* |
| **MAI-Transcribe 2** | ✅ 3 | **%13.6** | 32 / 90 ms | 0 / 391 | 8.3 sn | $0.10 |
| Grok STT 1.0 | ⚠️ 3 | %15.2 | 29 / 61 ms | 0 / 371 | 7.2 sn | $0.10 |
| MAI-Transcribe 1.5 | ❌ | %17.3 | – | – | 7.6 sn | $0.36 |
| Meta Muse Voice (DIARIZATION) | ❌ | %18.6 | – | – | 47.2 sn | $0.18 |
| OpenAI GPT Transcribe | ❌ | %19.4 | – | – | 9.6 sn | $0.27 |
| Meta Muse Voice | ❌ | %20.2 | – | – | 46.3 sn | $0.18 |
| Deepgram Nova-3 | ❌ 2 kişi | %21.5 | 80 / 211 ms | 0 | 4.3 sn | $0.26 |
| Whisper large-v3-turbo | ❌ | %22.3 | 118 / 403 ms | 7 | 6.8 sn | $0.012 |
| Whisper large-v3 | ❌ | %23.0 | yalnızca segment | – | 7.0 sn | $0.09 |
| AssemblyAI Universal-3.5 Pro | ❌ | %23.8 | 593 / 2109 ms | 0 | 6.7 sn | $0.45 |
| Qwen3-ASR 1.7B | ❌ | %26.7 | 531 / 2632 ms | 143 | 14.6 sn | $0.027 |
| Fish Audio Transcribe 1 Pro | ⚠️ 3 | %33.5 | **11659 / 41042 ms** | **242 / 394** | 11.3 sn | $0.36 |
| Qwen3-ASR 0.6B | ❌ | %36.1 | 549 / 3200 ms | 138 | 7.2 sn | $0.012 |
| Nemotron 3.5 ASR 0.6B | ❌ | **%92.2** | 919 / 933 ms | 0 | 8.6 sn | $0.012 |

\* ElevenLabs fiyatı %50 indirimli.

İkili metin farkı: ElevenLabs↔MAI-2 %13.6, ElevenLabs↔Grok %15.2, Grok↔MAI-2 %19.2. Bu üçü bir küme oluşturuyor; geri kalan modeller hepsinden %25'in üzerinde ayrışıyor.

### Konuşmacı ayrımı

Konuşmacı kimlikleri içerikten doğrulandı. S0 "Senin iş hayatın nasıl Tayfun?" diye soruyor, S2 "İyi abi" diye cevap veriyor. Buna göre S0 = Mesut Süre, S1 = Anlatanadam, S2 = Tayfun Biçer.

| Model | Bulunan | ElevenLabs ile uyum | Ayrıntı |
| --- | --- | --- | --- |
| ElevenLabs | 3 | (referans) | ✅ Bağlamla çelişen tur bulunamadı. Tur dağılımı: 25 / 16 / 12 |
| MAI-Transcribe 2 | 3 | **%95.8** | ✅ Neredeyse aynı. Birkaç kısa tur farklı atanmış |
| Grok | 3 | %95.1 | ⚠️ Turları doğru kişilere veriyor ama **konuşmacı değişimini genellikle bir kelime geç algılıyor**. Tur başı kelimeleri ("Yeter", "Menzili", "Bir dakika", "Vallahi") bir önceki konuşmacıya yazılmış |
| Deepgram Nova-3 | 2 | %78.8 | ❌ Üç kişiyi ikiye indirmiş |
| Fish Audio | 3 | %72.9 | ❌ 3 kişi buluyor ama zaman damgaları kaydığı için segmentler ses üzerinde yanlış yerlere düşüyor |

Grok'un bir kelime gecikmesi dublaj açısından önemli: segmentin ilk kelimesi yanlış konuşmacının sesiyle seslendirilir.

### Metin doğruluğu

Ayrışılan yerler okunarak değerlendirildi:

| Yer | ElevenLabs | MAI-2 | Grok | Değerlendirme |
| --- | --- | --- | --- | --- |
| 00:00 | tuvalet eğitimi | tuvalet eğitimi | **tuvalete gittim** | Grok yanlış |
| 00:06 | sokaklara işemekten | yeter ya sokakları | sokakları | ElevenLabs dilbilgisi olarak doğru |
| 00:25 | aracın | aracın | **araçın** | Grok yazım hatası |
| 00:35 | **söyleyemeyeceğim** | söyleyemeyelim | söyleyemeyelim | Diğer ikisi uyuşuyor, ElevenLabs yanlış |
| 00:54 | bir daha **bineceksin** | bir daha yapacaksın | bir daha yapacaksın | Diğer ikisi uyuşuyor, ElevenLabs yanlış |
| 01:07 | onayladınız | onayladınız | **ona eğlenirsin** | Grok yanlış |
| 01:27 | aranda | **adamda** | **oranda** | ElevenLabs doğru ("öndekiyle aranda") |
| 01:52 | iş hayatın nasıl Tayfun | şoförlüğün nasıl Tayfun | **senin kaç golünüz** | Grok tamamen alakasız. İlk ikisi arasında bağlam (yolculuk cevabı) MAI-2'yi destekliyor |
| 01:57 | **de işinden** | deyişinden | şahsen | MAI-2 doğru ("deyişinden ... işkillendim") |
| 02:04 | çok dediğin | çok dediğin | **derin** | Grok yanlış |

Özetle:
- **Grok'ta bariz hatalar ve atlanmış ifadeler var.** Türkçe için en zayıf üç modelden biri.
- **ElevenLabs ve MAI-2 birbirine yakın; ikisinin de hataları var.** ElevenLabs bu koşuda 3 yerde diğer iki modelin uyuştuğu doğru karşılığı kaçırdı.
- **MAI-2 araya girmeleri daha çok yakalıyor** ("Hayır, bir dakika", "yeter ya"). Bunların bir kısmı üst üste konuşma olabilir.
- **Çıktılar koşudan koşuya biraz değişiyor.** Örneğin "deyişinden" kelimesini ElevenLabs bir koşuda doğru, bir koşuda yanlış yazdı. Küçük farkları tek koşuya dayanarak değerlendirmemek gerekiyor.

Kesin bir karar için kesitin elle birebir dökümünü çıkarmak gerekiyor.

## Dublaj Hattı İçin Öneri

1. **Birincil ASR:** ElevenLabs Scribe v2, `verbose_json` ve `timestamp_granularities=["word"]` ile, `diarize=true` açık olarak.
2. **Yedek:** Microsoft MAI-Transcribe 2, `diarization={enabled:true}` ile. Kritik işlerde iki modeli birlikte çalıştırıp konuşmacı ve metin farklarını işaretlemek ucuz bir kalite kontrolü olur (ikisinin toplamı ~$0.21/saat).
3. **Segmentleme:** Kelimeleri konuşmacı değişiminde, 0.8 sn üzeri sessizlikte veya 15 sn'yi aşan bir cümlenin sonunda böl (`stt/common.py: words_to_segments`). Her segment konuşmacı kimliğiyle birlikte klonlama adımına referans ses olarak gidecek.
4. **Açık ağırlık / yerel seçenek:** Whisper large-v3 İngilizcede iyi, ama konuşmacı ayrımı yok; yerelde pyannote gibi ayrı bir diarization modeliyle birlikte kullanmak gerekir. Türkçede açık ağırlıklı modellerin hiçbiri yeterli değil.

## Sınırlamalar ve Sonraki Adımlar

- **Her ses için tek koşu yapıldı.** Gecikmeler ve küçük metin farkları koşular arasında değişiyor. Karar verici farklar için tekrarlı ölçüm gerekir.
- **Birebir döküm yok.** Bütün oranlar ElevenLabs'e göre "fark", mutlak hata değil. Kesin WER ve konuşmacı hata oranı (DER) için Türkçe kesitin elle dökümü çıkarılmalı.
- Test edilmeyen koşullar: arka plan müziği veya gürültü (dizi/film sahnesi), kadın ve erkek seslerin karışık olduğu Türkçe içerik, üst üste konuşma, 5 dakikadan uzun ses (istek boyutu ve parçalama davranışı).
- `keyterms` gibi doğruluk artırıcı parametreler kullanılmadı. Özel isimlerin (Kocaeli, Tayfun gibi) yoğun olduğu içerikte bu ayar sonucu değiştirebilir.
- AssemblyAI ve Meta'nın diarization'ı kendi API'lerinde var, yalnızca OpenRouter üzerinden gelmiyor. İstenirse doğrudan API anahtarıyla ayrıca test edilebilir.

## Dosyalar

| Yol | İçerik |
| --- | --- |
| `stt/common.py` | Anahtar okuma, ses çıkarma ve kodlama (WAV/FLAC), sessizlikten bölme, API çağrısı, Fish etiket hizalama, segmentleme |
| `stt/run_stt.py` | Model tanımları (`MODELS`) ve test koşucusu |
| `stt/compare.py` | İkili WER, referans farkları, zaman damgası ve konuşmacı uyumu, Türkçe normalizasyon (`--lang tr`) |
| `docs/test_en.mp4`, `docs/test_tr.mp4` | Test videoları (depoda yok) |
| `outputs/stt/<test>/<model>/raw_*.json` | API'nin ham yanıtları (istek parametreleriyle) |
| `outputs/stt/<test>/<model>/transcript.json` | Ortak şema: `text`, `words`, `segments` (her biri `speaker` ve `speaker_label` ile), maliyet, süre, `segment_source` |
| `outputs/stt/<test>/<model>/transcript.txt` | Okunabilir döküm: zaman damgası + `[speaker_N]` etiketi + metin |
| `outputs/stt/<test>/summary.json` | Bütün modellerin özet metrikleri (`speakers`, `speaker_labels`, `turns_per_speaker` dahil) |
| `outputs/stt/<test>/comparison.json` | Karşılaştırma sonuçları |

`<test>` = `test_en` veya `test_tr`.

## Kaynaklar

- [OpenRouter – Transcription on OpenRouter](https://openrouter.ai/blog/tutorials/transcription-on-openrouter/)
- OpenRouter model sayfaları: [ElevenLabs Scribe v2](https://openrouter.ai/elevenlabs/scribe-v2), [OpenAI GPT Transcribe](https://openrouter.ai/openai/gpt-transcribe), [Fish Audio Transcribe 1 Pro](https://openrouter.ai/fish-audio/transcribe-1-pro), [AssemblyAI Universal-3.5 Pro](https://openrouter.ai/assemblyai/universal-3-5-pro), [Meta Muse Voice Transcribe 1.0](https://openrouter.ai/meta/muse-voice-transcribe-1.0), [Grok STT 1.0](https://openrouter.ai/x-ai/grok-stt-1.0), [Deepgram Nova-3](https://openrouter.ai/deepgram/nova-3), [MAI-Transcribe 2](https://openrouter.ai/microsoft/mai-transcribe-2), [MAI-Transcribe 1.5](https://openrouter.ai/microsoft/mai-transcribe-1.5), [Nemotron 3.5 ASR 0.6B](https://openrouter.ai/nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b), [Qwen3-ASR 1.7B](https://openrouter.ai/qwen/qwen3-asr-1.7b), [Qwen3-ASR 0.6B](https://openrouter.ai/qwen/qwen3-asr-0.6b), [Whisper large-v3](https://openrouter.ai/openai/whisper-large-v3), [Whisper large-v3-turbo](https://openrouter.ai/openai/whisper-large-v3-turbo)
- Model açıklamaları, sağlayıcılar ve fiyatlar: `GET https://openrouter.ai/api/v1/models?output_modalities=transcription` ve `GET https://openrouter.ai/api/v1/models/<id>/endpoints`
- [ElevenLabs – Speech to Text API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert), [Keyterm prompting](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/batch/keyterm-prompting)
- [Meta – Speech to text API](https://dev.meta.ai/docs/speech-to-text), [Introducing Muse Voice Transcribe](https://research.meta.ai/blog/introducing-muse-voice-transcribe)
- [AssemblyAI – Label speakers (streaming)](https://www.assemblyai.com/docs/streaming/label-speakers-and-separate-channels)
- [BBC – Fall on stony ground bölümü](https://web2.iono.fm/e/1526012)
