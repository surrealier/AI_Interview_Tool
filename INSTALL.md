# Install Guide

Target release: AI Interviewer for Windows 10/11.

## Installer (recommended)

Run `AIInterview-Setup-<version>.exe`. It installs per-user (no administrator
rights needed) into `%LOCALAPPDATA%\Programs\AIInterview`, creates a Start menu
entry, and registers an uninstaller.

On first run, the setup wizard offers to download the Qwen3-TTS model (about
2.4 GB for 0.6B, 4.5 GB for 1.7B) with a progress bar. An internet connection
is required once for this download; afterwards the app works fully offline.

## Portable ZIP

Extract `AIInterview-<version>-win64.zip` anywhere and run `AIInterview.exe`.
The layout:

```text
AIInterview/
  AIInterview.exe
  _internal/               runtime files (do not modify)
  README.md, INSTALL.md, PRIVACY.md, TERMS.md, SUPPORT.md,
  RELEASE_NOTES.md, THIRD_PARTY_NOTICES.md, MODEL_LICENSES.md
  assets/
    interviewer.mp4        optional interviewer video
  models/                  filled by the in-app model download
```

Model weights and custom video files are external assets. They are not compiled
into the EXE or included in the ZIP; the app downloads models on first setup.

## Developer Install

Use Python 3.12. If you already use a conda environment with CUDA/PyTorch, use
that environment instead of creating `.venv`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt -r requirements-dev.txt -c constraints.txt
python -m pip install -r requirements-interactive.txt -r requirements-qwen.txt -c constraints.txt
```

`constraints.txt` pins the known-good versions used for release builds
(regenerate with `.\scripts\lock_deps.ps1`). For CUDA acceleration install the
matching torch wheel first:

```powershell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu124
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

End users download models inside the app (setup wizard model step, or
설정 → 미디어 → 모델 다운로드). For development environments the script still
works:

```powershell
.\scripts\download_models.ps1 -Size 0.6B
```

For better tone control, use:

```powershell
.\scripts\download_models.ps1 -Size 1.7B
```

## EXE Build

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm interview_app.spec
```

The release candidate folder is:

```text
dist\AIInterview\
```

Run `AIInterview.exe`, open `런타임 진단`, and complete the manual smoke test in
`docs/release-checklist.md` before packaging.

To create the installer and the customer ZIP (requires Inno Setup 6 for the
installer; pass `-SkipInstaller` to skip it):

```powershell
.\scripts\build_release.ps1 -Python python
.\scripts\smoke_test_dist.ps1
```

## Uninstall

Installer builds: use Windows "Apps > Installed apps" or the uninstaller in the
Start menu. The uninstaller asks whether to delete downloaded models (several
GB) and never touches your documents or settings.

Portable builds: delete the application folder.

To remove local user data in both cases, also delete:

```text
%USERPROFILE%\Documents\AIInterview\
%APPDATA%\AIInterview\
```

## Optional: Claude analysis engine

The app scores answers, generates follow-ups, and writes reports offline by
default. To use Claude for that instead, install the optional dependency and
provide a key:

```powershell
python -m pip install -r requirements-cloud.txt
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Then pick **Claude** in the setup wizard's analysis-engine step, or under
설정 → AI 코치. The app asks for consent before the first call and states what is
sent (question and transcript text; never audio). A key can also be saved in the
app, which writes it to `%APPDATA%\AIInterview\credentials.json`. See
`PRIVACY.md`.

A local **Ollama** model needs no extra package: pull a model, then set its name
under 설정 → AI 코치.
