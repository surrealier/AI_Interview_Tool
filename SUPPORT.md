# Support

For the v0.9.0-beta release, support is best-effort unless a separate paid
agreement says otherwise.

## Before Contacting Support

1. Open the app and press `런타임 진단`.
2. Confirm the selected Python/EXE environment has the expected dependencies.
3. Confirm the model folder and tokenizer folder exist when Qwen3-TTS is used.
4. Reproduce the issue with one short Korean or English question.

## Files Useful for Debugging

- `%APPDATA%\AIInterview\logs\app.log`
- `%APPDATA%\AIInterview\config.json`
- A screenshot of the runtime diagnostics dialog
- The relevant session `session.json` with personal data redacted

Do not send answer WAV files, transcripts, or notes unless they are necessary
for the issue and you are allowed to share them.

## Issue Template

```text
Version:
Windows version:
GPU/CUDA:
TTS backend:
STT model/device:
Model folder:
Steps to reproduce:
Expected result:
Actual result:
Runtime diagnostics:
```
