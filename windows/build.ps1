#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$windows_dir = $PSScriptRoot
$proj = Split-Path $windows_dir

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Set-Location $proj

# Baue Bootstrapper als single .exe (laedt alles von GitHub beim ersten Start)
Step "Building chessbot-installer.exe (Bootstrapper)"
pyinstaller --clean --noconfirm --onefile `
  --name chessbot-installer `
  --icon NONE `
  "$windows_dir\bootstrap.py"

$output = "$proj\dist\chessbot-installer.exe"
if (Test-Path $output) {
    $sizeMB = [Math]::Round((Get-Item $output).Length / 1MB, 0)
    Write-Host "`nDone: $output ($sizeMB MB)" -ForegroundColor Green
} else {
    throw "chessbot-installer.exe nicht gefunden."
}
