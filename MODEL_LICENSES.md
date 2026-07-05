# Model Licenses

AI Interviewer does not bundle model weights inside the EXE or the release
package. The in-app downloader (or `scripts/download_models.ps1`) fetches the
models below into the external `models/` folder next to the app.

## Default TTS Models (Apache-2.0)

All three repositories are published by the Qwen team under the **Apache
License 2.0** (declared on each Hugging Face model card), which permits
commercial use and redistribution. The app pins the following revisions
(`ai_interviewer/model_downloader.py:MODEL_REVISIONS`):

| Repository | Pinned revision | License |
| --- | --- | --- |
| `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | `85e237c12c027371202489a0ec509ded67b5e4b5` | Apache-2.0 |
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `0c0e3051f131929182e2c023b9537f8b1c68adfe` | Apache-2.0 |
| `Qwen/Qwen3-TTS-Tokenizer-12Hz` | `7dd38ad4e9bad454aae9cd937d0cd577604fe229` | Apache-2.0 |

The downloader records the repository, revision, license, and download time in
each model folder's `.download_complete` marker and in `models/model_sources.txt`.
When upgrading models, update `MODEL_REVISIONS`, re-verify the model card
license, and update this table.

## STT Models (MIT)

The optional STT path uses `faster-whisper` (MIT), which downloads
CTranslate2 conversions of OpenAI Whisper models (weights released under the
MIT license) from Hugging Face (`Systran/faster-whisper-*`) on first use.

## Distribution Policy

- Do not commit model weights to this repository.
- Do not place model weights inside the PyInstaller bundle or the release
  ZIP/installer; `scripts/build_release.ps1` fails if `dist\AIInterview\models`
  contains files.
- If a future full-offline package includes model files next to the EXE,
  include the Apache-2.0 license text and the revision metadata above in the
  package.
