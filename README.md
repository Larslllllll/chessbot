# Chessbot

Ein Python-Bot der automatisch Schach spielt — auf **Duolingo** und **Chess.com** — gesteuert über Playwright. Läuft auf Windows, Linux und macOS.

Enthält eine eigene Alpha-Beta-Engine mit Piece-Square-Tables, Transpositionstabelle, Null-Move-Pruning, LMR und PVS. Stockfish wird automatisch erkannt oder beim ersten Start heruntergeladen (2000+ ELO).

## Features

- Spielt automatisch auf Duolingo Chess und Chess.com
- Eigene Engine: Alpha-Beta + Quiescence + Transpositionstabelle + NMP + LMR + PVS
- Stockfish wird automatisch gefunden oder heruntergeladen (plattformspezifische Binary)
- CLI-Modus: Mensch gegen Bot im Terminal, ohne Browser
- Läuft nativ auf Windows, Linux und macOS

## Schnellstart

```bash
pip install -r requirements.txt
playwright install chromium

# Bot starten (interaktives Menü)
python play_chess.py

# Gegen den Bot im Terminal spielen
python main.py
```

**Optionen:**

| Option | Standard | Beschreibung |
|--------|----------|--------------|
| `--depth` | `8` | Suchtiefe der eingebauten Engine (ignoriert wenn Stockfish gefunden) |
| `--time` | `0.5` | Sekunden Bedenkzeit pro Zug |

## Stockfish

Stockfish wird beim ersten Start automatisch heruntergeladen und in `engine/` abgelegt. Wer ihn lieber selbst installiert:

| Plattform | Befehl |
|-----------|--------|
| Windows | `winget install Stockfish.Stockfish` |
| macOS | `brew install stockfish` |
| Linux | `sudo apt install stockfish` |

Alternativ einfach die Binary irgendwo im PATH ablegen.

## Als Binary bauen

Jede Plattform hat einen eigenen Build-Ordner mit Script und PyInstaller-Spec.

### Windows → `chessbot-setup.exe`

```powershell
.\windows\build.ps1
# Ausgabe: dist\installer\chessbot-setup.exe
```

Benötigt: Python, PyInstaller, Inno Setup (wird automatisch heruntergeladen falls nicht vorhanden).

### Linux → `chessbot-linux.tar.gz`

```bash
bash linux/build.sh
# Ausgabe: dist/release/chessbot-linux.tar.gz
```

Entpacken und starten:

```bash
tar -xzf chessbot-linux.tar.gz
cd chessbot
./install_browser   # einmalig
./chessbot
```

### macOS → `chessbot-macos.dmg`

```bash
bash macos/build.sh
# Ausgabe: dist/release/chessbot-macos.dmg  (oder .tar.gz falls create-dmg fehlt)
```

`create-dmg` für DMG-Output: `brew install create-dmg`

## Projektstruktur

```
chessbot/
├── engine.py              # Alpha-Beta-Engine + plattformübergreifende Stockfish-Erkennung
├── playwright_adapter.py  # Browser-Adapter für Duolingo und Chess.com
play_chess.py              # Einstiegspunkt (Browser-Bot)
main.py                    # CLI-Modus (Mensch vs. Bot)
install_browser.py         # Playwright Chromium installieren (für Standalone-Binary)
requirements.txt
windows/                   # Build-Dateien für Windows (build.ps1, chessbot.spec, installer.iss)
linux/                     # Build-Dateien für Linux   (build.sh,  chessbot.spec)
macos/                     # Build-Dateien für macOS   (build.sh,  chessbot.spec)
```

---

*Vibe-coded mit Claude Code*
