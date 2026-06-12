# Chessbot

Ein Python-Bot der automatisch Schach spielt — auf **Duolingo** und **Chess.com** — gesteuert über Playwright. Enthält eine eigene Alpha-Beta-Engine mit Piece-Square-Tables, Transpositionstabelle, Null-Move-Pruning, LMR und PVS. Stockfish wird automatisch erkannt und genutzt, wenn installiert (2000+ ELO).

## Was der Bot kann

- Spielt automatisch auf Duolingo Chess und Chess.com
- Eigene Engine: Alpha-Beta + Quiescence + Transpositionstabelle + NMP + LMR + PVS
- Erkennt Stockfish automatisch (winget / PATH / lokaler Ordner)
- CLI-Modus: Mensch gegen Bot im Terminal, ohne Browser

## Voraussetzungen

- Python 3.11+
- Google Chrome oder Microsoft Edge

## Schnellstart

```bash
pip install -r requirements.txt
playwright install chromium

# Bot starten (interaktives Menü)
python play_chess.py

# Gegen den Bot im Terminal spielen
python main.py
```

## Optionen

```
python play_chess.py --depth 8 --time 0.5
```

| Option | Standard | Beschreibung |
|--------|----------|--------------|
| `--depth` | `8` | Suchtiefe der eingebauten Engine (wird ignoriert wenn Stockfish gefunden) |
| `--time` | `0.5` | Sekunden Bedenkzeit pro Zug |

## Stockfish installieren

Für deutlich stärkeres Spiel (2000+ ELO):

```bash
winget install Stockfish.Stockfish
```

Oder `stockfish.exe` einfach im PATH ablegen oder in einen Ordner `StockFish/stockfish/` neben dem Projekt. Ohne Stockfish wird automatisch die eingebaute Python-Engine verwendet.

## Projektstruktur

```
chessbot/
├── engine.py              # Alpha-Beta-Engine + Stockfish-Erkennung
├── playwright_adapter.py  # Browser-Adapter für Duolingo und Chess.com
play_chess.py              # Einstiegspunkt (Browser-Bot)
main.py                    # CLI-Modus (Mensch vs. Bot)
requirements.txt
```

---

