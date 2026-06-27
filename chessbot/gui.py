"""PyQt6 GUI for Chess Bot."""
from __future__ import annotations

import asyncio
import sys
from typing import Any

import chess
import chess.svg
from PyQt6.QtCore import Qt, QByteArray, QThread, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPixmap, QTextCursor,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

# ── Catppuccin Mocha palette ──────────────────────────────────────────────────
_BG     = "#1e1e2e"
_SURF   = "#181825"
_SURF2  = "#313244"
_SURF3  = "#45475a"
_TEXT   = "#cdd6f4"
_SUB    = "#a6adc8"
_GREEN  = "#a6e3a1"
_RED    = "#f38ba8"
_BLUE   = "#89b4fa"
_YELLOW = "#f9e2af"
_PEACH  = "#fab387"

_QSS = f"""
* {{
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
    color: {_TEXT};
}}
QMainWindow, QWidget {{
    background: {_BG};
}}
QSplitter::handle {{
    background: {_SURF2};
}}
QGroupBox {{
    border: 1px solid {_SURF2};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 4px;
    font-weight: 600;
    color: {_BLUE};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}}
QLabel {{
    background: transparent;
    color: {_TEXT};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {_SURF2};
    border: 1px solid {_SURF3};
    border-radius: 4px;
    padding: 4px 8px;
    color: {_TEXT};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px;
    background: {_SURF3};
    border: none;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {_SURF2};
    border: 1px solid {_SURF3};
    color: {_TEXT};
    selection-background-color: {_BLUE};
    selection-color: {_BG};
}}
QTextEdit {{
    background: {_SURF};
    border: 1px solid {_SURF2};
    border-radius: 4px;
    color: {_GREEN};
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
}}
QTableWidget {{
    background: {_SURF};
    border: 1px solid {_SURF2};
    border-radius: 4px;
    gridline-color: {_SURF2};
    color: {_TEXT};
    alternate-background-color: {_BG};
}}
QTableWidget::item {{ padding: 2px 6px; }}
QTableWidget::item:selected {{ background: {_SURF3}; }}
QHeaderView::section {{
    background: {_SURF2};
    border: none;
    border-right: 1px solid {_SURF3};
    border-bottom: 1px solid {_SURF3};
    padding: 4px 6px;
    font-weight: 600;
    color: {_BLUE};
}}
QPushButton {{
    background: {_SURF2};
    border: 1px solid {_SURF3};
    border-radius: 6px;
    padding: 6px 16px;
    color: {_TEXT};
    font-weight: 600;
}}
QPushButton:hover {{ background: {_SURF3}; border-color: {_BLUE}; }}
QPushButton:disabled {{ color: {_SURF3}; border-color: {_SURF2}; background: {_BG}; }}
QPushButton#btnStart {{
    background: {_GREEN};
    color: {_BG};
    border: none;
    font-size: 14px;
    min-width: 100px;
}}
QPushButton#btnStart:hover {{ background: #8ecf8a; }}
QPushButton#btnStart:disabled {{ background: {_SURF2}; color: {_SURF3}; }}
QPushButton#btnStop {{
    background: {_RED};
    color: {_BG};
    border: none;
    font-size: 14px;
    min-width: 100px;
}}
QPushButton#btnStop:hover {{ background: #d87090; }}
QPushButton#btnStop:disabled {{ background: {_SURF2}; color: {_SURF3}; }}
QScrollBar:vertical {{
    background: {_SURF};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {_SURF3};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {_SURF};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_SURF3};
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""

_SITES = {
    "Duolingo":  "https://www.duolingo.com/chess-matches",
    "Chess.com": "https://www.chess.com/play/online/new",
    "Andere …":  "",
}

_STARTPOS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


# ── Chess board widget ────────────────────────────────────────────────────────

class BoardWidget(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)
        self._fen = _STARTPOS
        self._last_move: str | None = None
        self._orientation = chess.WHITE
        self.setStyleSheet(f"background: {_BG};")

    def update_board(
        self,
        fen: str,
        last_move: str | None = None,
        orientation: chess.Color = chess.WHITE,
    ) -> None:
        self._fen = fen
        self._last_move = last_move
        self._orientation = orientation
        self._render()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._render()

    def _render(self) -> None:
        size = min(self.width(), self.height())
        if size < 80:
            return
        try:
            board = chess.Board(self._fen)
        except Exception:
            board = chess.Board()

        lm: chess.Move | None = None
        if self._last_move:
            try:
                lm = chess.Move.from_uci(self._last_move)
            except Exception:
                pass

        colors = {
            "square light":           "#f0d9b5",
            "square dark":            "#b58863",
            "square light lastmove":  "#cdd26a",
            "square dark lastmove":   "#aaa23a",
            "margin":                 "#2c2d3a",
            "coord":                  "#cdd6f4",
        }
        svg_str = chess.svg.board(
            board,
            lastmove=lm,
            orientation=self._orientation,
            size=size,
            colors=colors,
            coordinates=True,
        )
        renderer = QSvgRenderer(QByteArray(svg_str.encode()))
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(_BG))
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.setPixmap(pixmap)


# ── CPL graph ─────────────────────────────────────────────────────────────────

class CplGraph(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(140, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._bot: list[int] = []
        self._opp: list[int] = []

    def add_cpl(self, bot: int | None, opp: int | None) -> None:
        if bot is not None:
            self._bot.append(min(bot, 500))
        if opp is not None:
            self._opp.append(min(opp, 500))
        self.update()

    def reset(self) -> None:
        self._bot.clear()
        self._opp.clear()
        self.update()

    def paintEvent(self, _: Any) -> None:  # noqa: N802
        w, h = self.width(), self.height()
        pl, pr, pt, pb = 30, 8, 20, 20
        gw = w - pl - pr
        gh = h - pt - pb
        max_cpl = 200

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(0, 0, w, h, QColor(_SURF))

        # Grid lines + Y labels
        for i in range(5):
            cpl_val = max_cpl * i // 4
            gy = pt + gh - gh * i // 4
            painter.setPen(QPen(QColor(_SURF2), 1))
            painter.drawLine(pl, gy, pl + gw, gy)
            painter.setPen(QColor(_SUB))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(2, gy + 4, str(cpl_val))

        # Axis
        painter.setPen(QPen(QColor(_SURF3), 1))
        painter.drawLine(pl, pt, pl, pt + gh)
        painter.drawLine(pl, pt + gh, pl + gw, pt + gh)

        def _draw(series: list[int], color: str) -> None:
            if not series:
                return
            n = len(series)
            pts = []
            for i, val in enumerate(series):
                gx = pl + (gw * i // max(n - 1, 1) if n > 1 else 0)
                gy = pt + gh - int(gh * min(val, max_cpl) / max_cpl)
                pts.append((gx, gy))
            painter.setPen(QPen(QColor(color), 2, Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            for gx, gy in pts:
                painter.drawEllipse(gx - 3, gy - 3, 6, 6)

        _draw(self._bot, _GREEN)
        _draw(self._opp, _RED)

        # Legend
        painter.setFont(QFont("Segoe UI", 8))
        painter.fillRect(pl + 4, pt + 4, 10, 10, QColor(_GREEN))
        painter.setPen(QColor(_TEXT))
        painter.drawText(pl + 16, pt + 13, "Bot")
        painter.fillRect(pl + 50, pt + 4, 10, 10, QColor(_RED))
        painter.drawText(pl + 62, pt + 13, "Gegner")

        painter.end()


# ── Signal stream (stdout → Qt signal) ───────────────────────────────────────

class _SignalStream:
    def __init__(self, signal: Any) -> None:
        self._sig = signal

    def write(self, text: str) -> None:
        if text:
            self._sig.emit(text)

    def flush(self) -> None:
        pass


# ── Worker thread ─────────────────────────────────────────────────────────────

class BotWorker(QThread):
    sig_log      = pyqtSignal(str)
    sig_board    = pyqtSignal(str, str, bool)   # fen, last_uci, is_white_orientation
    sig_move     = pyqtSignal(int, str, int, int)  # move_no, uci, bot_cpl(-1=n/a), opp_cpl(-1=n/a)
    sig_status   = pyqtSignal(str)
    sig_finished = pyqtSignal()

    def __init__(self, url: str, depth: int, time_limit: float, xp_farm: bool = False) -> None:
        super().__init__()
        self.url = url
        self.depth = depth
        self.time_limit = time_limit
        self.xp_farm = xp_farm
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None

    def run(self) -> None:
        stream = _SignalStream(self.sig_log)
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = stream  # type: ignore[assignment]
        sys.stderr = stream  # type: ignore[assignment]
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_run())
        except Exception as exc:
            self.sig_log.emit(f"\n[FEHLER] {exc}\n")
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            try:
                self._loop.close()
            except Exception:
                pass
            self.sig_finished.emit()

    async def _async_run(self) -> None:
        self._stop = asyncio.Event()
        from play_chess import run_bot  # imported here to avoid circular deps

        def _on_board(fen: str, uci: str | None, orient: chess.Color) -> None:
            self.sig_board.emit(fen, uci or "", orient == chess.WHITE)

        def _on_move(no: int, uci: str, bot_cpl: int | None, opp_cpl: int | None) -> None:
            self.sig_move.emit(
                no, uci,
                bot_cpl if bot_cpl is not None else -1,
                opp_cpl if opp_cpl is not None else -1,
            )

        callbacks = {
            "on_board":  _on_board,
            "on_move":   _on_move,
            "on_status": lambda s: self.sig_status.emit(s),
        }
        await run_bot(self.url, self.depth, self.time_limit, self._stop, callbacks, xp_farm=self.xp_farm)

    def stop(self) -> None:
        if self._loop and self._stop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._stop.set)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess Bot")
        self.setMinimumSize(960, 680)
        self._worker: BotWorker | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root_split = QSplitter(Qt.Orientation.Vertical)
        self.setCentralWidget(root_split)

        # Top: board  |  right column
        top_split = QSplitter(Qt.Orientation.Horizontal)
        top_split.setHandleWidth(6)

        # ── Board ─────────────────────────────────────────────────────────────
        self._board = BoardWidget()
        top_split.addWidget(self._board)

        # ── Right column ──────────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(8)
        rl.setContentsMargins(6, 6, 6, 6)

        # Settings group
        grp_cfg = QGroupBox("Einstellungen")
        cl = QVBoxLayout(grp_cfg)
        cl.setSpacing(6)

        row_site = QHBoxLayout()
        row_site.addWidget(QLabel("Plattform:"))
        self._site = QComboBox()
        for name in _SITES:
            self._site.addItem(name)
        self._site.currentTextChanged.connect(self._on_site_changed)
        row_site.addWidget(self._site)
        row_site.addStretch()
        cl.addLayout(row_site)

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("URL:"))
        self._url = QLineEdit(list(_SITES.values())[0])
        self._url.setReadOnly(True)
        row_url.addWidget(self._url)
        cl.addLayout(row_url)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Tiefe:"))
        self._depth = QSpinBox()
        self._depth.setRange(1, 20)
        self._depth.setValue(8)
        self._depth.setFixedWidth(58)
        row_params.addWidget(self._depth)
        row_params.addSpacing(12)
        row_params.addWidget(QLabel("Zeit/Zug (s):"))
        self._time = QDoubleSpinBox()
        self._time.setRange(0.1, 30.0)
        self._time.setSingleStep(0.1)
        self._time.setValue(0.5)
        self._time.setDecimals(1)
        self._time.setFixedWidth(64)
        row_params.addWidget(self._time)
        row_params.addStretch()
        cl.addLayout(row_params)

        self._xp_farm = QCheckBox("XP farm / Auto-Rematch")
        self._xp_farm.setChecked(False)
        cl.addWidget(self._xp_farm)

        rl.addWidget(grp_cfg)

        # Control row
        ctrl = QHBoxLayout()
        self._btn_start = QPushButton("▶  Start")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setFixedHeight(40)
        self._btn_start.clicked.connect(self._on_start)
        ctrl.addWidget(self._btn_start)

        self._btn_stop = QPushButton("■  Stop")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setFixedHeight(40)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        ctrl.addWidget(self._btn_stop)
        rl.addLayout(ctrl)

        # Status label
        self._status = QLabel("● Inaktiv")
        self._status.setStyleSheet(f"color: {_SURF3}; font-weight: 700; font-size: 13px;")
        rl.addWidget(self._status)

        # Move history + CPL graph
        mid_split = QSplitter(Qt.Orientation.Horizontal)
        mid_split.setHandleWidth(4)

        grp_moves = QGroupBox("Züge (Bot)")
        ml = QVBoxLayout(grp_moves)
        ml.setContentsMargins(4, 12, 4, 4)
        self._moves = QTableWidget(0, 4)
        self._moves.setHorizontalHeaderLabels(["#", "UCI", "Bot CPL", "Gegner CPL"])
        self._moves.setAlternatingRowColors(True)
        hh = self._moves.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._moves.verticalHeader().setVisible(False)
        self._moves.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._moves.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._moves.setShowGrid(True)
        ml.addWidget(self._moves)
        mid_split.addWidget(grp_moves)

        grp_cpl = QGroupBox("CPL Verlauf")
        cpl_l = QVBoxLayout(grp_cpl)
        cpl_l.setContentsMargins(4, 12, 4, 4)
        self._graph = CplGraph()
        cpl_l.addWidget(self._graph)
        mid_split.addWidget(grp_cpl)
        mid_split.setSizes([200, 200])

        rl.addWidget(mid_split, stretch=1)
        top_split.addWidget(right)
        top_split.setSizes([380, 580])

        root_split.addWidget(top_split)

        # ── Log ───────────────────────────────────────────────────────────────
        grp_log = QGroupBox("Log")
        ll = QVBoxLayout(grp_log)
        ll.setContentsMargins(4, 12, 4, 4)
        ll.setSpacing(4)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        ll.addWidget(self._log)

        btn_clear = QPushButton("Log leeren")
        btn_clear.setFixedWidth(100)
        btn_clear.clicked.connect(self._log.clear)
        ll.addWidget(btn_clear, alignment=Qt.AlignmentFlag.AlignRight)

        root_split.addWidget(grp_log)
        root_split.setSizes([520, 180])

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_site_changed(self, name: str) -> None:
        url = _SITES.get(name, "")
        self._url.setText(url)
        self._url.setReadOnly(name != "Andere …")

    def _on_start(self) -> None:
        url = self._url.text().strip()
        if not url:
            self._append_log("[Fehler] Keine URL angegeben.\n")
            return

        self._moves.setRowCount(0)
        self._graph.reset()
        self._board.update_board(_STARTPOS)

        depth = self._depth.value()
        t = self._time.value()
        self._worker = BotWorker(url, depth, t, xp_farm=self._xp_farm.isChecked())
        self._worker.sig_log.connect(self._append_log)
        self._worker.sig_board.connect(self._on_board)
        self._worker.sig_move.connect(self._on_move)
        self._worker.sig_status.connect(self._on_status)
        self._worker.sig_finished.connect(self._on_finished)
        self._worker.start()

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._set_status("Läuft", _GREEN)
        self._append_log(f"[Start] {url}  Tiefe={depth}  Zeit={t}s\n")

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.stop()
        self._append_log("[Stopp angefordert…]\n")

    def _on_finished(self) -> None:
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._set_status("Inaktiv", _SURF3)
        self._append_log("[Bot beendet]\n")

    def _on_board(self, fen: str, last_uci: str, white_bottom: bool) -> None:
        orient = chess.WHITE if white_bottom else chess.BLACK
        self._board.update_board(fen, last_uci or None, orient)

    def _on_move(self, move_no: int, uci: str, bot_cpl: int, opp_cpl: int) -> None:
        row = self._moves.rowCount()
        self._moves.insertRow(row)

        self._moves.setItem(row, 0, QTableWidgetItem(str(move_no)))
        self._moves.setItem(row, 1, QTableWidgetItem(uci))

        def _cpl_item(val: int) -> QTableWidgetItem:
            text = str(val) if val >= 0 else "–"
            item = QTableWidgetItem(text)
            if val >= 0:
                color = _GREEN if val <= 5 else (_YELLOW if val <= 50 else _RED)
                item.setForeground(QColor(color))
            return item

        self._moves.setItem(row, 2, _cpl_item(bot_cpl))
        self._moves.setItem(row, 3, _cpl_item(opp_cpl))
        self._moves.scrollToBottom()

        self._graph.add_cpl(
            bot_cpl if bot_cpl >= 0 else None,
            opp_cpl if opp_cpl >= 0 else None,
        )

    def _on_status(self, text: str) -> None:
        self._set_status(text, _BLUE)

    def _set_status(self, text: str, color: str) -> None:
        self._status.setText(f"● {text}")
        self._status.setStyleSheet(f"color: {color}; font-weight: 700; font-size: 13px;")

    def _append_log(self, text: str) -> None:
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log.setTextCursor(cursor)
        self._log.insertPlainText(text)
        self._log.ensureCursorVisible()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        event.accept()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(_QSS)
    win = MainWindow()
    win.resize(1100, 740)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
