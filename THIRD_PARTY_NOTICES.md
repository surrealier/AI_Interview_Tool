# Third-Party Notices

AI Interviewer uses optional third-party packages depending on the selected
runtime profile.

## Core

- Python standard library
- Tkinter
- PyInstaller for Windows packaging

## Qwen TTS Profile

- `qwen-tts`
- `torch`
- `soundfile`
- `huggingface-hub`

## Interactive Profile

- `opencv-python`
- `Pillow`
- `sounddevice`
- `numpy`
- `faster-whisper`

Each dependency is governed by its own license. Before a commercial release,
generate and archive a dependency license report for the exact lockfile or build
environment used to create the release artifact.

Model weights are not covered by this notice. See `MODEL_LICENSES.md`.
