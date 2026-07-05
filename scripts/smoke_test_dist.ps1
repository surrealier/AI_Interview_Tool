param(
    [string]$DistDir = ".\dist\AIInterview"
)

$ErrorActionPreference = "Stop"

$Exe = Join-Path (Resolve-Path $DistDir) "AIInterview.exe"
if (-not (Test-Path $Exe)) {
    throw "Missing $Exe - build first (scripts\build_release.ps1)"
}

# 1) Headless smoke: the packaged runtime must boot and report OK via exit code.
$Smoke = Start-Process -FilePath $Exe -ArgumentList "--smoke" -PassThru -Wait
if ($Smoke.ExitCode -ne 0) {
    throw "--smoke failed with exit code $($Smoke.ExitCode). Check %APPDATA%\AIInterview\logs\app.log"
}
Write-Host "smoke check: OK (exit 0)"

# 2) Launch smoke: the GUI must stay alive for 5 seconds.
$App = Start-Process -FilePath $Exe -PassThru
Start-Sleep -Seconds 5
if ($App.HasExited) {
    throw "AIInterview.exe exited within 5s (exit code $($App.ExitCode)). Check the app log."
}
Stop-Process -Id $App.Id -Force
Write-Host "launch check: OK (alive after 5s)"
