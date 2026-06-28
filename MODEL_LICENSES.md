# Model Licenses

AI Interviewer does not bundle model weights inside the EXE. Users or release
operators must download models into an external `models/` folder and comply with
the upstream model terms.

## Default TTS Models

- `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`
- `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`
- `Qwen/Qwen3-TTS-Tokenizer-12Hz`

Before commercial distribution, verify the current Hugging Face model cards and
Qwen project license terms for the exact model revision being distributed. Record
the model revision or commit hash in the release notes.

## STT Models

The optional STT path uses `faster-whisper`, which downloads or loads Whisper
model variants selected by the user. Users are responsible for using models
whose licenses allow their intended use.

## Distribution Policy

- Do not commit model weights to this repository.
- Do not place model weights inside the PyInstaller bundle.
- If a paid package includes model files next to the EXE, include the upstream
  license files and model revision metadata in the package.
- If models are downloaded by script, document the source repository and target
  local folder.
