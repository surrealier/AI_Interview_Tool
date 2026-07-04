param(
    [ValidateSet("0.6B", "1.7B")]
    [string]$Size = "0.6B",
    [string]$ModelRoot = ".\models",
    [string]$Revision = "main"
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

$TokenizerDir = Join-Path $ModelRoot "Qwen3-TTS-Tokenizer-12Hz"
$ModelDir = Join-Path $ModelRoot ($ModelId.Split("/")[-1])

hf download $TokenizerId --revision $Revision --local-dir $TokenizerDir
hf download $ModelId --revision $Revision --local-dir $ModelDir

# The app's is_model_installed() looks for this marker (same format as the
# in-app downloader writes).
function Write-InstallMarker([string]$Dir, [string]$RepoId) {
    @{
        repo_id       = $RepoId
        revision      = $Revision
        license       = "apache-2.0"
        downloaded_at = (Get-Date -Format o)
    } | ConvertTo-Json | Set-Content -Encoding UTF8 -Path (Join-Path $Dir ".download_complete")
}

Write-InstallMarker $TokenizerDir $TokenizerId
Write-InstallMarker $ModelDir $ModelId

$MetadataPath = Join-Path $ModelRoot "model_sources.txt"
@(
    "downloaded_at=$(Get-Date -Format o)"
    "revision=$Revision"
    "license=apache-2.0"
    "tokenizer=$TokenizerId -> $TokenizerDir"
    "model=$ModelId -> $ModelDir"
) | Set-Content -Encoding UTF8 -Path $MetadataPath

Write-Host "Downloaded $ModelId and tokenizer to $ModelRoot"
Write-Host "Wrote model source metadata to $MetadataPath"
