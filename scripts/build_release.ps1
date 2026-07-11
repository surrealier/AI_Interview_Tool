param(
    [string]$Python = "python",
    [string]$Version = "",
    [string]$OutputRoot = ".\releases",
    [switch]$SkipBuild,
    [switch]$SkipInstaller,
    [switch]$FullOffline  # reserved: future bundle that includes model weights
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$DistDir = Join-Path $ProjectRoot "dist\AIInterview"
$OutputDir = Join-Path $ProjectRoot $OutputRoot

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

$ZipPath = Join-Path $OutputDir "AIInterview-$Version-win64.zip"

if (-not $SkipBuild) {
    # A stale dist can contain hand-copied model weights; a clean build keeps
    # the artifact reproducible and weight-free.
    if (Test-Path $DistDir) {
        Remove-Item -Recurse -Force $DistDir
    }
    & $Python (Join-Path $ProjectRoot "scripts\gen_version_info.py")
    if ($LASTEXITCODE -ne 0) { throw "gen_version_info.py failed" }
    & $Python -B -m PyInstaller --noconfirm (Join-Path $ProjectRoot "interview_app.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
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
$LicensesDir = Join-Path $ProjectRoot "docs\third_party_licenses"
if (Test-Path $LicensesDir) {
    Copy-Item -Recurse -Force $LicensesDir (Join-Path $DocsDir "third_party_licenses")
}
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "models") | Out-Null
# Ship the realistic default interviewer video next to the EXE. Users can
# replace it later from the app's media settings.
$DistAssetsDir = Join-Path $DistDir "assets"
New-Item -ItemType Directory -Force -Path $DistAssetsDir | Out-Null
$DefaultInterviewerVideo = Join-Path $ProjectRoot "assets\interviewer.mp4"
if (Test-Path $DefaultInterviewerVideo) {
    Copy-Item -LiteralPath $DefaultInterviewerVideo -Destination $DistAssetsDir -Force
}

$ModelWeights = Get-ChildItem (Join-Path $DistDir "models") -Recurse -File -ErrorAction SilentlyContinue
if ($ModelWeights) {
    throw "dist models folder is not empty; the release artifact must not bundle weights (found $($ModelWeights.Count) files)."
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# Installer (primary artifact)
if (-not $SkipInstaller) {
    $Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $DefaultIscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        if (Test-Path $DefaultIscc) { $Iscc = Get-Item $DefaultIscc }
    }
    if ($Iscc) {
        & $Iscc.Source (Join-Path $ProjectRoot "scripts\setup.iss") "/DAppVersion=$Version"
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }
        Write-Host "Installer: $OutputDir\AIInterview-Setup-$Version.exe"
    } else {
        Write-Warning "ISCC.exe not found; skipping installer. Install Inno Setup 6 or pass -SkipInstaller."
    }
}

# Portable ZIP (secondary artifact)
if (Test-Path $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $DistDir -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host "Release folder: $DistDir"
Write-Host "Release zip: $ZipPath"
