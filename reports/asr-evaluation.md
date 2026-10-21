# ASR Evaluation

October 10, 2026 · Emrullah Çelik

The first step of the dubbing pipeline turns speech into text: words, word timestamps and who said what. This
report compares **14 speech-to-text models (15 configurations)** available on OpenRouter on two clips, one
English and one Turkish, and explains why the pipeline uses **ElevenLabs Scribe v2**.

## Summary

- **Chosen model: ElevenLabs Scribe v2.** The most consistent model in both languages. Speaker diarization was
  flawless in English and consistent with the context in Turkish; its word timestamps served as the reference.
- **Backup: Microsoft MAI-Transcribe 2.** Closest to ElevenLabs in Turkish (13.6% text difference, 95.8% speaker
  label agreement) and slightly cheaper, but it mixed up speakers in the English clip.
- **Speaker diarization decided the choice.** Only 5 of the 14 models return speaker labels through OpenRouter:
  ElevenLabs, Grok, Fish Audio, MAI-Transcribe 2 and Deepgram. Without speaker labels, lines cannot be voiced
  with the right voice.
- **Language separated the models clearly.** On the clean English studio recording every commercial model landed
  within 0–0.5% error, so accuracy did not discriminate. On casual Turkish conversation the difference from the
  reference ranged from 13% to 92%.
- **Eliminated:** Whisper large-v3-turbo drops whole phrases in English. In Turkish, Fish Audio's timestamps
  drift by up to 12 seconds, Qwen3-ASR's timestamps are unusable, and Nemotron 0.6B produces largely meaningless
  output (92% difference). Grok is perfect in English but makes obvious errors in Turkish and detects speaker
  changes one word late.

## Test setup

| | English (`test_en`) | Turkish (`test_tr`) |
| --- | --- | --- |
| Source | BBC Learning English, *The English We Speak: Fall on stony ground* | [Rabarba 1638](https://www.youtube.com/watch?v=aGXL_xdwUhU) (Karnaval), 10:00–12:30 |
| Length | 2:34.7 | 2:30.0 |
| Speakers | 5: two presenters and three people in street interviews | 3 men |
| Difficulty | Clean studio recording, orderly turns | Fast, short turns, interruptions, laughter, slang, similar-sounding male voices |
| `language` | not given (auto-detect) | `tr` |

- **Audio:** mono 16 kHz WAV. Deepgram rejected the 4.9 MB WAV, so it received lossless FLAC instead.
- **API:** `POST https://openrouter.ai/api/v1/audio/transcriptions` with base64 audio.
- **Cost:** about $0.22 for both rounds.

### Reference and metrics

There is no verbatim transcript for either clip; BBC's published script leaves out filler words. **ElevenLabs'
output was used as a consensus reference**, and every difference was checked by hand. All percentages below are
therefore *differences from ElevenLabs*, not absolute error rates. Spelling variants ("Fei Fei" / "Feifei",
"programme" / "program") and capitalization were not counted. For Turkish, text was normalized (İ/ı casing,
numbers spelled out: "1500" → "bin beş yüz").

| Metric | Meaning |
| --- | --- |
| WER | Word-level difference from the reference text |
| Speaker agreement | Share of words assigned to the same speaker as in the reference |
| Timestamp difference | Gap between word start times and the reference, mean and 95th percentile |
| Zero-length words | Words whose start and end times are equal (a sign of fabricated timestamps) |

## Models and OpenRouter settings

| Model | OpenRouter ID | Word timestamps | Diarization via OpenRouter |
| --- | --- | --- | --- |
| ElevenLabs Scribe v2 | `elevenlabs/scribe-v2` | ✅ | ✅ `provider.options.elevenlabs.diarize = true` |
| Grok STT 1.0 | `x-ai/grok-stt-1.0` | ✅ | ✅ `provider.options.xai.diarize = true` (the key `x-ai` is silently ignored) |
| Fish Audio Transcribe 1 Pro | `fish-audio/transcribe-1-pro` | ✅ (80 ms steps) | ✅ On by default; speakers appear as `<\|speaker:N\|>` tags inside the text |
| Microsoft MAI-Transcribe 2 | `microsoft/mai-transcribe-2` | ✅ | ✅ `provider.options.azure.diarization = {enabled: true}` |
| Deepgram Nova-3 | `deepgram/nova-3` | ✅ | ✅ `provider.options.deepgram.diarize = true` |
| AssemblyAI Universal-3.5 Pro | `assemblyai/universal-3-5-pro` | ✅ | ❌ `speaker_labels` accepted but not reflected in the output |
| Meta Muse Voice Transcribe 1.0 | `meta/muse-voice-transcribe-1.0` | ❌ | ❌ `mode = DIARIZATION` accepted, but only `text` is returned |
| OpenAI GPT Transcribe | `openai/gpt-transcribe` | ❌ | ❌ |
| Microsoft MAI-Transcribe 1.5 | `microsoft/mai-transcribe-1.5` | ❌ | ❌ |
| Whisper large-v3 | `openai/whisper-large-v3` | ⚠️ depends on the provider | ❌ |
| Whisper large-v3-turbo | `openai/whisper-large-v3-turbo` | ✅ | ❌ |
| Qwen3-ASR 1.7B / 0.6B | `qwen/qwen3-asr-1.7b`, `qwen/qwen3-asr-0.6b` | ✅ (many zero-length words) | ❌ |
| NVIDIA Nemotron 3.5 ASR 0.6B | `nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b` | ✅ | ❌ |

Meta was run twice, with and without `mode = DIARIZATION`. Whisper, Qwen3-ASR and Nemotron are open-weight models;
their hosted versions on OpenRouter were tested.

**Things to know about OpenRouter:**
- Provider-specific parameters go in `provider.options.<provider>.<parameter>`. Some providers (Meta, Azure)
  validate them and return 400 on invalid values; others (AssemblyAI, xAI) silently ignore unknown keys. Every
  parameter was therefore checked for an actual effect on the output.
- `verbose_json` (timestamps) returns 400 on OpenAI GPT Transcribe, Meta and MAI-Transcribe 1.5.
- **The same model can be routed to different providers with different capabilities.** Whisper large-v3 returned
  word timestamps in the English round and only segment timestamps in the Turkish round.
- **Request size limits differ.** Deepgram rejected a 4.9 MB WAV as a "large audio input" but accepted the
  2.6 MB FLAC. AssemblyAI's sync API accepts at most 120 seconds per request, so its audio was split at the
  quietest point; speaker IDs do not match across chunks.
- The upstream timeout is about 60 seconds. Meta took about 46 seconds for a 2.5-minute clip; longer audio needs
  splitting.
- **Latency varies a lot between runs.** Nemotron processed the same English clip in 9.6 seconds in one run and
  121.6 seconds in another.
- Microsoft's listed prices ($0.10 and $0.36) are per hour of audio; this was confirmed on a 3-second clip.
- ElevenLabs' `keyterms` option (custom vocabulary) was not used, so all results show raw model performance.

## English results

| Model | Speakers | WER | Timestamp diff. (mean / p95) | Latency | Per hour |
| --- | --- | --- | --- | --- | --- |
| **ElevenLabs Scribe v2** | ✅ 5/5 | (reference) | (reference) | 7.9 s | $0.11* |
| **Grok STT 1.0** | ✅ 5/5 | 0.26% | 24 / 55 ms | 7.3 s | $0.10 |
| **Fish Audio Transcribe 1 Pro** | ✅ 5/5 | 0.00% | 83 / 180 ms | 9.5 s | $0.36 |
| MAI-Transcribe 2 | ⚠️ 5 IDs, mixed up | 0.00% | 31 / 80 ms | 9.5 s | $0.10 |
| Deepgram Nova-3 | ⚠️ 3 people | 0.26% | 67 / 190 ms | 3.5 s | $0.26 |
| AssemblyAI Universal-3.5 Pro | ❌ | 0.26% | 40 / 102 ms | 5.7 s | $0.45 |
| Whisper large-v3 | ❌ | 1.03% | 30 / 69 ms | 8.9 s | $0.09 |
| MAI-Transcribe 1.5 | ❌ | 0.00% | – | 8.0 s | $0.36 |
| Meta Muse Voice Transcribe | ❌ | 0.26% | – | 44.5 s | $0.18 |
| OpenAI GPT Transcribe | ❌ | 0.52% | – | 8.9 s | $0.27 |
| Qwen3-ASR 1.7B | ❌ | 0.52% | 138 / 480 ms | 11.1 s | $0.027 |
| Qwen3-ASR 0.6B | ❌ | 0.52% | 137 / 480 ms | 10.9 s | $0.012 |
| Nemotron 3.5 ASR 0.6B | ❌ | 1.55% | 196 / 419 ms | 121.6 s | $0.012 |
| Whisper large-v3-turbo | ❌ | **4.90%** | 162 / 430 ms | 8.3 s | $0.012 |

\* The ElevenLabs endpoint is listed on OpenRouter with a 50% discount; without it the price would be about
$0.22 per hour. Hourly prices were calculated from the actual cost measured in this test.

### Text accuracy

| Model | Differences from the reference |
| --- | --- |
| ElevenLabs, Fish, MAI-Transcribe 2, MAI-Transcribe 1.5 | none |
| AssemblyAI, Grok, Deepgram, Meta | dropped "um" |
| OpenAI GPT Transcribe | dropped "um" and a repeated "I" (cleaned-up transcript) |
| Qwen3-ASR 1.7B / 0.6B | "the expression **fall** on stony ground" → "for"; dropped "um" |
| Whisper large-v3 | "fall" → "for"; an extra "ground"; dropped "um" and "I" |
| Nemotron | "Feifei" → "Feife", "pay cut" → "paycup", "fall" → "for"; dropped "um" and "I" |
| Whisper large-v3-turbo | **Dropped "That fell on stony ground. He" and "We hope that this program is fertile ground for your" entirely**; "fall" → "for"; an extra "and". Same result in two separate runs |

The commercial models agree word for word, so accuracy does not separate them on this clip. For dubbing, models
that keep filler words (ElevenLabs, Fish, MAI-Transcribe 2) are better, because the speaker's rhythm and the
segment length are reflected more accurately. Whisper-turbo's dropped phrases would mean lost content in the dub.

### Speaker diarization

Correct split: the two presenters and three separate interviewees.

| Model | Found | Agreement with ElevenLabs | Details |
| --- | --- | --- | --- |
| ElevenLabs | 5 | (reference) | ✅ Every turn correct |
| Grok | 5 | 100% | ✅ Every turn correct |
| Fish Audio | 5 | 100% | ✅ Turns correct; one word moved 3.6 s early |
| MAI-Transcribe 2 | 5 IDs | 88.4% | ❌ One presenter split into two IDs; one interviewee merged with that presenter's second ID |
| Deepgram Nova-3 | 3 | 89.6% | ❌ The first interviewee taken for a presenter; the other two interviewees merged into one person |

Without speaker labels, lines from different people end up in one segment. In AssemblyAI's output, one presenter's
"Like your ideas, Phil." and the other presenter's reply "Don't remind me..." fell into the same segment, which
in the cloning step means voicing a line with the wrong voice.

### Word timestamps

Start-time difference from ElevenLabs:

| Model | Mean | p95 | Zero-length words |
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

ElevenLabs, Grok, MAI-Transcribe 2 and Whisper large-v3 agree within about 30 ms, which is reliable enough for
cutting audio. About 13% of Qwen's words have zero length.

## Turkish results

Without a verbatim transcript, Turkish was evaluated in two ways: agreement between models, and reading the
places where they disagree for grammar and context.

| Model | Speakers | Difference from ElevenLabs | Timestamp diff. (mean / p95) | Zero-length words | Latency | Per hour |
| --- | --- | --- | --- | --- | --- | --- |
| **ElevenLabs Scribe v2** | ✅ 3 | (reference) | (reference) | 5 / 387 | 11.4 s | $0.11 |
| **MAI-Transcribe 2** | ✅ 3 | **13.6%** | 32 / 90 ms | 0 / 391 | 8.3 s | $0.10 |
| Grok STT 1.0 | ⚠️ 3 | 15.2% | 29 / 61 ms | 0 / 371 | 7.2 s | $0.10 |
| MAI-Transcribe 1.5 | ❌ | 17.3% | – | – | 7.6 s | $0.36 |
| Meta Muse Voice (DIARIZATION) | ❌ | 18.6% | – | – | 47.2 s | $0.18 |
| OpenAI GPT Transcribe | ❌ | 19.4% | – | – | 9.6 s | $0.27 |
| Meta Muse Voice | ❌ | 20.2% | – | – | 46.3 s | $0.18 |
| Deepgram Nova-3 | ❌ 2 people | 21.5% | 80 / 211 ms | 0 | 4.3 s | $0.26 |
| Whisper large-v3-turbo | ❌ | 22.3% | 118 / 403 ms | 7 | 6.8 s | $0.012 |
| Whisper large-v3 | ❌ | 23.0% | segments only | – | 7.0 s | $0.09 |
| AssemblyAI Universal-3.5 Pro | ❌ | 23.8% | 593 / 2109 ms | 0 | 6.7 s | $0.45 |
| Qwen3-ASR 1.7B | ❌ | 26.7% | 531 / 2632 ms | 143 | 14.6 s | $0.027 |
| Fish Audio Transcribe 1 Pro | ⚠️ 3 | 33.5% | **11659 / 41042 ms** | **242 / 394** | 11.3 s | $0.36 |
| Qwen3-ASR 0.6B | ❌ | 36.1% | 549 / 3200 ms | 138 | 7.2 s | $0.012 |
| Nemotron 3.5 ASR 0.6B | ❌ | **92.2%** | 919 / 933 ms | 0 | 8.6 s | $0.012 |

Pairwise text differences: ElevenLabs ↔ MAI-Transcribe 2 13.6%, ElevenLabs ↔ Grok 15.2%, Grok ↔ MAI-Transcribe 2
19.2%. These three form a cluster; every other model differs from all three by more than 25%.

### Speaker diarization

The speaker identities were verified from the content (one speaker asks another by name how work is going, and
the named person answers).

| Model | Found | Agreement with ElevenLabs | Details |
| --- | --- | --- | --- |
| ElevenLabs | 3 | (reference) | ✅ No turn contradicts the context. 25 / 16 / 12 turns |
| MAI-Transcribe 2 | 3 | **95.8%** | ✅ Almost identical; a few short turns assigned differently |
| Grok | 3 | 95.1% | ⚠️ Turns go to the right people, but **speaker changes are usually detected one word late**: the first word of a turn is attributed to the previous speaker |
| Deepgram Nova-3 | 2 | 78.8% | ❌ Three people reduced to two |
| Fish Audio | 3 | 72.9% | ❌ Finds three people, but drifting timestamps put segments in the wrong place in the audio |

Grok's one-word delay matters for dubbing: the first word of a segment would be voiced with the wrong speaker's
voice.

### Text accuracy

The places where the top three disagree, read in context:

| Time | ElevenLabs | MAI-Transcribe 2 | Grok | Verdict |
| --- | --- | --- | --- | --- |
| 00:00 | tuvalet eğitimi (potty training) | tuvalet eğitimi | **tuvalete gittim** (I went to the toilet) | Grok wrong |
| 00:06 | sokaklara işemekten | yeter ya sokakları | sokakları | ElevenLabs grammatically correct |
| 00:25 | aracın | aracın | **araçın** | Grok misspelled |
| 00:35 | **söyleyemeyeceğim** | söyleyemeyelim | söyleyemeyelim | The other two agree; ElevenLabs wrong |
| 00:54 | bir daha **bineceksin** | bir daha yapacaksın | bir daha yapacaksın | The other two agree; ElevenLabs wrong |
| 01:07 | onayladınız (you agreed) | onayladınız | **ona eğlenirsin** | Grok wrong |
| 01:27 | aranda | **adamda** | **oranda** | ElevenLabs correct ("the gap to the car ahead") |
| 01:52 | iş hayatın nasıl (how's work) | şoförlüğün nasıl (how's driving) | **senin kaç golünüz** (how many goals) | Grok unrelated; the context (an answer about road trips) supports MAI-Transcribe 2 |
| 01:57 | **de işinden** | deyişinden | şahsen | MAI-Transcribe 2 correct |
| 02:04 | çok dediğin | çok dediğin | **derin** | Grok wrong |

- **Grok has obvious errors and dropped phrases**; it is one of the three weakest models for Turkish.
- **ElevenLabs and MAI-Transcribe 2 are close, and both make mistakes.** In this run ElevenLabs missed three
  places where the other two agreed on the correct word.
- **MAI-Transcribe 2 catches more interruptions** ("Hayır, bir dakika", "yeter ya"); some of these may be
  overlapping speech.
- **Output changes slightly between runs.** ElevenLabs spelled one word correctly in one run and incorrectly in
  another, so small differences should not be judged from a single run.

## Decision

1. **Primary ASR: ElevenLabs Scribe v2** with word timestamps and `diarize = true`.
2. **Backup: Microsoft MAI-Transcribe 2** with diarization enabled. Running both on important jobs and flagging
   where speakers or text disagree would be a cheap quality check (about $0.21 per hour for both).
3. **Segmentation:** split words at a speaker change, at a pause longer than 0.8 seconds, or at the end of a
   sentence once a segment exceeds 15 seconds. Each segment goes to voice cloning with its speaker ID.
4. **Open-weight option:** Whisper large-v3 is good in English but has no diarization, so it would need a separate
   diarization model such as pyannote. None of the open-weight models is good enough in Turkish.

## Limitations

- **One run per clip.** Latency and small text differences vary between runs.
- **No verbatim transcript.** All rates are differences from ElevenLabs, not absolute errors. Exact WER and
  diarization error rate (DER) would need a hand-made transcript of the Turkish clip.
- **Untested conditions:** background music or noise (film and TV scenes), Turkish content with mixed male and
  female voices, overlapping speech, and audio longer than 5 minutes.
- **`keyterms` was not used.** On content dense with proper names it could change the results.
- AssemblyAI and Meta offer diarization in their own APIs; only their OpenRouter routes lack it.

## References

- [OpenRouter: Transcription on OpenRouter](https://openrouter.ai/blog/tutorials/transcription-on-openrouter/)
- Model pages on OpenRouter: [ElevenLabs Scribe v2](https://openrouter.ai/elevenlabs/scribe-v2),
  [OpenAI GPT Transcribe](https://openrouter.ai/openai/gpt-transcribe),
  [Fish Audio Transcribe 1 Pro](https://openrouter.ai/fish-audio/transcribe-1-pro),
  [AssemblyAI Universal-3.5 Pro](https://openrouter.ai/assemblyai/universal-3-5-pro),
  [Meta Muse Voice Transcribe 1.0](https://openrouter.ai/meta/muse-voice-transcribe-1.0),
  [Grok STT 1.0](https://openrouter.ai/x-ai/grok-stt-1.0), [Deepgram Nova-3](https://openrouter.ai/deepgram/nova-3),
  [MAI-Transcribe 2](https://openrouter.ai/microsoft/mai-transcribe-2),
  [MAI-Transcribe 1.5](https://openrouter.ai/microsoft/mai-transcribe-1.5),
  [Nemotron 3.5 ASR 0.6B](https://openrouter.ai/nvidia/nemotron-3.5-asr-streaming-multilingual-0.6b),
  [Qwen3-ASR 1.7B](https://openrouter.ai/qwen/qwen3-asr-1.7b), [Qwen3-ASR 0.6B](https://openrouter.ai/qwen/qwen3-asr-0.6b),
  [Whisper large-v3](https://openrouter.ai/openai/whisper-large-v3),
  [Whisper large-v3-turbo](https://openrouter.ai/openai/whisper-large-v3-turbo)
- [ElevenLabs: Speech to Text API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert),
  [Keyterm prompting](https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-to-text/batch/keyterm-prompting)
- [Meta: Speech to text API](https://dev.meta.ai/docs/speech-to-text)
- [AssemblyAI: Label speakers](https://www.assemblyai.com/docs/streaming/label-speakers-and-separate-channels)
- [BBC: Fall on stony ground](https://web2.iono.fm/e/1526012)
