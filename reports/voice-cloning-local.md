# Voice Cloning Evaluation: Local Models

October 11, 2026 · Emrullah Çelik

The voice cloning step re-voices each translated line in the original speaker's voice. This report compares
**5 open models (7 configurations)** that fit on a laptop GPU (RTX 3050 Ti, 4 GB VRAM) in four directions, and
explains why the pipeline uses **OmniVoice with a duration target**. Models too large for this card are covered
in the [cloud evaluation](voice-cloning-cloud.md).

## Summary

- **Best overall: OmniVoice.** Speaker similarity matches the level of the original recording in every direction
  (0.61 in TR → EN, the same as the original audio itself). It degrades least on very short lines, uses the least
  VRAM (2.3 GB), and its **duration target**, which matters most for dubbing, works on its own. Its weights are
  licensed for non-commercial use only (CC-BY-NC).
- **Best commercially usable option depends on the language:**
  - Without Turkish, **Qwen3-TTS 0.6B** (Apache-2.0): highest similarity in German and French (0.76–0.79), close
    to OmniVoice in TR → EN. It is the slowest model (2.2–2.8× slower than real time) and cannot speak Turkish.
  - With Turkish, **Chatterbox Multilingual V3** (MIT): lowest WER in EN → TR (2.0%), but lower similarity
    (0.54–0.67), and it repeats or invents words on one-word lines. It adds an inaudible watermark to its output.
- **XTTS-v2, the older baseline, falls behind.** Fastest model with correct pronunciation, but the lowest
  similarity (0.45–0.54); a good measure of how far newer models have come.
- **CosyVoice3** gives good similarity in German and French (0.70–0.74) but makes speech 30–35% longer than the
  original and was the hardest to install.
- **Duration is the real bottleneck, not the model.** In TR → EN, every model's English audio is **55–100% longer**
  than the original Turkish line: Turkish speakers are fast and the translations are long. Forcing OmniVoice to
  fit makes speech unintelligible (WER 5.6% → 15%). From English into German, French and Turkish the duration
  target works without side effects: 94–100% of lines land within ±15% of the original length and WER does not
  rise.
- **Lines shorter than one second are a problem for every model** ("Right?", "Ugh.", "Next week."). Chatterbox and
  XTTS stretch them 5–18× and add repetitions.

## Test setup

| Direction | Source | Lines | Speakers | Notes |
| --- | --- | --- | --- | --- |
| TR → EN | Turkish comedy podcast clip, 2:30 | 53 | 3 | Fast, short turns, laughter, interruptions; lines as short as 0.6 s |
| EN → TR | BBC Learning English episode, 2:35 | 16 | 5 | Clean studio recording; 3 speakers have a single line |
| EN → DE | Same English episode | 16 | 5 | Translation written by hand for this test |
| EN → FR | Same English episode | 16 | 5 | Translation written by hand for this test |

The source clips are the same ones used in the [ASR evaluation](asr-evaluation.md); transcripts and speaker
labels come from ElevenLabs Scribe v2.

- **Speaker references:** for each speaker, their longest lines were cut from the original audio and joined
  (about 10 seconds, at most 14) together with their transcript. Every line of that speaker was voiced from the
  same reference.
- **Placement:** generated lines were placed at their original start times; overlaps were not resolved.

### Metrics

| Metric | How it was measured | Good value |
| --- | --- | --- |
| WER | All generated lines were transcribed again with ElevenLabs Scribe v2 in the target language and compared with the translation | Low |
| Broken lines | Lines with WER above 50% (skipped, repeated or invented words) | 0 |
| Similarity | Cosine similarity of ECAPA-TDNN speaker embeddings between each generated line and the speaker's reference | High; the "original audio" value under each table is a practical ceiling |
| Duration ratio | Generated length / original line length (median) | 1.00 |
| ±15% | Share of lines within ±15% of the original length | High |
| RTF | Generation time / generated audio length; below 1 is faster than real time | Low |
| VRAM | Peak GPU memory during generation (PyTorch) | Low |

## Results

### TR → EN (53 lines)

| Model | WER | Broken | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OmniVoice** | 5.6% | 1 | **0.61** | 1.65 | 15% | 1.54 | **2.3 GB** |
| OmniVoice (duration target) | 15.0% | 5 | **0.63** | **1.08** | **62%** | 1.95 | 3.0 GB |
| Qwen3-TTS 0.6B | 6.9% | 2 | **0.61** | 1.55 | 17% | 2.42 | 2.8 GB |
| Chatterbox V3 | 8.5% | 9 | 0.54 | 1.64 | 17% | 1.39 | 3.1 GB |
| Chatterbox V3 (`cfg_weight=0`) | 10.4% | 7 | 0.58 | 2.02 | 4% | 1.50 | 3.4 GB |
| CosyVoice3 (no transcript) | **4.1%** | 2 | 0.47 | 1.77 | 8% | 1.30 | 3.1 GB |
| XTTS-v2 | 6.7% | 3 | 0.45 | 1.99 | 8% | **0.55** | **2.0 GB** |

Original audio: same speaker 0.61, different speaker 0.15 (30 lines). CosyVoice3 with the reference transcript:
WER 21.7%, similarity 0.64. It has to choose between good similarity with broken output and clean pronunciation
with low similarity.

### EN → TR (16 lines)

Qwen3-TTS and CosyVoice3 do not support Turkish.

| Model | WER | Broken | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OmniVoice** | 5.1% | 0 | **0.78** | 1.13 | 69% | 0.77 | 2.3 GB |
| OmniVoice (duration target) | 4.4% | 0 | **0.75** | **1.02** | **94%** | 0.80 | 3.0 GB |
| Chatterbox V3 | **2.0%** | 0 | 0.62 | 1.06 | 56% | 1.36 | 3.6 GB |
| Chatterbox V3 (`cfg_weight=0`) | 2.4% | 0 | 0.66 | 1.24 | 25% | 1.41 | 3.6 GB |
| XTTS-v2 | 3.0% | 0 | 0.47 | 1.08 | 50% | **0.58** | **2.1 GB** |

Original audio: same speaker 0.75, different speaker 0.13 (11 lines). Part of OmniVoice's WER comes from a single
line where one word was changed.

### EN → DE (16 lines)

| Model | WER | Broken | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OmniVoice | 0.5% | 0 | 0.73 | 1.14 | 56% | 0.74 | 2.3 GB |
| OmniVoice (duration target) | 0.3% | 0 | 0.72 | **1.02** | **100%** | 0.81 | 3.0 GB |
| **Qwen3-TTS 0.6B** | 0.3% | 0 | **0.76** | 1.11 | 62% | 2.81 | 2.8 GB |
| Chatterbox V3 | 0.3% | 0 | 0.67 | 1.03 | 69% | 1.41 | 3.6 GB |
| Chatterbox V3 (`cfg_weight=0`) | 0.8% | 0 | 0.70 | 1.21 | 38% | 1.35 | 3.7 GB |
| CosyVoice3 | 2.6% | 0 | 0.74 | 1.30 | 25% | 1.03 | 3.2 GB |
| XTTS-v2 | 0.3% | 0 | 0.54 | 1.20 | 44% | **0.59** | **2.0 GB** |

### EN → FR (16 lines)

| Model | WER | Broken | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OmniVoice | 0.7% | 0 | 0.72 | 1.14 | 50% | 0.77 | 2.3 GB |
| OmniVoice (duration target) | 0.2% | 0 | 0.73 | **1.02** | **94%** | 0.83 | 3.0 GB |
| **Qwen3-TTS 0.6B** | 1.7% | 0 | **0.79** | 1.12 | 69% | 2.21 | 2.8 GB |
| Chatterbox V3 | 0.7% | 0 | 0.64 | 1.02 | 75% | 1.39 | 3.6 GB |
| Chatterbox V3 (`cfg_weight=0`) | 0.7% | 0 | 0.66 | 1.26 | 44% | 1.37 | 3.7 GB |
| CosyVoice3 | 2.0% | 0 | 0.70 | 1.35 | 25% | 1.02 | 3.2 GB |
| XTTS-v2 | 0.5% | 0 | 0.50 | 1.07 | 50% | **0.60** | **2.1 GB** |

For German and French the original-audio values are the same as for EN → TR (0.75 / 0.13).

## Model notes

- **OmniVoice** (`k2-fsa/OmniVoice`, 0.6B). `pip install omnivoice`, no extra setup. With the `duration` parameter
  the output lands on the requested length. With an English source it works without quality loss. With a Turkish
  source the translation is much longer than the original, so fitting speeds speech up until it breaks; the
  shortest lines (a question squeezed into 0.28 s) even came out silent. The duration target should be used when
  the line length reasonably fits the text.
- **Qwen3-TTS 0.6B Base** (`Qwen/Qwen3-TTS-12Hz-0.6B-Base`). `pip install qwen-tts`. Clones from reference audio
  plus transcript; a Turkish transcript is not officially supported but caused no problems (only two small
  stutters). Without flash-attn on this card it runs 2–3× slower than real time.
- **Chatterbox Multilingual V3** (`ResembleAI/chatterbox`, 0.5B). The PyPI release (0.1.7) loads the V2 weights;
  for V3 the package was installed from GitHub with `t3_model="v3"`. In the default fp32 the peak VRAM is 4.5 GB,
  which spills into system RAM on a 4 GB card and makes it **45× slower**; with the language model in bf16 the
  peak drops to 3.1–3.6 GB. The watermark package (`perth`) needs `setuptools<81`. The model card's recommended
  `cfg_weight=0` for cross-lingual use raised similarity slightly (+0.02–0.04) but slowed speech down (duration
  ratio 1.2–2.0).
- **CosyVoice3** (`FunAudioLLM/Fun-CosyVoice3-0.5B-2512`). No pip package; installed from the GitHub repository
  with hand-picked dependencies (Python 3.10, PyTorch 2.3.1, without TensorRT, DeepSpeed and Gradio). `fp16=True`
  only computes in half precision while the weights stay in fp32: the peak was 4.3 GB and each line took about
  110 s. With the LLM converted to fp16 the peak dropped to 3.1 GB and generation became about 30× faster. The
  repository downloads 11.8 GB.
- **XTTS-v2** (`coqui/XTTS-v2`). The `coqui-tts` package does not install PyTorch itself; it needs
  `torch==2.8.0`, `transformers<5` and `spacy` for splitting long text. License acceptance via
  `COQUI_TOS_AGREED=1` (CPML, non-commercial).

## Limitations

- **One run.** All models sample during generation, so the same line can come out differently. Models a few
  points apart cannot be ranked reliably.
- **The similarity metric is language-sensitive.** ECAPA embeddings score the same speaker slightly lower across
  languages. The original-audio value is measured within one language, so a cross-lingual score equal to it is a
  very good result.
- **References come from the clip being dubbed.** Some speakers (three in the English clip) have only one line,
  so their reference is the very line being dubbed. This is also the case in real use, but those speakers were
  left out of the original-audio comparison.
- **Part of the WER comes from ASR.** In TR → EN, numbers like "eighty-five thousand two hundred" are written as
  digits by ASR, which raises every model's WER equally. English idioms kept inside the Turkish, German and French
  translations ("fell on stony ground") are harder to pronounce.
- **Hand-written translations.** The German and French translations were written for this test.
- **Measurements give a rough ranking.** Naturalness, emotion and accent need listening.

## What the pipeline adopted

- **OmniVoice with a duration target**, since it was the best overall and fits on a 4 GB card.
- **Translations are given the speaking time of each line**, so the duration target does not have to compress
  speech the way it did in TR → EN.
- **Lines that still do not fit are sped up only into the silence after them**, instead of overlapping the next
  line.
- **Each line longer than 3 seconds uses its own original recording as the reference**, so its emotion and
  intonation carry over; shorter lines use the speaker's shared reference. This was added after these
  measurements and was judged by listening.
