# Chessbot

A Python chess bot that plays automatically on **Duolingo** and **Chess.com** via Playwright. Includes a built-in alpha-beta engine with piece-square tables, transposition table, null-move pruning, LMR, and PVS. Automatically uses Stockfish when available for 2000+ ELO play.

## Features

- Plays automatically on Duolingo Chess and Chess.com
- Built-in engine: alpha-beta + quiescence + TT + NMP + LMR + PVS
- Auto-discovers Stockfish (winget / PATH / local folder)
- CLI mode for human vs bot (no browser needed)
- Windows installer built with PyInstaller + Inno Setup

## Requirements

- Python 3.11+
- Google Chrome or Microsoft Edge (for Playwright)

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium

# Play on Duolingo or Chess.com (interactive menu)
python play_chess.py

# CLI: play against the bot in your terminal
python main.py
```

## Options

```
python play_chess.py --depth 8 --time 0.5
```

| Flag | Default | Description |
|------|---------|-------------|
| `--depth` | `8` | Search depth for built-in engine (ignored when Stockfish found) |
| `--time` | `0.5` | Seconds to think per move |

## Stockfish

Install Stockfish for much stronger play (2000+ ELO). The bot auto-detects it:

```bash
winget install Stockfish.Stockfish
```

Or place `stockfish.exe` anywhere on your PATH, or in a `StockFish/stockfish/` folder next to the project. Without Stockfish the built-in Python engine is used automatically.

## Windows installer

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php). Run the build script once:

```powershell
.\build.ps1
```

This produces `dist\installer\chessbot-setup.exe`. The installer:
1. Copies the bundled app to `Program Files\Chessbot`
2. Copies `stockfish.exe` to `engine\`
3. Installs the Playwright Chromium browser (one-time, ~5 min)
4. Optionally creates a desktop shortcut

## Project structure

```
chessbot/
├── engine.py           # Alpha-beta engine + Stockfish discovery
├── playwright_adapter.py  # Duolingo + Chess.com browser adapters
├── __init__.py
play_chess.py           # Main entry point (browser bot)
main.py                 # CLI mode (human vs bot)
StockFish/              # Bundled Stockfish binary
tests/                  # pytest test suite
build.ps1               # Build script (PyInstaller + Inno Setup)
installer.iss           # Inno Setup script
chessbot.spec           # PyInstaller spec
```

## Tests

```bash
pytest
```
