#Requires -Version 5.1
<#
.SYNOPSIS
  Builds chessbot.exe with PyInstaller and packages it into a Windows installer.

.DESCRIPTION
  Run from project root: .\windows\build.ps1
  1. Runs PyInstaller to create dist\chessbot\ bundle
  2. Runs PyInstaller to create dist\install_browser.exe helper
  3. Locates or downloads Inno Setup 6 compiler (ISCC.exe)
  4. Compiles installer.iss -> dist\installer\chessbot-setup.exe
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$windows_dir = $PSScriptRoot
$proj = Split-Path $windows_dir   # project root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# Change to project root so PyInstaller dist/ lands there
Set-Location $proj

# ── 1. Build main app bundle ───────────────────────────────────────────────
Step "Building chessbot bundle (PyInstaller onedir)"
pyinstaller --clean --noconfirm "$windows_dir\chessbot.spec"

# ── 2. Build browser installer helper (onefile) ────────────────────────────
Step "Building install_browser.exe"
pyinstaller --clean --noconfirm --onefile `
  --name install_browser `
  --collect-all playwright `
  "$proj\install_browser.py"

# Copy helper into main bundle directory
Copy-Item "$proj\dist\install_browser.exe" "$proj\dist\chessbot\" -Force

# ── 3. Locate Inno Setup compiler ──────────────────────────────────────────
Step "Locating Inno Setup"
$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Source

if (-not $iscc) {
    $candidate = @(
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    $iscc = $candidate
}

if (-not $iscc) {
    Write-Host "Inno Setup not found — downloading portable version..." -ForegroundColor Yellow
    $isUrl  = "https://jrsoftware.org/download.php/is.exe"
    $isTmp  = "$env:TEMP\innosetup_installer.exe"
    Invoke-WebRequest -Uri $isUrl -OutFile $isTmp -UseBasicParsing
    Start-Process $isTmp -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait
    $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        throw "Inno Setup install failed. Install manually from https://jrsoftware.org/isdl.php"
    }
}

Write-Host "Using: $iscc"

# ── 4. Create output directory and run ISCC ───────────────────────────────
Step "Compiling installer"
New-Item -ItemType Directory -Force -Path "$proj\dist\installer" | Out-Null
& $iscc "$windows_dir\installer.iss"

$output = "$proj\dist\installer\chessbot-setup.exe"
if (Test-Path $output) {
    $size = (Get-Item $output).Length / 1MB
    Write-Host "`nDone: $output ({0:N0} MB)" -f $size -ForegroundColor Green
} else {
    throw "Installer not found at expected path: $output"
}
