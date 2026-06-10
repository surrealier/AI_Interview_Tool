param(
    [ValidateSet("0.6B", "1.7B")]
    [string]$Size = "0.6B",
    [string]$ModelRoot = ".\models"
)

$ErrorActionPreference = "Stop"

if ($Size -eq "1.7B") {
    $ModelId = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
} else {
    $ModelId = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
}

$TokenizerId = "Qwen/Qwen3-TTS-Tokenizer-12Hz"

New-Item -ItemType Directory -Force -Path $ModelRoot | Out-Null

python -m pip install -U "huggingface_hub[cli]"

hf download $TokenizerId --local-dir (Join-Path $ModelRoot "Qwen3-TTS-Tokenizer-12Hz")
hf download $ModelId --local-dir (Join-Path $ModelRoot ($ModelId.Split("/")[-1]))

Write-Host "Downloaded $ModelId and tokenizer to $ModelRoot"
