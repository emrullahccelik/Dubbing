# Voice Cloning Evaluation: Cloud Models

October 11, 2026 · Emrullah Çelik

A follow-up to the [local evaluation](voice-cloning-local.md). Five larger models that do not fit on a 4 GB card
were tested on a rented GPU with the same clips, the same speaker references and the same metrics. Including an
extra configuration for Qwen3-TTS 1.7B, that makes 6 runs.

| | |
| --- | --- |
| Machine | Vast.ai, RTX 3090 24 GB, about 4.6 CPU cores available to the container, 100 GB disk |
| Time and cost | About 2 hours, about $0.50 (about $0.20 per hour, excluding bandwidth) |
| Models | VoxCPM2, Qwen3-TTS 1.7B, IndexTTS-2.5, Fish Audio S2 Pro, Higgs TTS 3 |
| Jobs | TR → EN (53 lines), EN → TR / DE / FR (16 lines each) |

## Summary

- **VoxCPM2 is the best general option among commercially usable models.** Apache-2.0, and it supports all four
  directions.
  - Highest similarity in TR → EN of any model, local ones included: 0.66, against 0.61 for the original
    recording itself.
  - In EN → TR: WER 3.4%, similarity 0.70.
  - About 2× faster than real time and fits in 6 GB of VRAM.
  - No duration control, though its EN → TR output is already close to the original length (median 1.09).
- **Fish S2 Pro gives the most balanced quality but is not commercially usable.**
  - Among the lowest WER in TR → EN (3.9%).
  - Similarity at the level of the original recording in EN → DE (0.75).
  - 75% of lines within ±15% of the original length.
  - Costs about 20 GB of VRAM and runs 1.6× slower than real time.
- **Higgs TTS 3 is the fastest but only average on similarity.**
  - RTF 0.26–0.28, about 4× faster than real time; the server takes 4–7 minutes to start.
  - Similarity 0.53–0.66.
  - In TR → EN it produced 30 seconds of garbage on one line and replaced short lines with fillers such as
    "Mm-hmm".
- **Qwen3-TTS 1.7B is not clearly better than 0.6B.**
  - Similar in EN → DE (0.74 vs 0.76), lower in EN → FR (0.65 vs 0.79).
  - In TR → EN it prepends the Turkish reference transcript to the English output: WER 32.6%.
  - Using only the speaker embedding (`x_vector_only_mode`) brings WER down to 3.9%, but similarity drops to 0.42.
- **IndexTTS-2.5 does not fit this use.** It supports neither Turkish, German nor French, and fell behind in the
  only direction it could run (TR → EN: WER 12.3%, similarity 0.56).
- **The two main local findings hold for larger models too.** In TR → EN the translation is longer than the
  original (median duration ratio 1.39–1.84 for every model), and lines shorter than a second ("Ugh.", "How?")
  are a problem for everyone. Bigger models do not fix either; they have to be solved in translation and
  segmentation.

## Results

Metrics are the same as in the [local evaluation](voice-cloning-local.md#metrics). The best three local models are
included for comparison; they ran on an RTX 3050 Ti, so their RTF is not directly comparable and is left out.

**VRAM notes:**
- **Fish S2 Pro:** includes the cache the model allocates up front; the real need may be lower.
- **Higgs TTS 3 (\*):** measured with `nvidia-smi`, so it is the memory pre-allocated by the SGLang server. With the
  default allocation ratio (0.85) long lines ran out of memory; at 0.6 the problem went away.

### TR → EN (53 lines)

| Model | WER | Broken | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **VoxCPM2** | 6.2% | 1 | **0.66** | 1.59 | 21% | 0.53 | 5.9 GB |
| **Fish S2 Pro** | **3.9%** | 1 | 0.55 | 1.53 | 11% | 1.64 | 20.2 GB |
| Higgs TTS 3 | 8.3% | 6 | 0.53 | **1.39** | **24%** | **0.28** | 18.3 GB\* |
| Qwen3-TTS 1.7B | 32.6% | 19 | 0.61 | 1.68 | 15% | 1.34 | 4.7 GB |
| Qwen3-TTS 1.7B, embedding only | **3.9%** | 1 | 0.42 | 1.59 | **24%** | 1.34 | 4.3 GB |
| IndexTTS-2.5 | 12.3% | 4 | 0.56 | 1.84 | 11% | 0.80 | 5.8 GB |
| *Local: OmniVoice* | *5.6%* | *1* | *0.61* | *1.65* | *15%* | | *2.3 GB* |
| *Local: Qwen3-TTS 0.6B* | *6.9%* | *2* | *0.61* | *1.55* | *17%* | | *2.8 GB* |
| *Local: CosyVoice3, no transcript* | *4.1%* | *2* | *0.47* | *1.77* | *8%* | | *3.1 GB* |

Original audio: same speaker 0.61, different speaker 0.15.

### EN → TR (16 lines)

Qwen3-TTS and IndexTTS cannot speak Turkish.

| Model | WER | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- |
| **VoxCPM2** | 3.4% | **0.70** | 1.09 | 69% | 0.52 | 5.9 GB |
| **Fish S2 Pro** | 3.7% | 0.68 | 1.10 | **75%** | 1.62 | 20.5 GB |
| Higgs TTS 3 | **3.0%** | 0.65 | 1.18 | 50% | **0.26** | 23.4 GB\* |
| *Local: OmniVoice* | *5.1%* | *0.78* | *1.13* | *69%* | | *2.3 GB* |
| *Local: OmniVoice, duration target* | *4.4%* | *0.75* | *1.02* | *94%* | | *3.0 GB* |
| *Local: Chatterbox V3* | *2.0%* | *0.62* | *1.06* | *56%* | | *3.6 GB* |

Original audio: same speaker 0.75, different speaker 0.13.

### EN → DE (16 lines)

| Model | WER | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- |
| **Fish S2 Pro** | 1.0% | **0.75** | 1.08 | **75%** | 1.65 | 20.5 GB |
| Qwen3-TTS 1.7B | **0.3%** | 0.74 | 1.07 | **75%** | 1.32 | 4.6 GB |
| VoxCPM2 | 0.5% | 0.69 | 1.17 | 50% | 0.52 | 5.9 GB |
| Higgs TTS 3 | 0.5% | 0.66 | 1.19 | 44% | **0.26** | 23.6 GB\* |
| *Local: Qwen3-TTS 0.6B* | *0.3%* | *0.76* | *1.11* | *63%* | | *2.8 GB* |
| *Local: OmniVoice* | *0.5%* | *0.73* | *1.14* | *56%* | | *2.3 GB* |

### EN → FR (16 lines)

| Model | WER | Similarity | Duration | ±15% | RTF | VRAM |
| --- | --- | --- | --- | --- | --- | --- |
| **VoxCPM2** | 1.7% | **0.73** | 1.18 | 44% | 0.52 | 5.9 GB |
| Fish S2 Pro | **0.7%** | 0.71 | 1.10 | **75%** | 1.61 | 20.6 GB |
| Higgs TTS 3 | **0.7%** | 0.66 | 1.16 | 44% | **0.26** | 23.6 GB\* |
| Qwen3-TTS 1.7B | **0.7%** | 0.65 | 1.02 | 63% | 1.32 | 4.6 GB |
| *Local: Qwen3-TTS 0.6B* | *1.7%* | *0.79* | *1.13* | *69%* | | *2.8 GB* |
| *Local: OmniVoice* | *0.7%* | *0.72* | *1.14* | *50%* | | *2.3 GB* |

## Model notes

- **VoxCPM2** (`openbmb/VoxCPM2`, 2.3B)
  - `pip install voxcpm`, no extra setup.
  - Run in "ultimate cloning" mode: the reference is given both as `prompt_wav_path` and `reference_wav_path`,
    together with its transcript.
  - Unlike Qwen and CosyVoice, a Turkish transcript caused no problems, because Turkish is a supported language.
  - 48 kHz output. Run with `cfg_value=2.0` and `inference_timesteps=10`.
- **Fish Audio S2 Pro** (`fishaudio/s2-pro`, 4.6B)
  - Installed from the `fish-speech` repository. `pyaudio` needs `portaudio19-dev` on the system.
  - The repository installs protobuf 5 while tensorboard needs 6.31+; `protobuf>=6.31.1` fixed it.
  - Used through the Python API (`tools.server.model_manager.ModelManager`); the command-line tool reloads the
    model on every call.
  - `torch.compile` was off. It may be faster with it on, at the cost of a long first compile.
- **Higgs TTS 3** (`bosonai/higgs-tts-3-4b`, 4.7B)
  - No Python API; it runs as an SGLang-Omni server (`sgl-omni serve`) and is used over HTTP.
  - **Startup:** the server compiles kernels on first start. With 4–5 CPU cores this took 7 minutes and exceeded
    the default 600 s limit; `SGLANG_OMNI_STARTUP_TIMEOUT=3600` solved it. The second start took 4 minutes.
  - **Memory:** with the default allocation ratio (0.85), four long lines failed with HTTP 500;
    `--mem-fraction-static 0.6` fixed it.
  - **Language:** the API has no language parameter; it infers the language from the text.
- **Qwen3-TTS 1.7B Base** (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`)
  - Same package and code as 0.6B. A Turkish transcript that caused no problems for 0.6B leaks into the output
    of 1.7B.
  - For Turkish sources, a variant that uses only the speaker embedding when the reference language is
    unsupported was added. Pronunciation recovers, but similarity drops.
- **IndexTTS-2.5** (`IndexTeam/IndexTTS-2.5`)
  - Installed from the `index-tts` repository with `uv sync --all-extras`. On first run it downloads helper
    models (w2v-bert, MaskGCT, CAMPPlus, BigVGAN).
  - Supported languages: zh, en, ja, es, ar. `duration_factor` adjusts length but was not used in this test.

## Running on a rented machine

- **CPU limit:** the container reports 24 cores but only about 4.6 are usable. PyTorch opened 24 threads and
  choked (2 lines did not finish in 10 minutes); `OMP_NUM_THREADS=4` fixed it.
- **Downloads:** while the model weights (about 28 GB) were downloading, PyPI and GitHub downloads almost
  stopped. Installation continued once the weights finished; setup took about 25 minutes in total.
- **Disk:** environments and weights used about 83 GB of the 100 GB disk. Less than 100 GB would not have been
  enough.

## Limitations

All limitations of the [local evaluation](voice-cloning-local.md#limitations) apply here too. In addition:

- **Speed:** cloud and local models ran on different GPUs; an RTX 3090 is much more powerful than an RTX 3050 Ti.
- **No tuning:** every model ran with the defaults recommended on its model card, in a single configuration.
  Temperature and CFG were not explored.

## Conclusion

- **Non-commercial use: OmniVoice.** None of the cloud models beat it overall; it also has a duration target and
  runs on a 4 GB card. This is the model the pipeline uses.
- **Commercial use: VoxCPM2.** One model covers all four directions, it is Apache-2.0, and it runs in 6 GB of
  VRAM. Whether it fits on a 4 GB card in bf16/fp16 has not been tested; if not, a small cloud GPU (12 GB class)
  is enough.
