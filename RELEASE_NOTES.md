# Release Notes

## v1.0.0-rc1 (in preparation)

Quality hardening toward the first commercial release.

### Added

- In-app model downloader: the setup wizard, settings, and diagnostics can
  download the Qwen3-TTS models with progress, speed/ETA, disk-space preflight,
  cancel, and resume. Pinned upstream revisions are recorded per model folder.
- Korean/English UI language switch (setup wizard step 1 and Media settings),
  applied live; the default follows the Windows locale.
- Session browser: list, open, and delete saved sessions from the workspace.
- Global crash handling: unhandled errors are logged and shown in a dialog with
  the log location and a copyable traceback.
- Windows installer (Inno Setup, per-user, Start-menu entry, uninstaller that
  offers to remove downloaded models); app icon and EXE version metadata.
- `--smoke` flag and `scripts/smoke_test_dist.ps1` for packaged-build checks;
  GitHub Actions CI for unit tests.

### Changed

- TTS device selection is automatic: CUDA when available, otherwise CPU with a
  visible CPU-mode notice (previously a hard `cuda:0` requirement failed on
  machines without an NVIDIA GPU).
- The app no longer silently downloads models from Hugging Face when local
  weights are missing; missing models are a diagnostic failure with a one-click
  download.
- The persisted TTS backend setting migrated to the stable id `windows-sapi`.
- UPX compression disabled to reduce antivirus false positives.
- Dependencies are declared and pinned via `constraints.txt`; the release ZIP
  no longer bundles model weights.

## v0.9.0-beta

AI Interviewer v0.9.0-beta is the first commercial beta candidate.

### Added

- Offline-first Windows desktop interview practice app.
- Korean and English default HR question set.
- Step-by-step setup wizard for language, TTS model, speaker, interview type, question source, sound test, and preferences.
- Qwen3-TTS and Windows SAPI TTS backends.
- Optional interviewer video panel with built-in animated fallback.
- Optional microphone recording, faster-whisper STT, and follow-up question generation.
- Session CSV/JSON export with timestamps, repeats, memo, transcript, answer audio path, TTS backend, and quality degradation flag.
- Runtime diagnostics for storage, TTS, STT, microphone, video, and follow-up provider readiness.
- Persistent user settings in `%APPDATA%\AIInterview\config.json`.
- Local support logs in `%APPDATA%\AIInterview\logs\app.log`.

### Changed

- Windows SAPI fallback is now off by default. If Qwen3-TTS fails, the app shows an error unless the user explicitly enables fallback.
- Qwen3-TTS models are no longer preloaded when the app opens. Loading starts only from sound test or interview start.
- Speaker selection is now a supported voice selector instead of free-form text input.
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
