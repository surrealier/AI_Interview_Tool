# Release Checklist

Target artifact: `AIInterview-v0.9.0-beta-win64.zip`

## Automated Gate

- `python -m pytest`
- `python -m ai_interviewer.release_check --strict`
- `pyinstaller --noconfirm interview_app.spec`

## Packaging Gate

- `dist\AIInterview\AIInterview.exe` starts without console errors.
- Package includes README, INSTALL, PRIVACY, TERMS, SUPPORT, RELEASE_NOTES, THIRD_PARTY_NOTICES, MODEL_LICENSES, and LICENSE.
- Package does not include session folders, answer recordings, logs, `.env`, or model weights unless explicitly approved for a paid package.
- `models/` can be absent without app crash; diagnostics must explain what is missing.

## Manual Smoke Test

- Start app with no models and verify diagnostics warning/error is understandable.
- Start app with Qwen 0.6B and play one Korean question.
- Start app with Qwen 1.7B and confirm interviewer tone instruction is applied.
- Toggle Windows fallback on/off and verify failure behavior is explicit.
- Record a short answer, transcribe it, generate a follow-up question, and save the session.
- Confirm `session.json` and `session.csv` contain TTS backend, warning, quality flag, transcript, follow-up, memo, and answer audio path.
- Confirm temporary SAPI `.txt` sidecar files are not left in `audio_cache/`.
- Open the saved session folder and verify no unrelated app files are written there.
- Run with missing microphone and confirm the error does not freeze the UI.
- Run with missing video file and confirm built-in interviewer animation fallback works.

## Approval Rule

Release is blocked by any crash, silent TTS fallback, corrupted session export,
plain-text sidecar leak, or install step that cannot be completed from the
included documentation.
