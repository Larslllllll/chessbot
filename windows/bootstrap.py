"""
Chessbot Bootstrapper — laedt Quellcode von GitHub und richtet alles ein.
Kein Python auf dem Zielsystem noetig (wird via winget installiert falls fehlend).
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO   = "Larslllllll/chessbot"
BRANCH = "main"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "C:/Chessbot")) / "Chessbot"
DESKTOP     = Path(os.path.expanduser("~")) / "Desktop"


def _download(url: str, dest: Path, label: str) -> None:
    print(f"Lade {label} herunter...")
    with urllib.request.urlopen(url, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        data  = bytearray()
        chunk = 1 << 16
        while True:
            block = resp.read(chunk)
            if not block:
                break
            data += block
            if total:
                pct = len(data) * 100 // total
                print(f"\r  {pct}%  ({len(data) // 1024} KB)", end="", flush=True)
    print()
    dest.write_bytes(data)


def _find_python() -> str | None:
    for name in ("python3.11", "python3", "python"):
        p = shutil.which(name)
        if not p:
            continue
        try:
            out = subprocess.check_output(
                [p, "--version"], text=True, stderr=subprocess.STDOUT
            ).strip()
            parts = out.split()[-1].split(".")
            if (int(parts[0]), int(parts[1])) >= (3, 11):
                return p
        except Exception:
            pass
    return None


def _install_python() -> None:
    print("Python 3.11+ nicht gefunden — wird via winget installiert...")
    subprocess.run(
        [
            "winget", "install",
            "--id", "Python.Python.3.11",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        check=True,
    )
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311"
    os.environ["PATH"] = f"{local};{local / 'Scripts'};{os.environ['PATH']}"


def _pip(python: str, *args: str) -> None:
    subprocess.run([python, "-m", "pip", *args], check=True)


def _create_shortcut(bat: Path) -> None:
    lnk = str(DESKTOP / "Chessbot.lnk")
    ps  = (
        f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{lnk}");'
        f'$s.TargetPath="cmd.exe";'
        f'$s.Arguments=\'/k "{bat}"\';'
        f'$s.WorkingDirectory="{INSTALL_DIR}";'
        f'$s.Description="Chessbot starten";'
        f'$s.Save()'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print(f"Desktop-Verknuepfung: {lnk}")


def main() -> None:
    print("\nChessbot Installer")
    print("=" * 40)

    # 1. Source von GitHub laden
    src_url = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "chessbot.zip"
        _download(src_url, zip_path, "Chessbot")

        print("Entpacke...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)

        extracted = next(Path(tmp).glob("chessbot-*/"))

        if INSTALL_DIR.exists():
            shutil.rmtree(INSTALL_DIR)
        shutil.copytree(extracted, INSTALL_DIR)

    print(f"Installiert in: {INSTALL_DIR}\n")

    # 2. Python sicherstellen
    python = _find_python()
    if not python:
        _install_python()
        python = _find_python()
    if not python:
        print("FEHLER: Python konnte nicht installiert werden.")
        input("Enter zum Beenden...")
        sys.exit(1)
    print(f"Python: {python}\n")

    # 3. Abhaengigkeiten
    print("Installiere Abhaengigkeiten...")
    _pip(python, "install", "-r", str(INSTALL_DIR / "requirements.txt"), "-q")

    # 4. Playwright Browser
    print("Installiere Playwright Chromium...")
    subprocess.run([python, "-m", "playwright", "install", "chromium"], check=True)

    # 5. Launcher .bat
    bat = INSTALL_DIR / "chessbot.bat"
    bat.write_text(
        f'@echo off\ncd /d "{INSTALL_DIR}"\n"{python}" play_chess.py %*\n',
        encoding="utf-8",
    )

    # 6. Desktop-Verknuepfung
    _create_shortcut(bat)

    print("\n" + "=" * 40)
    print("Installation abgeschlossen!")
    print(f'Starte Chessbot ueber die Desktop-Verknuepfung.')
    input("\nEnter zum Schliessen...")


if __name__ == "__main__":
    main()
