# AI Interviewer

AI Interviewer is an offline-first Windows desktop app that runs a practice
interview and then tells you how it went. It reads each question aloud, records
and transcribes the answer, scores it against a competency rubric, asks the
follow-up the answer actually earned, and produces a session report you can
export. The UI supports Korean and English (switchable in-app).

Everything works with no network and no language model. A local Ollama model or
Claude can be turned on to sharpen the same outputs — see
[Analysis Engine](#analysis-engine).

Current release target: `v1.1.0-rc1` (version source of truth:
`ai_interviewer/__init__.py`).

## What It Does

1. **Plans.** Questions are tagged with the competency they measure and the
   stage they belong to, so coverage is visible while the interview runs.
2. **Interviews.** Qwen3-TTS speaks each question; the answer is recorded and
   transcribed locally with faster-whisper.
3. **Scores.** Each answer gets a 0-100 rubric score across six dimensions,
   plus the specific gaps it left open.
4. **Probes.** When an answer omits something that matters, the app asks about
   that — bounded by a depth cap, and silent when the answer was strong.
5. **Reports.** An overall band, a competency radar, delivery analytics, and a
   practice plan, exportable as Markdown, HTML, or JSON.

See `docs/interview-intelligence.md` for the architecture.

## Beta Scope

- Windows 10/11 single-user desktop app.
- Korean and English default HR question set.
- Step-by-step setup wizard for language, TTS model, speaker, interview type, analysis engine, question source, sound test, and preferences.
- Question prefix cleanup such as `1.`, `1)`, `1.2.`, `Q1.`.
- Qwen3-TTS first, Windows SAPI optional fallback.
- Interviewer video panel with built-in animated fallback.
- Optional microphone recording, faster-whisper STT, and adaptive follow-up questions.
- Rubric scoring, delivery analytics, and a session report (Markdown/HTML/JSON).
- Local session export with timestamps, TTS backend, quality flag, transcript, memo, answer audio path, follow-up question, competency, score, and delivery metrics.
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

## Analysis Engine

Scoring, follow-ups, and reports run on one of three engines, chosen in the
setup wizard or under 설정 → AI 코치:

| Engine | Network | Needs | Notes |
| --- | --- | --- | --- |
| **Offline** (default) | none | nothing | Rule-based, deterministic, always available. |
| **Local Ollama** | localhost | a pulled model | Set the model name in settings or `AI_INTERVIEW_OLLAMA_MODEL`. |
| **Claude** | Anthropic API | `requirements-cloud.txt` + a key | Opt-in with an explicit consent dialog. |

```powershell
python -m pip install -r requirements-cloud.txt   # only for the Claude engine
$env:ANTHROPIC_API_KEY = "sk-ant-..."             # or save it in the app
```

Cloud analysis sends the question and the answer **transcript text** only;
recordings are never uploaded. It cannot be enabled by editing `config.json` —
the app drops a cloud provider that has no recorded consent. Keys are stored in
`%APPDATA%\AIInterview\credentials.json`, never in `config.json`. See
`PRIVACY.md`.

Answer *delivery* (pace, filler, hedging) is always measured locally and is
never sent to or asked of a model.

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

## Speech Models

**Text-to-speech** is Qwen3-TTS (0.6B by default, 1.7B for stronger tone
control), with Windows SAPI as an optional fallback. Synthesis is slower than
real time — roughly 13s on CUDA and 27s on CPU for a 4-second sentence — so the
app never makes you wait for it:

- The **first** question is generated during setup, right after the sound test.
- Every **later** question is generated while you answer the previous one.
- The cache is shared and keyed by voice and text, so a repeated question pack
  plays back instantly on every later run (`%APPDATA%\AIInterview\tts_cache`).
- Generated audio is tightened before caching: the model's 0.5-1.0s of padding
  at each end is cut to a short breath and an over-long mid-sentence stop is
  capped, so a question is spoken as a sentence rather than delivered inside a
  bubble of silence. Clause pauses are shortened, never deleted.

Measured end to end, the pause before a question went from 9.9s to 0.000s.

**Speech-to-text** is faster-whisper, and the model defaults to `auto`:

| device | model | why |
| --- | --- | --- |
| CUDA | `large-v3-turbo` | best accuracy, 23.8x realtime |
| CPU | `small` | 7.9x realtime, keeps the interview responsive |

`large-v3-turbo` can be selected manually on CPU too (3.4x realtime — still
faster and more accurate than `medium`). The `distil-*` checkpoints are not
offered: they are English-only and translate Korean speech into English rather
than transcribing it.

Both figures were measured on 24 seconds of Korean speech, int8 on CPU and
float16 on CUDA.

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
- `docs/interview-intelligence.md`: rubric, scoring, probing, and provider architecture
