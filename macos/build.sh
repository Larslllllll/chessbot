#!/usr/bin/env bash
set -euo pipefail

MACOS_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(dirname "$MACOS_DIR")"

step() { printf "\n==> %s\n" "$1"; }

# Change to project root so PyInstaller dist/ lands there
cd "$PROJ"

# ── 1. Build main app bundle ───────────────────────────────────────────────
step "Building chessbot bundle (PyInstaller onedir)"
pyinstaller --clean --noconfirm "$MACOS_DIR/chessbot.spec"

# ── 2. Build browser installer helper (onefile) ────────────────────────────
step "Building install_browser"
pyinstaller --clean --noconfirm --onefile \
  --name install_browser \
  --collect-all playwright \
  "$PROJ/install_browser.py"

cp "$PROJ/dist/install_browser" "$PROJ/dist/chessbot/"

# ── 3. Package as DMG (if create-dmg is available) ────────────────────────
step "Packaging for distribution"
mkdir -p "$PROJ/dist/release"

if command -v create-dmg &>/dev/null; then
  step "Creating chessbot.dmg"
  create-dmg \
    --volname "Chessbot" \
    --window-size 600 400 \
    --icon-size 128 \
    "$PROJ/dist/release/chessbot-macos.dmg" \
    "$PROJ/dist/chessbot/"
  SIZE=$(du -sh "$PROJ/dist/release/chessbot-macos.dmg" | cut -f1)
  printf "\nDone: %s/dist/release/chessbot-macos.dmg (%s)\n" "$PROJ" "$SIZE"
else
  # Fallback: plain tarball
  tar -czf "$PROJ/dist/release/chessbot-macos.tar.gz" \
    -C "$PROJ/dist" chessbot
  SIZE=$(du -sh "$PROJ/dist/release/chessbot-macos.tar.gz" | cut -f1)
  printf "\nDone: %s/dist/release/chessbot-macos.tar.gz (%s)\n" "$PROJ" "$SIZE"
  printf "Tip: brew install create-dmg for a proper DMG installer.\n"
fi

printf "\nUsage:\n"
printf "  open chessbot/  (run install_browser first, then chessbot)\n"
