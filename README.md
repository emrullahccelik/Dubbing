# Dubbing

A pipeline that dubs a video or audio recording into another language **in the speakers' own voices**.
Speech is transcribed, translated with its context preserved, and each line is re-voiced with a clone of the
original speaker's voice. The result is placed back into the video together with the background audio, such as
music and laughter.

It can be used from the command line or a web interface, and can also be run with Docker.

## Example

A 2.5-minute BBC Learning English episode (5 speakers), dubbed from English into three languages:

**Original (English)**

https://github.com/user-attachments/assets/27465ca9-900d-493f-8b22-fc0af6801f66

**Turkish dub**

https://github.com/user-attachments/assets/6c9373d7-d54a-4742-8a65-69a980c1c7cb

**German dub**

https://github.com/user-attachments/assets/815d7518-5b10-419c-9426-c24ae0e9ce3f

**French dub**

https://github.com/user-attachments/assets/a43ef6f5-c074-45f5-bcc6-6fdc66cc108a

Audio only: [original_en.mp3](samples/original_en.mp3) · [dub_tr.mp3](samples/dub_tr.mp3) ·
[dub_de.mp3](samples/dub_de.mp3) · [dub_fr.mp3](samples/dub_fr.mp3)

A sample line:

| | |
| --- | --- |
| EN | No, I'm not. I've just been with the rest of the team. We're working on a project, and they're just getting everything wrong. |
| TR | Evet, değilim. Az önce ekibin geri kalanıyla birlikteydim. Bir proje üzerinde çalışıyoruz ve her şeyi yanlış yapıyorlar. |
| DE | Nein, bin ich auch nicht. Ich komme gerade vom Team. Wir arbeiten an einem Projekt, und die machen einfach alles falsch. |
| FR | Non, pas vraiment. Je sors d'une réunion avec le reste de l'équipe. On travaille sur un projet, et ils se trompent sur tout. |

## How it works

```
video / audio
   │
   ├─ 1. ASR ──────────── speech → text, word timestamps, speaker diarization
   ├─ 2. Analysis ─────── topic, tone, speakers and glossary
   ├─ 3. Translation ──── in blocks of 20 lines, with context and glossary
   ├─ 4. Voice cloning ── each line in the original speaker's voice, at its original length
   ├─ 5. Background ───── music, ambience and laughter between lines are separated out
   └─ 6. Mix ──────────── lines are placed on the timeline, mixed with the background, added to the video
```

**1. ASR**: [ElevenLabs Scribe v2](https://elevenlabs.io/speech-to-text) (via OpenRouter). Words are split into
segments at speaker changes, at long pauses, or at the end of a sentence once a segment gets long. Non-speech tags
such as `[laughter]` and `[music]` are removed from the text to be voiced and stored separately with their
timestamps.

**2. Analysis**: The full transcript is sent to the LLM once. The model summarizes what the content is, its tone
and its speakers, and extracts a glossary: proper names, brand and show names, terms, and expressions that must
stay untranslated (for example, an idiom being taught in an English lesson).

**3. Translation**: Segments are translated in blocks of 20 rather than one by one. Each block is sent with the
analysis summary, the glossary, the preceding lines (with their translations) and the following lines, so the
translation stays natural and consistent. Each line's speaking time is included too, and the translation is kept
short enough to be spoken in that time. When the model settles on a translation for a new term, it is added to
the glossary and used in later blocks. The default model is `anthropic/claude-sonnet-5.5`; any model on
OpenRouter can be used instead.

**4. Voice cloning**: [OmniVoice](https://huggingface.co/k2-fsa/OmniVoice). Each line is generated with its
original duration as the target. The reference voice is:
- the line's **own original recording** if it is longer than 3 seconds, so the line's emotion and intonation carry
  over too;
- otherwise the speaker's **shared reference**: about 10 seconds cut from the speaker's longest lines and joined
  together.

**5. Background**: [Demucs](https://github.com/adefossez/demucs) (`htdemucs_ft`) separates the original audio into
speech and everything else. Human sounds such as laughter and applause mostly end up in the speech channel, so
only the parts of the speech channel outside the lines are kept; inside the lines it is muted.

**6. Mix**: Each line is placed at its original start time. If the generated audio fits in the gap before the next
line, it is left as is (short lines are not slowed down); if not, it is sped up just enough to fit, keeping its
pitch. The result is mixed with the background; for a video input, the new audio is muxed in without re-encoding
the picture.

## Project structure

```
dub/
├── asr.py          1. Transcription with ElevenLabs Scribe, segmentation, tag removal
├── translate.py    2–3. LLM client (OpenRouter), analysis and block translation
├── tts.py          4. Reference preparation and voice generation with OmniVoice
├── separate.py     5. Background separation with Demucs
├── mix.py          6. Placement, speed-up, mixing, video muxing
├── pipeline.py     Pipeline class that runs the steps in order, and the command line
├── common.py       Paths, API key, ffmpeg helpers
└── web/
    ├── app.py      FastAPI server: upload, job queue, progress, download
    └── static/     Single-page interface
samples/            Sample audio from this README
data/               Run outputs
Dockerfile, docker-compose.yml, requirements.txt
```

## Setup

Requirements: Python 3.12, an NVIDIA GPU (voice generation uses about 2.3 GB of VRAM and runs on a 4 GB card), and
an [OpenRouter](https://openrouter.ai/keys) API key. ffmpeg does not need to be installed separately; it ships with
the `imageio-ffmpeg` package.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in OPENROUTER_API_KEY
```

Model weights (OmniVoice, Demucs) are downloaded on the first run.

## Usage

### Web interface

```bash
.venv/bin/python -m dub.web            # http://localhost:8000
```

Drag and drop a file, then choose the source language (or automatic detection) and the target language. Progress
is shown for each step separately; when the job is done, the result plays on the page and can be downloaded. The
translation is shown in a table next to the original. Jobs run one at a time on the GPU, and a failed job can be
retried from where it stopped.

### Command line

```bash
.venv/bin/python -m dub.pipeline --input video.mp4 --target tr
.venv/bin/python -m dub.pipeline --input recording.mp3 --source en --target de --llm google/gemini-3.8-flash
```

| Option | Description |
| --- | --- |
| `--target` | Target language (ISO-639-1: `tr`, `en`, `de`, `fr`, `es`, …) |
| `--source` | Source language; detected by ASR if omitted |
| `--llm` | OpenRouter model ID for translation |
| `--batch` | Number of segments translated per request (default 20) |
| `--ref` | `segment` (default) or `speaker`: every line uses the speaker's shared reference |
| `--no-background` | Do not add the original background audio |
| `--until <step>` | Stop after this step (`asr`, `analysis`, `translation`, `tts`, `separation`, `mix`) |
| `--redo <step>` | Rerun this step and all steps after it |
| `--job` | Name of the output folder |

### Docker

The host needs the NVIDIA driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

```bash
docker compose up --build              # http://localhost:8000
```

Outputs are written to `./data` and model weights to the `model-cache` volume. The API key is read from `.env`.

## Outputs

Each job has its own folder: `data/pipeline/<file>_<target language>/` from the command line, `data/web/<id>/` from
the web interface. Each step's result is saved as JSON; a step whose file already exists is read instead of rerun.

| File | Contents |
| --- | --- |
| `01_asr.json` | Segments, words, non-speech sounds |
| `02_analysis.json` | Summary, tone, speakers, glossary |
| `03_translation.json` | Original and translation side by side, final glossary, LLM usage and cost |
| `04_tts.json` | References used, generated audio and duration per segment |
| `05_separation.json` | Separated channels |
| `06_mix.json` | Segment placement and speed-up factors |
| `refs/`, `tts/`, `separation/` | Reference audio, voiced segments, separated channels |
| `final/dub.mp4` · `final/dub.m4a` · `final/dub.wav` | Result: video or audio, plus uncompressed audio |

## Reports

How the components were chosen:

- [ASR evaluation](reports/asr-evaluation.md): 14 speech-to-text models on English and Turkish clips
- [Voice cloning: local models](reports/voice-cloning-local.md): 5 open models on a 4 GB laptop GPU, four directions
- [Voice cloning: cloud models](reports/voice-cloning-cloud.md): 5 larger models on a rented RTX 3090

## Notes

- The OmniVoice weights are licensed for non-commercial use only (CC-BY-NC).
- When the translation is much longer than the source (for example, fast Turkish speech dubbed into English), lines
  may be sped up noticeably.
- Long recordings are sent to ASR in a single request.
