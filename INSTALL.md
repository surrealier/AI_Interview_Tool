# Install Guide

Target release: AI Interviewer v0.9.0-beta for Windows 10/11.

## Recommended Beta Package Layout

```text
AIInterview/
  AIInterview.exe
  README.md
  INSTALL.md
  PRIVACY.md
  TERMS.md
  SUPPORT.md
  RELEASE_NOTES.md
  THIRD_PARTY_NOTICES.md
  MODEL_LICENSES.md
  assets/
    interviewer.mp4        optional
  models/
    Qwen3-TTS-Tokenizer-12Hz/
    Qwen3-TTS-12Hz-0.6B-CustomVoice/
```

Model weights and custom video files are external assets. They are not compiled
into the EXE.

## Developer Install

Use Python 3.12. If you already use a conda environment with CUDA/PyTorch, use
that environment instead of creating `.venv`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-interactive.txt
python -m pip install -r requirements-qwen.txt
```

Run:

```powershell
python -m ai_interviewer
```

Runtime check:

```powershell
python -m ai_interviewer.release_check --strict
```

## Model Download

```powershell
.\scripts\download_models.ps1 -Size 0.6B
```

For better tone control, use:

```powershell
.\scripts\download_models.ps1 -Size 1.7B
```

## EXE Build

```powershell
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm interview_app.spec
```

The release candidate folder is:

```text
dist\AIInterview\
```

Run `AIInterview.exe`, open `런타임 진단`, and complete the manual smoke test in
`docs/release-checklist.md` before packaging the folder as a ZIP.

To create the customer ZIP with documents copied next to the EXE:

```powershell
.\scripts\build_release.ps1 -Python python
```

## Uninstall

Delete the application folder. To remove local user data, also delete:

```text
%USERPROFILE%\Documents\AIInterview\
%APPDATA%\AIInterview\
```
