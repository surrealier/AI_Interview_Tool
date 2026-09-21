# Release Notes

## v1.1.0-rc1 (in preparation)

The interview stops being a question reader and starts being an assessment.

### Added

- **Competency rubric.** Every answer is scored 0-100 on six weighted
  dimensions (structure, evidence, impact, reasoning, relevance, delivery) and
  attributed to one of eight competencies, banded outstanding → insufficient.
  Interview type decides which competencies the headline score weights.
- **Answer coach.** A live panel scores the answer just given: dimension
  meters, the specific gaps it left open (no situation, no metric, unclear
  contribution, …), what worked, what to fix, and a model-answer outline.
- **Adaptive follow-ups.** The app decides *whether* a follow-up is earned and
  aims it at the most important omission, with a configurable depth cap. A
  strong answer with no gaps ends the thread instead of being padded.
- **Delivery analytics, measured locally.** Pace (per language), filler rate,
  hedging, sentence length, and numeric evidence, computed from the transcript
  and the recorded duration — never guessed by a model.
- **Interview blueprint.** Questions are tagged with the competency they
  measure and the stage they belong to (opening / core / deep dive / closing),
  which drives live coverage tracking. With a provider configured, a
  role-specific plan can be authored from a job description.
- **Session report.** A new report screen with an overall dial, a competency
  radar, per-dimension meters, delivery summary, strengths, focus areas, and a
  practice plan — exportable as Markdown, a standalone HTML page, or JSON into
  the session folder.
- **Pluggable analysis engine.** Offline rule engine (default, no network, no
  model), a local Ollama model, or Claude. Everything works offline; a provider
  only improves the same outputs.
- **Cloud analysis is opt-in and gated.** A consent dialog states exactly what
  is sent (question and transcript text, never audio). A `config.json` edited
  by hand cannot enable it. API keys live in their own file, never in
  `config.json`.

### Changed

- Session schema is now version 3: per-answer evaluation, delivery metrics and
  probe chains, plus the session blueprint and report. The CSV export gained
  flat analysis columns (`competency`, `answer_score`, `words_per_minute`, …)
  and stays spreadsheet-friendly; older sessions still load.
- `generate_follow_up_question` now delegates to the probing engine, so the
  offline follow-up is chosen by what the answer is missing rather than by
  keyword match. Same signature, better question.
- Runtime diagnostics report the analysis chain that will actually run, with
  the reason any engine was skipped.
- The setup wizard has an analysis-engine step, and takes cloud consent there
  rather than silently at the first scored answer.

### Changed (models and speed)

- **Speech-to-text picks its model by device.** The default is now `auto`:
  `large-v3-turbo` where CUDA is available, `small` on CPU. Measured on 24s of
  Korean speech (int8 on CPU, float16 on CUDA):

  | model | CPU | CUDA | notes |
  | --- | --- | --- | --- |
  | `small` | 7.9x realtime | 41.2x | good, minor errors |
  | `medium` | 3.1x realtime | — | loses punctuation |
  | `large-v3-turbo` | 3.4x realtime | 23.8x | best accuracy, and faster than `medium` |

  `large-v3-turbo` is now selectable everywhere. `distil-*` checkpoints are
  deliberately not offered: they are English-only and silently *translate*
  Korean speech into English instead of transcribing it.
- **The next question is synthesized while the candidate answers.** Speech
  synthesis costs more than the audio it produces — about 13s on CUDA and 27s
  on CPU for a 4s sentence — so the wait now happens inside the answer window.
  Measured end to end, the pause before the next question went from 9.9s to
  0.000s (served from the cache). This is what makes a CPU-only machine usable
  from the second question onward.
- **Local model suggestions.** The Ollama field is now an editable picker of
  models small enough to answer on a CPU, led by Qwen because it handles
  Korean best at that size.

### Fixed

- Korean measurement detection no longer fires on ordinary words: units are
  only counted next to a figure, so 분류 / 초기 / 건강 / 명확 stopped being read
  as "numeric evidence".

## v1.0.0-rc1

Quality hardening toward the first commercial release.

### Added

- Complete UI rewrite on Qt (PySide6): per-monitor high-DPI rendering
  (crisp at 125%/150% scaling), a token-driven design system with light and
  dark themes, and a System/Light/Dark theme switch (setup wizard options and
  Media settings; the default follows the Windows color scheme).
- Vector icon set (Lucide, ISC license) across all controls, tinted per theme.
- Non-blocking runtime diagnostics: the pre-session and TTS diagnostics checks
  now run in the background instead of briefly freezing the window.
- `--smoke-ui` flag: offscreen GUI boot check for packaged builds, wired into
  `scripts/smoke_test_dist.ps1`.

### Removed

- Tkinter/ttkbootstrap UI stack (fully replaced by PySide6-Essentials; see
  `THIRD_PARTY_NOTICES.md` for the Qt LGPL-3.0 notice).

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
