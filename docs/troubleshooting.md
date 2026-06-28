# Troubleshooting

## No Sound

1. Press `소리 테스트`.
2. If the Windows sound is not heard, check Windows output device, volume, and mute state.
3. Press `런타임 진단`.
4. If Qwen dependencies are missing, install `requirements-qwen.txt` in the same environment that runs the app.
5. If you need a temporary workaround, enable `Qwen 실패 시 Windows 음성 fallback 허용` or select `Windows 기본 음성`.

## Qwen Is Slow

The first generation can take longer because the model loads into GPU memory.
Use the 0.6B model for lower memory use or the 1.7B model for better tone
control. Confirm CUDA is visible in the diagnostics report.

## STT Fails

- Install `requirements-interactive.txt`.
- Refresh the microphone list and select the correct input device.
- Use `tiny` or `base` if the GPU is out of memory.
- Use STT device `cpu` and compute `int8` when CUDA is unavailable.

## Follow-Up Questions Are Generic

The built-in rules-based follow-up generator is intentionally conservative. For
better follow-up questions, install Ollama locally and configure the model name
in the app settings. If the Ollama host is remote, review the privacy notice
because answers may be sent to that endpoint.

## Where Data Is Stored

Sessions:

```text
%USERPROFILE%\Documents\AIInterview\sessions\
```

Settings/logs:

```text
%APPDATA%\AIInterview\
```
