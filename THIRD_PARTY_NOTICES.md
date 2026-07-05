# Third-Party Notices

AI Interviewer uses the third-party packages below, depending on the selected
runtime profile. The pinned versions for a release build are recorded in
`constraints.txt`; full license texts are archived under
`docs/third_party_licenses/` and shipped with the release package.

## Core

| Package | License |
| --- | --- |
| Python standard library / Tkinter | PSF License |
| `ttkbootstrap` | MIT |

## Qwen TTS Profile

| Package | License |
| --- | --- |
| `qwen-tts` | Apache-2.0 |
| `torch` | BSD-3-Clause |
| `transformers` | Apache-2.0 |
| `tokenizers` | Apache-2.0 |
| `accelerate` | Apache-2.0 |
| `safetensors` | Apache-2.0 |
| `soundfile` | BSD-3-Clause |
| `huggingface-hub` | Apache-2.0 |

The bundled `soundfile` wheel includes a prebuilt `libsndfile` binary, which is
licensed under LGPL-2.1. It is dynamically linked; the library can be replaced
by any compatible `libsndfile` build. Source: https://github.com/libsndfile/libsndfile

## Interactive Profile

| Package | License |
| --- | --- |
| `opencv-python` | Apache-2.0 |
| `Pillow` | MIT-CMU (HPND) |
| `sounddevice` | MIT |
| `numpy` | BSD-3-Clause |
| `faster-whisper` | MIT |
| `ctranslate2` | MIT |
| `onnxruntime` | MIT |
| `av` (PyAV, bundles FFmpeg) | BSD-3-Clause; FFmpeg components under LGPL-2.1+ |

`sounddevice` bundles the PortAudio library (MIT license).

## Build Tooling (not distributed inside the app)

- PyInstaller — GPL-2.0-or-later with a bootloader exception that permits
  distributing packaged applications under any license.
- Inno Setup — free of charge for distribution, (c) Jordan Russell.

Each dependency is governed by its own license. Regenerate the archived license
texts with `pip-licenses` against `constraints.txt` when dependencies change:

```powershell
python -m pip install pip-licenses
python -m piplicenses --format=plain-vertical --with-license-file --no-license-path --output-file docs/third_party_licenses/licenses.txt
```

Model weights are not covered by this notice. See `MODEL_LICENSES.md`.
