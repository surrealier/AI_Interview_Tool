param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutPath = Join-Path $ProjectRoot "constraints.txt"

# Packages that materially affect the shipped app. Everything else in the
# environment (dev tooling, unrelated conda packages) is intentionally excluded.
$Tracked = @(
    "accelerate",
    "av",
    "ctranslate2",
    "faster-whisper",
    "huggingface_hub",
    "numpy",
    "onnxruntime",
    "opencv-python",
    "pillow",
    "pyinstaller",
    "qwen-tts",
    "safetensors",
    "PySide6-Essentials",
    "shiboken6",
    "sounddevice",
    "soundfile",
    "tokenizers",
    "torch",
    "transformers"
)

$Freeze = & $Python -m pip freeze
if (-not $Freeze) {
    throw "pip freeze produced no output for $Python"
}

$Pins = @()
foreach ($Name in $Tracked) {
    $EscapedName = [regex]::Escape($Name)
    $Line = $Freeze | Where-Object { $_ -match "^(?i)$EscapedName==" } | Select-Object -First 1
    if (-not $Line) {
        Write-Warning "Tracked package not installed: $Name"
        continue
    }
    # Strip local version suffixes (e.g. torch==2.6.0+cu124 -> 2.6.0) so the
    # constraint matches both CUDA-index and PyPI wheels.
    $Pins += ($Line -replace "\+.*$", "")
}

$Header = @(
    "# Known-good dependency pins captured from the release build environment.",
    "# Use with: python -m pip install -r <requirements file> -c constraints.txt",
    "# Regenerate with: .\scripts\lock_deps.ps1 -Python <python>",
    "#",
    "# torch 2.6.0+cu124 requires --index-url https://download.pytorch.org/whl/cu124;",
    "# the local-version suffix is stripped here so the constraint also matches the",
    "# CPU wheel from PyPI."
)

($Header + ($Pins | Sort-Object)) -join "`n" | Set-Content -Encoding UTF8 -NoNewline $OutPath
Add-Content -Path $OutPath -Value ""
Write-Host "Wrote $(($Pins).Count) pins to $OutPath"
