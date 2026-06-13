#!/usr/bin/env bash
set -euo pipefail

LINUX_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(dirname "$LINUX_DIR")"

step() { printf "\n==> %s\n" "$1"; }

# Change to project root so PyInstaller dist/ lands there
cd "$PROJ"

# ── 1. Build main app bundle ───────────────────────────────────────────────
step "Building chessbot bundle (PyInstaller onedir)"
pyinstaller --clean --noconfirm "$LINUX_DIR/chessbot.spec"

# ── 2. Build browser installer helper (onefile) ────────────────────────────
step "Building install_browser"
pyinstaller --clean --noconfirm --onefile \
  --name install_browser \
  --collect-all playwright \
  "$PROJ/install_browser.py"

cp "$PROJ/dist/install_browser" "$PROJ/dist/chessbot/"

# ── 3. Package as tarball ─────────────────────────────────────────────────
step "Creating chessbot-linux.tar.gz"
mkdir -p "$PROJ/dist/release"
tar -czf "$PROJ/dist/release/chessbot-linux.tar.gz" \
  -C "$PROJ/dist" chessbot

SIZE=$(du -sh "$PROJ/dist/release/chessbot-linux.tar.gz" | cut -f1)
printf "\nDone: %s/dist/release/chessbot-linux.tar.gz (%s)\n" "$PROJ" "$SIZE"
printf "\nInstall:\n"
printf "  tar -xzf chessbot-linux.tar.gz\n"
printf "  cd chessbot && ./install_browser && ./chessbot\n"
