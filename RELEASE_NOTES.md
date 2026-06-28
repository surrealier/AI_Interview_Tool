# Release Notes

## v0.9.0-beta

AI Interviewer v0.9.0-beta is the first commercial beta candidate.

### Added

- Offline-first Windows desktop interview practice app.
- Korean and English default HR question set.
- Qwen3-TTS and Windows SAPI TTS backends.
- Optional interviewer video panel with built-in animated fallback.
- Optional microphone recording, faster-whisper STT, and follow-up question generation.
- Session CSV/JSON export with timestamps, repeats, memo, transcript, answer audio path, TTS backend, and quality degradation flag.
- Runtime diagnostics for storage, TTS, STT, microphone, video, and follow-up provider readiness.
- Persistent user settings in `%APPDATA%\AIInterview\config.json`.
- Local support logs in `%APPDATA%\AIInterview\logs\app.log`.

### Changed

- Windows SAPI fallback is now off by default. If Qwen3-TTS fails, the app shows an error unless the user explicitly enables fallback.
- Session saves use temp files and atomic replace to reduce corruption risk.
- Temporary Windows SAPI text sidecar files are deleted after fallback synthesis.

### Known Limitations

- The app is unsigned in beta builds unless a separate signed package is produced.
- Qwen3-TTS quality and speed depend on local GPU/CUDA and installed model size.
- The 0.6B Qwen model may not honor interviewer tone instructions as strongly as the 1.7B model.
- STT and video features require optional interactive dependencies.
- Enterprise administration, multi-user accounts, cloud sync, auto-update, and code signing are outside this beta scope.

### Release Gate

Do not publish a beta package until unit tests pass, `python -m ai_interviewer.release_check --strict` has been reviewed, and the manual checklist in `docs/release-checklist.md` is complete.
