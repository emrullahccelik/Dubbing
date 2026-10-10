# Dublaj Hattı - Açık ve Kapalı Kaynak Modeller

Oct 10, 2026 · @Emrullah Çelik

Ses tonunu koruyan dublaj hattı için model seçenekleri. Hat akışı: **ASR (sesi metne çevir) → çeviri → ses klonlama (çevrilen metni orijinal konuşmacının sesiyle seslendir)**. Her ses parçası, kendi konuşmacı kaydı ve metniyle birlikte klonlama modeline verilir; bu sayede ayrı bir konuşmacı ayrıştırma adımına gerek kalmaz.

## 1. Konuşmadan Metne (ASR)

### Açık kaynak: parametre sayısı ve GPU gereksinimi

| Model | Parametre | VRAM | Not |
| --- | --- | --- | --- |
| Whisper large-v3 | 1.55 milyar | \~3 GB (FP16); tam pipeline ile \~10 GB | 99 dil, Apache 2.0, en dengeli seçenek |
| Whisper large-v3-turbo | \~809 milyon | \~6 GB | Decoder 32 → 4 katman, belirgin şekilde daha hızlı |
| Faster-whisper (large) | 1.55 milyar | \~2.9 GB (int8) / \~4.5 GB (fp16) | Aynı model, optimize çalışma zamanı; 8 GB kart yeterli |
| Qwen3-ASR | 0.6B ve 1.7B | \~2-4 GB | Yeni; ekosistem henüz olgunlaşıyor |
| NVIDIA Canary-Qwen | 2.5 milyar | \~6-8 GB (tahmini) | İngilizce doğrulukta lider |
| NVIDIA Parakeet TDT | \~0.6 milyar | \~2-4 GB (tahmini) | Çok hızlı ama ağırlıklı olarak İngilizce |

**Önerilen minimum GPU:** RTX 3060 (12 GB). **Rahat:** RTX 4090 (24 GB).

### Kapalı kaynak: tahmini maliyet

| Servis | Tahmini maliyet | Not |
| --- | --- | --- |
| ElevenLabs Scribe | \~$0.22 / saat'ten başlıyor | ElevenLabs ekosistemiyle uyumlu |
| Deepgram | Saat başı, kullanıma göre | Hızlı, API odaklı |
| AssemblyAI | Ücretsiz başlangıç kredisi, sonra saat başı | Kolay entegrasyon |
| Google Cloud / Azure / Amazon Transcribe | Dakika/saat başı, kademeli | Ücretsiz katman mevcut |

> Deepgram, AssemblyAI, Google, Azure ve Amazon fiyatları plana ve hacme göre değişir; güncel rakamı kendi sitelerinden doğrulamak gerekir.

## 2. Ses Klonlama (Metinden Sese)

### Açık kaynak: parametre sayısı ve GPU gereksinimi

| Model | Parametre | Referans ses | VRAM | Lisans / Not |
| --- | --- | --- | --- | --- |
| XTTS v2 (Coqui) | \~470 milyon (ağırlık 1.88 GB, FP32) | 6 saniye | 3-4 GB (FP16); 6 GB rahat | Ticari kullanımda lisans kısıtlı (CPML); Türkçe destekli |
| Qwen3-TTS | 0.6B ve 1.7B | \~3 saniye | \~4 GB (1.7B, bf16) | Apache 2.0, ticari kullanım serbest |
| IndexTTS-2 | \~1.5 milyar (tahmini) | Referans + stil kontrolü | \~8 GB (tahmini) | Süre kontrolü var, dublaj senkronu için uygun |
| Fish Speech V1.5 | \~500 milyon (tahmini) | Kısa referans | \~4 GB (tahmini) | Çok dilli, verimli |
| CosyVoice2 | 0.5 milyar | Kısa referans | \~3-4 GB (tahmini) | Hafif, zero-shot |
| F5-TTS | \~336 milyon | Kısa referans | \~3 GB | Kaynak açısından en verimlilerden |

### Kapalı kaynak: tahmini maliyet

| Servis | Dakika başı | 10 dakikalık video |
| --- | --- | --- |
| ElevenLabs Dublaj v1 (otomatik, filigranlı) | \~$0.33 | \~$3.30 |
| ElevenLabs Dublaj v1 (otomatik, filigransız) | \~$0.50 | \~$5.00 |
| ElevenLabs Dubbing Studio | \~$0.50 | \~$5.00 |
| ElevenLabs Dublaj v2 (otomatik ses klonlama) | \~$2.20 | \~$22.00 |
| ElevenLabs TTS (Multilingual, karakter başı) | \~$0.10 / 1.000 karakter | Metin uzunluğuna bağlı |

> Maliyetler her hedef dil için ayrı hesaplanır: 10 dakikalık bir videoyu 3 dile dublajlamak, v2'de \~$66 tutar.

## 3. Açık Kaynak Hat İçin Toplam GPU Tahmini

| Kurulum | Toplam VRAM | Önerilen GPU |
| --- | --- | --- |
| Faster-whisper (int8) + XTTS v2 | \~7-8 GB | RTX 4060 / 3060 12 GB |
| Whisper large-v3 + Qwen3-TTS 1.7B | \~8-14 GB | RTX 4070 Ti / 4080 |
| Whisper + IndexTTS-2 + yerel çeviri LLM'i (8B) | \~20-24 GB | RTX 4090 24 GB |

Modeller sırayla (ASR bittikten sonra TTS) çalıştırılırsa VRAM ihtiyacı en büyük modelin ihtiyacına düşer.

## 4. Önerilen Hat

1. **Whisper large-v3 / faster-whisper** ile sesi zaman damgalı segmentlere ve metne çevir.
2. Bir çeviri modeli (LLM ya da çeviri API'si) ile metni hedef dile çevir.
3. Her segmentin orijinal ses kaydını referans olarak kullanıp **Qwen3-TTS** (ticari serbest) ya da **XTTS v2** (köklü, ama lisans dikkat) ile seslendir.
4. Üretilen segmentleri zaman damgalarına göre videoya yerleştir; süre farkı varsa hızlandır/yavaşlat ya da süre kontrolü olan modeli (IndexTTS-2) kullan.

> "(tahmini)" ile işaretli değerler resmi kaynakta net olarak doğrulanamamıştır; kurulum öncesi model sayfasından kontrol edilmelidir.
