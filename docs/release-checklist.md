# Release Checklist

Target artifacts: `AIInterview-Setup-<version>.exe` (installer) and
`AIInterview-<version>-win64.zip` (portable). The version comes from
`ai_interviewer/__init__.py` (`release_check --print-display-version`).

## Automated Gate

- `python -m pytest`
- `python -m ai_interviewer.release_check --strict`
- `.\scripts\build_release.ps1 -Python python` (cleans dist, generates the EXE
  version resource, builds, compiles the installer, writes the ZIP; fails if
  model weights are present in dist)
- `.\scripts\smoke_test_dist.ps1` (`--smoke` exit code + 5-second launch check)

## Packaging Gate

- `dist\AIInterview\AIInterview.exe` starts without console errors.
- EXE file properties show the product name, company, and correct version;
  the window and taskbar show the app icon.
- Package includes README, INSTALL, PRIVACY, TERMS, SUPPORT, RELEASE_NOTES,
  THIRD_PARTY_NOTICES, MODEL_LICENSES, LICENSE, and
  `docs/third_party_licenses/`.
- Package does not include session folders, answer recordings, logs, `.env`,
  or model weights.
- `models/` can be absent without app crash; diagnostics must explain what is
  missing and offer the in-app download.
- The packaged app scores an answer offline: with no Ollama model and no API
  key, the Coach tab must still produce a score. A packaged build that cannot
  score offline means `ai_interviewer.intelligence` was not bundled.
- Diagnostics lists the speech-to-text model it will load and the analysis
  chain it will use, with a reason for every engine it skipped.

## Manual Smoke Test

- Clean VM: run the installer per-user, launch from the Start menu.
- Start app with no models: the wizard model step blocks Next and offers the
  download; download the 0.6B model, cancel mid-way, retry, and confirm resume.
- Switch the UI language (ko ↔ en) in the wizard and in Media settings and
  confirm the screen rebuilds in the selected language.
- On a machine (or with `CUDA_VISIBLE_DEVICES=""`) without CUDA: preload shows
  the CPU-mode notice instead of an error dialog.
- Start app with Qwen 0.6B and play one Korean question.
- Speech timing: run the setup sound test, then start the interview and confirm
  the first question begins speaking immediately (it was synthesized during
  setup). Advance to question 2 while the answer timer is running and confirm
  playback is instant, not a fresh 13-27s synthesis.
- Re-run the same question pack in a new session and confirm every question
  plays instantly from `%APPDATA%\AIInterview\tts_cache`.
- Delete the `tts_cache` folder and confirm the app regenerates audio rather
  than erroring.
- Start app with Qwen 1.7B and confirm interviewer tone instruction is applied.
- Toggle Windows fallback on/off and verify failure behavior is explicit.
- Record a short answer, transcribe it, and confirm it is scored automatically:
  the Coach tab shows dimension meters, gaps, and a suggested follow-up.
- Give a deliberately vague answer ("we did well and everyone was happy") and
  confirm the probe asks for the missing specifics rather than moving on.
- Give a strong answer with a number in it and confirm no probe is forced.
- Open the interview report, confirm the dial, radar, and per-question rows
  render, then export Markdown / HTML / JSON and open each from the session
  `report\` folder.
- Open the session browser, open a session folder, delete an old session, and
  confirm the active session cannot be deleted.
- Confirm `session.json` and `session.csv` contain TTS backend, warning,
  quality flag, transcript, follow-up, memo, answer audio path, competency,
  answer score, and delivery metrics.
- Confirm temporary SAPI `.txt` sidecar files are not left in `audio_cache/`.
- Run with missing microphone and confirm the error does not freeze the UI.
- Run with missing video file and confirm built-in interviewer animation
  fallback works.
- Uninstall: user data under Documents/%APPDATA% is preserved; the models
  prompt appears and honors the choice.

## Approval Rule

Release is blocked by any crash, silent TTS fallback, corrupted session export,
plain-text sidecar leak, or install step that cannot be completed from the
included documentation.

Two additions for the analysis layer:

- **Offline must stay whole.** If scoring, probing, or the report needs a
  network or a model to work at all, the release is blocked — those paths are
  the default install.
- **Cloud must stay deliberate.** If analysis data can leave the machine
  without the user having accepted the consent dialog, the release is blocked.
  Check that a hand-edited `config.json` setting `ai_provider` to `Claude`
  without `enable_cloud_ai` falls back to offline.
