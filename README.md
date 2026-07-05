# AI Interviewer

AI Interviewer is an offline-first Windows desktop app for interview practice.
Paste or load a question list, let the app read each question aloud, record and
transcribe answers, generate follow-up questions, and export session records to
CSV/JSON. The UI supports Korean and English (switchable in-app).

Current release target: `v1.0.0-rc1` (version source of truth:
`ai_interviewer/__init__.py`).

## Beta Scope

- Windows 10/11 single-user desktop app.
- Korean and English default HR question set.
- Step-by-step setup wizard for language, TTS model, speaker, interview type, question source, sound test, and preferences.
- Question prefix cleanup such as `1.`, `1)`, `1.2.`, `Q1.`.
- Qwen3-TTS first, Windows SAPI optional fallback.
- Interviewer video panel with built-in animated fallback.
- Optional microphone recording, faster-whisper STT, and follow-up question generation.
- Local session export with timestamps, TTS backend, quality flag, transcript, memo, answer audio path, and follow-up question.
- Runtime diagnostics and local support logs.

## Quick Start

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-interactive.txt
python -m pip install -r requirements-qwen.txt
python -m ai_interviewer
```

If you already use a CUDA-ready conda environment, use that environment instead
of creating `.venv`.

```cmd
conda activate torch251
cd /d C:\bongkj\Projects\AI_Interview
python -m pip install -r requirements.txt
python -m pip install -r requirements-qwen.txt
pythonw -m ai_interviewer
```

## Models

Model weights are not committed and are not bundled inside the EXE or release
packages. The default model folder is `models/` next to the project or packaged
app. **End users download models inside the app** (setup wizard model step or
설정 → 미디어 → 모델 다운로드) with progress, cancel, and resume; revisions are
pinned and recorded (see `MODEL_LICENSES.md`, Apache-2.0).

For development environments the script also works:

```powershell
.\scripts\download_models.ps1 -Size 0.6B
```

For stronger interviewer tone control:

```powershell
.\scripts\download_models.ps1 -Size 1.7B
```

Expected layout:

```text
models/
  Qwen3-TTS-Tokenizer-12Hz/
  Qwen3-TTS-12Hz-0.6B-CustomVoice/
```

## Runtime Diagnostics

Inside the app, press `런타임 진단`.

From a terminal:

```powershell
python -m ai_interviewer.release_check --strict
```

Windows SAPI fallback is off by default. If Qwen fails, the app shows an error
unless the fallback checkbox is explicitly enabled.

Qwen model weights are not loaded when the app opens. The selected model is
loaded only when you run the setup sound test or start the interview. The
device is selected automatically: CUDA when available, otherwise CPU (slower,
with a visible CPU-mode notice).

## Local Data

Sessions:

```text
%USERPROFILE%\Documents\AIInterview\sessions\<session_id>\
```

Settings and logs:

```text
%APPDATA%\AIInterview\config.json
%APPDATA%\AIInterview\logs\app.log
```

Session folders may contain voice recordings, transcripts, notes, and other
personal data. See `PRIVACY.md`.

## Build Release

```powershell
.\scripts\build_release.ps1 -Python python   # installer + ZIP
.\scripts\smoke_test_dist.ps1                # packaged smoke check
```

The script cleans `dist\`, generates the EXE version resource, runs
PyInstaller, copies customer documents, compiles the Inno Setup installer
(`AIInterview-Setup-<version>.exe`; requires Inno Setup 6, or pass
`-SkipInstaller`), and writes a portable ZIP under `releases\`. The artifact
never includes model weights. See `INSTALL.md` and
`docs/release-checklist.md` before publishing.

## Tests

```powershell
python -m pytest
```

## Documents

- `INSTALL.md`: install, model, build, and uninstall guide
- `PRIVACY.md`: local data and network behavior
- `TERMS.md`: beta terms and limitations
- `SUPPORT.md`: support checklist and issue template
- `RELEASE_NOTES.md`: release notes
- `MODEL_LICENSES.md`: model distribution policy
- `THIRD_PARTY_NOTICES.md`: dependency notice
