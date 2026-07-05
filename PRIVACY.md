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
```

Session folders may contain personal data, including voice recordings, answers,
transcripts, notes, job/company references, and generated follow-up questions.

## Network Use

The app does not require a cloud service for normal local use. The only network
activity happens when the user explicitly triggers it:

- Model download from Hugging Face, started by the user in the setup wizard or
  settings (or via `scripts/download_models.ps1`). Only the model files are
  downloaded; no interview data is sent.
- Ollama follow-up generation when an Ollama host/model is configured
  (default host is local: `http://127.0.0.1:11434`).
- Any optional cloud provider added by the user or a future licensed build.

The app never uploads recordings, transcripts, or notes anywhere on its own,
and contains no telemetry or crash reporting.

When Ollama or another remote endpoint is configured, the original question and
candidate answer may be sent to that endpoint to generate a follow-up question.

## Deletion

To delete interview data, close the app and remove the target session folder
under `%USERPROFILE%\Documents\AIInterview\sessions\`. To reset settings and
logs, remove `%APPDATA%\AIInterview\`.

## Support

When requesting support, send only the minimum needed files. Remove or redact
voice recordings, transcripts, names, company names, phone numbers, email
addresses, and other personal information unless support explicitly needs them.
