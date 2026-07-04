param(
    [string]$Python = "python",
    [string]$Version = "",
    [string]$OutputRoot = ".\releases",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

if (-not $Version) {
    Push-Location $ProjectRoot
    try {
        $Version = (& $Python -m ai_interviewer.release_check --print-display-version).Trim()
    } finally {
        Pop-Location
    }
    if (-not $Version) {
        throw "Could not determine version from ai_interviewer.release_check --print-display-version"
    }
}
$DistDir = Join-Path $ProjectRoot "dist\AIInterview"
$OutputDir = Join-Path $ProjectRoot $OutputRoot
$ZipPath = Join-Path $OutputDir "AIInterview-$Version-win64.zip"

if (-not $SkipBuild) {
    & $Python -B -m PyInstaller --noconfirm (Join-Path $ProjectRoot "interview_app.spec")
}

if (-not (Test-Path (Join-Path $DistDir "AIInterview.exe"))) {
    throw "Missing build output: $DistDir\AIInterview.exe"
}

$Docs = @(
    "README.md",
    "INSTALL.md",
    "PRIVACY.md",
    "TERMS.md",
    "SUPPORT.md",
    "RELEASE_NOTES.md",
    "MODEL_LICENSES.md",
    "THIRD_PARTY_NOTICES.md",
    "LICENSE"
)

foreach ($Doc in $Docs) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Doc) -Destination (Join-Path $DistDir $Doc) -Force
}

$DocsDir = Join-Path $DistDir "docs"
New-Item -ItemType Directory -Force -Path $DocsDir | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\release-checklist.md") -Destination $DocsDir -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\troubleshooting.md") -Destination $DocsDir -Force
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "assets") | Out-Null

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath (Join-Path $ProjectRoot "dist\AIInterview") -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host "Release folder: $DistDir"
Write-Host "Release zip: $ZipPath"
