# Privacy Notice

AI Interviewer is designed as an offline-first Windows desktop app. By default,
interview questions, answer recordings, transcripts, notes, generated follow-up
questions, TTS audio cache, logs, and session CSV/JSON files stay on the user's
PC.

## Local Data

Default session location:

```text
%USERPROFILE%\Documents\AIInterview\sessions\<session_id>\
```

Default settings and logs:

```text
%APPDATA%\AIInterview\config.json
%APPDATA%\AIInterview\logs\app.log
%APPDATA%\AIInterview\credentials.json   (only if you save an API key)
%APPDATA%\AIInterview\tts_cache\         (synthesised question audio)
```

The voice cache holds spoken *questions*, never your answers. It is shared
across sessions so a question is synthesised once instead of on every run, and
it is safe to delete at any time — the app regenerates what it needs.

Session folders may contain personal data, including voice recordings, answers,
transcripts, notes, job/company references, generated follow-up questions,
rubric scores, delivery metrics, and exported reports under `report\`.

If you fill in the optional target role, job description, or background summary,
those are stored in `config.json` and are sent to whichever analysis engine you
have selected.

## Network Use

The app does not require a cloud service for normal local use. The only network
activity happens when the user explicitly triggers it:

- Model download from Hugging Face, started by the user in the setup wizard or
  settings (or via `scripts/download_models.ps1`). Only the model files are
  downloaded; no interview data is sent.
- Local Ollama analysis when an Ollama host/model is configured (default host
  is local: `http://127.0.0.1:11434`).
- Claude analysis, only after you select it and accept the consent dialog.

The app never uploads recordings, transcripts, or notes anywhere on its own,
and contains no telemetry or crash reporting.

## What the Analysis Engines Receive

The default engine is **Offline**: rule-based, no network, nothing leaves the PC.

If you select **Ollama** or **Claude**, these are sent to that engine for the
answer being analysed:

- the interview question,
- the answer **transcript text** (and your memo, if there is no transcript),
- the competency being measured, the interview type, and the optional role,
  job description, and background summary you entered,
- locally measured delivery figures (pace, filler rate) as context,
- for a report: the per-answer scores and transcript excerpts.

These are **never** sent: audio recordings, session files, file paths, logs,
your settings, or anything from other sessions.

Cloud analysis is off by default and cannot be turned on by editing
`config.json` — the app drops a cloud engine that has no recorded consent. Turn
it off again at any time by selecting Offline; that takes effect on the next
analysis.

API keys are read from the `ANTHROPIC_API_KEY` environment variable first. If
you instead save a key in the app it is written to
`%APPDATA%\AIInterview\credentials.json` in plain text, kept out of
`config.json` on purpose so it does not travel in support bundles. Anyone with
access to your Windows account can read that file; prefer the environment
variable on shared machines, and use 키 삭제 to remove a saved key.

Data sent to Anthropic is handled under Anthropic's terms and privacy policy,
not this notice.

## Deletion

To delete interview data, close the app and remove the target session folder
under `%USERPROFILE%\Documents\AIInterview\sessions\`. To reset settings and
logs, remove `%APPDATA%\AIInterview\` (this also removes a saved API key).

## Support

When requesting support, send only the minimum needed files. Remove or redact
voice recordings, transcripts, names, company names, phone numbers, email
addresses, and other personal information unless support explicitly needs them.
