# Optional local engines

**No model is needed or installed by Koma Studio.** The System & models page distinguishes an executable or loopback service being detected from a model being usable. Nothing in this release sends a story to these engines. No voices or checkpoints appear as working choices.

| Engine | What is checked now | Requirements to evaluate in a later phase |
|---|---|---|
| [Ollama](https://github.com/ollama/ollama) (runtime: MIT) | Detects its executable or version response on `127.0.0.1:11434`. | Start with the no-model story planner. If trying a small quantized text model later, select a model with a documented license and measure memory and inference time. Use only local weights; explicitly [disable Ollama cloud features](https://github.com/ollama/ollama/blob/main/docs/faq.mdx#how-do-i-disable-ollamas-cloud-features). |
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI) (runtime: GPL-3.0) | Detects the `/system_stats` response on `127.0.0.1:8188`. | Prefer imported illustrations on CPU. If evaluating a lightweight SD 1.5-compatible checkpoint, review its individual license, check disk and RAM, and benchmark one low-resolution sample. A responding server does not prove a GPU backend or model is usable. Use an offline build/configuration and vetted workflows, not remote or partner nodes. |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) (runtime: GPL-3.0) | Detects a Piper executable on `PATH`. It does not enumerate usable voices. | Test a small installed voice offline and check the voice-specific license and locale. English/Hindi/Bengali are saved narration preferences, not a claim that a voice exists. Imported or recorded speech is the planned alternative. |

Runtime and model licenses are separate. Record source URL, exact revision or filename, model-specific license, disk size, and observed RAM/runtime before adding a checkpoint or voice to a supported list. Do not install an image model or switch to GPU acceleration based on the adapter name alone.

Koma Studio uses a built-in rule-based planner and imports local stills. Milestone 1 animates those kinds of prepared layers without inference. It invokes your local FFmpeg/FFprobe installation only for MP4 export; see the [setup instructions](../README.md#ffmpeg-setup-for-export). No voice engine, model download, or external media provider is shipped.
