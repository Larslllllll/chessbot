#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$windows_dir = $PSScriptRoot
$proj = Split-Path $windows_dir

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

Set-Location $proj

# 1. Build main app bundle
Step "Building chessbot bundle (PyInstaller onedir)"
pyinstaller --clean --noconfirm "$windows_dir\chessbot.spec"

# 2. Build browser installer helper
Step "Building install_browser.exe"
pyinstaller --clean --noconfirm --onefile `
  --name install_browser `
  --collect-all playwright `
  "$proj\install_browser.py"

Copy-Item "$proj\dist\install_browser.exe" "$proj\dist\chessbot\" -Force

# 3. Locate Inno Setup
Step "Locating Inno Setup"
$iscc = $null

$fromPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($fromPath) { $iscc = $fromPath.Source }

if (-not $iscc) {
    $pf   = $env:ProgramFiles
    $pf86 = [Environment]::GetFolderPath('ProgramFilesX86')
    $candidates = @(
        "$pf\Inno Setup 6\ISCC.exe",
        "$pf86\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}

if (-not $iscc) {
    Write-Host "Inno Setup not found - downloading..." -ForegroundColor Yellow
    $isTmp = "$env:TEMP\innosetup_installer.exe"
    Invoke-WebRequest -Uri "https://jrsoftware.org/download.php/is.exe" -OutFile $isTmp -UseBasicParsing
    Start-Process $isTmp -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait
    $pf86 = [Environment]::GetFolderPath('ProgramFilesX86')
    $iscc = "$pf86\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        throw "Inno Setup install failed."
    }
}

Write-Host "Using: $iscc"

# 4. Compile installer
Step "Compiling installer"
New-Item -ItemType Directory -Force -Path "$proj\dist\installer" | Out-Null
& $iscc "$windows_dir\installer.iss"

$output = "$proj\dist\installer\chessbot-setup.exe"
if (Test-Path $output) {
    $sizeMB = [Math]::Round((Get-Item $output).Length / 1MB, 0)
    Write-Host "`nDone: $output ($sizeMB MB)" -ForegroundColor Green
} else {
    throw "Installer not found at: $output"
}
