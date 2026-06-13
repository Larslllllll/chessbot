from __future__ import annotations

import platform as _platform
import sys
from dataclasses import dataclass
from pathlib import Path
import shutil
import time as _time

import chess
import chess.polyglot

_LOCAL_ENGINE_DIR = Path(__file__).parent.parent / "engine"


def _stockfish_url() -> str:
    machine = _platform.machine().lower()
    if sys.platform == "win32":
        return (
            "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
            "stockfish-windows-x86-64-avx2.zip"
        )
    if sys.platform == "darwin":
        if "arm" in machine:
            return (
                "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
                "stockfish-macos-m1-apple-silicon.tar"
            )
        return (
            "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
            "stockfish-macos-x86-64-modern.tar"
        )
    # Linux / other Unix
    if "aarch64" in machine or ("arm" in machine and "64" in machine):
        return (
            "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
            "stockfish-ubuntu-aarch64.tar"
        )
    return (
        "https://github.com/official-stockfish/Stockfish/releases/latest/download/"
        "stockfish-ubuntu-x86-64-avx2.tar"
    )


# ── Stockfish auto-discovery ──────────────────────────────────────────────────

def find_stockfish() -> str | None:
    # 1. Lokal heruntergeladene Version (engine/ neben der exe)
    if _LOCAL_ENGINE_DIR.exists():
        for hit in sorted(_LOCAL_ENGINE_DIR.glob("stockfish*"), reverse=True):
            if hit.is_file() and hit.stat().st_size > 0:
                return str(hit)

    # 2. PATH
    sf = shutil.which("stockfish")
    if sf:
        return sf

    # 3. Windows-specific locations
    if sys.platform == "win32":
        import glob
        winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        winget_hits = sorted(
            winget_base.glob("Stockfish.Stockfish_*/stockfish/stockfish*.exe"),
            reverse=True,
        )
        if winget_hits:
            return str(winget_hits[0])
        for d in [
            "C:/Program Files/Stockfish",
            "C:/Program Files (x86)/Stockfish",
            "C:/stockfish",
            str(Path(__file__).parent.parent),
            str(Path(__file__).parent.parent / "stockfish"),
            str(Path(__file__).parent.parent / "StockFish" / "stockfish"),
        ]:
            for hit in sorted(glob.glob(f"{d}/stockfish*.exe"), reverse=True):
                return hit

    return None


def ensure_stockfish() -> str | None:
    """Returns Stockfish path, downloading the engine on first run."""
    path = find_stockfish()
    if path:
        return path

    import io
    import os
    import urllib.request

    url = _stockfish_url()
    print("Stockfish nicht gefunden – wird heruntergeladen ...")
    print(f"Quelle: {url}")

    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            data = bytearray()
            chunk = 1 << 16
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                data += block
                if total:
                    pct = len(data) * 100 // total
                    print(f"\r  {pct:3d}%  ({len(data) // 1024} KB)", end="", flush=True)
        print()
    except Exception as exc:
        print(f"Download fehlgeschlagen: {exc}")
        return None

    _LOCAL_ENGINE_DIR.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        import zipfile
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.namelist():
                name = Path(member).name
                if name.startswith("stockfish") and name.endswith(".exe"):
                    dest = _LOCAL_ENGINE_DIR / name
                    dest.write_bytes(zf.read(member))
                    print(f"Stockfish installiert: {dest}")
                    return str(dest)
        print("Fehler: Kein stockfish*.exe im Archiv gefunden.")
    else:
        import tarfile
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                name = Path(member.name).name
                if name.startswith("stockfish") and "." not in name:
                    f = tf.extractfile(member)
                    if f is None:
                        continue
                    dest = _LOCAL_ENGINE_DIR / name
                    dest.write_bytes(f.read())
                    os.chmod(dest, 0o755)
                    print(f"Stockfish installiert: {dest}")
                    return str(dest)
        print("Fehler: Kein stockfish-Binary im Archiv gefunden.")

    return None


# ── Board wrapper ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Board:
    _board: chess.Board

    @classmethod
    def startpos(cls) -> Board:
        return cls(chess.Board())

    @property
    def turn(self) -> str:
        return "w" if self._board.turn == chess.WHITE else "b"

    def push(self, move: chess.Move) -> Board:
        b = self._board.copy()
        b.push(move)
        return Board(b)

    def result(self) -> str | None:
        outcome = self._board.outcome()
        if outcome is None:
            return None
        if outcome.winner == chess.WHITE:
            return "White wins"
        if outcome.winner == chess.BLACK:
            return "Black wins"
        return "Draw"

    def unicode_board(self) -> str:
        return self._board.unicode(invert_color=False, borders=True)


# ── Piece values ─────────────────────────────────────────────────────────────

PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# ── Piece-square tables (rank 8 first, a-file left) ──────────────────────────
# White index: (7-rank)*8+file   Black: rank*8+file

_PAWN_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]
_KNIGHT_PST = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]
_BISHOP_PST = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20,
]
_ROOK_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
]
_QUEEN_PST = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20,
]
_KING_MID_PST = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20,
]
_KING_END_PST = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50,
]
_PST: dict[int, list[int]] = {
    chess.PAWN: _PAWN_PST,
    chess.KNIGHT: _KNIGHT_PST,
    chess.BISHOP: _BISHOP_PST,
    chess.ROOK: _ROOK_PST,
    chess.QUEEN: _QUEEN_PST,
    chess.KING: _KING_MID_PST,
}


# ── Evaluation ────────────────────────────────────────────────────────────────

def _is_endgame(b: chess.Board) -> bool:
    return (
        len(b.pieces(chess.QUEEN, chess.WHITE)) == 0
        and len(b.pieces(chess.QUEEN, chess.BLACK)) == 0
    )


def _pst_idx(sq: int, color: chess.Color) -> int:
    rank, file = sq >> 3, sq & 7
    return ((7 - rank) << 3 | file) if color == chess.WHITE else (rank << 3 | file)


def evaluate(board: Board) -> int:
    b = board._board
    endgame = _is_endgame(b)
    king_pst = _KING_END_PST if endgame else _KING_MID_PST
    score = 0
    for sq in chess.SQUARES:
        piece = b.piece_at(sq)
        if piece is None:
            continue
        pst = king_pst if piece.piece_type == chess.KING else _PST[piece.piece_type]
        val = PIECE_VALUES[piece.piece_type] + pst[_pst_idx(sq, piece.color)]
        score += val if piece.color == chess.WHITE else -val
    return score


# ── Transposition table ───────────────────────────────────────────────────────

_TT_MAX = 1 << 21   # ~2M entries
_EXACT = 0
_LOWER = 1          # fail-high: score >= beta
_UPPER = 2          # fail-low:  score <= alpha

# Each entry: (depth: int, score: int, flag: int, move: Move|None)
_TT: dict[int, tuple[int, int, int, chess.Move | None]] = {}


# ── Per-search state (reset each call to best_move) ──────────────────────────

_MAX_PLY = 64
_killers: list[list[chess.Move | None]] = [[None, None] for _ in range(_MAX_PLY)]
_history: dict[int, int] = {}          # from_sq<<6|to_sq → score


def _reset() -> None:
    global _killers, _history
    _killers = [[None, None] for _ in range(_MAX_PLY)]
    _history = {}


# ── Move ordering ─────────────────────────────────────────────────────────────

_INF = 100_000


def _mvv_lva(b: chess.Board, move: chess.Move) -> int:
    victim = b.piece_type_at(move.to_square) or chess.PAWN  # en-passant
    attacker = b.piece_type_at(move.from_square)
    return PIECE_VALUES[victim] - (PIECE_VALUES[attacker] >> 3)  # type: ignore[index]


def _move_score(
    b: chess.Board,
    move: chess.Move,
    tt_move: chess.Move | None,
    killers: list[chess.Move | None],
) -> int:
    if move == tt_move:
        return 10_000_000
    if b.is_capture(move):
        return 1_000_000 + _mvv_lva(b, move)
    if move.promotion:
        return 900_000
    if move == killers[0]:
        return 800_000
    if move == killers[1]:
        return 700_000
    return _history.get(move.from_square << 6 | move.to_square, 0)


def _captures_ordered(b: chess.Board) -> list[chess.Move]:
    return sorted(
        (m for m in b.legal_moves if b.is_capture(m)),
        key=lambda m: _mvv_lva(b, m),
        reverse=True,
    )


# ── Quiescence search ─────────────────────────────────────────────────────────

def _quiescence(b: chess.Board, alpha: int, beta: int) -> int:
    sign = 1 if b.turn == chess.WHITE else -1
    stand_pat = evaluate(Board(b)) * sign
    if stand_pat >= beta:
        return beta
    if stand_pat + 975 < alpha:   # delta pruning: queen can't save us
        return alpha
    if stand_pat > alpha:
        alpha = stand_pat
    for move in _captures_ordered(b):
        if _mvv_lva(b, move) < -200:  # skip clearly losing captures
            break
        b.push(move)
        score = -_quiescence(b, -beta, -alpha)
        b.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


# ── Alpha-beta (negamax + PVS + LMR + NMP + TT) ──────────────────────────────

def _negamax(b: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
    if ply > 64:  # hard safety cap — should never trigger in normal play
        return evaluate(Board(b)) * (1 if b.turn == chess.WHITE else -1)
    # Draws
    if b.is_repetition(2) or b.is_fifty_moves():
        return 0

    # TT probe
    key = chess.polyglot.zobrist_hash(b)
    tt = _TT.get(key)
    tt_move: chess.Move | None = None
    if tt is not None:
        tt_depth, tt_score, tt_flag, tt_move = tt
        if tt_depth >= depth:
            if tt_flag == _EXACT:
                return tt_score
            if tt_flag == _LOWER:
                alpha = max(alpha, tt_score)
            else:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    if b.is_game_over():
        return -_INF + ply if b.is_checkmate() else 0
    if depth == 0:
        return _quiescence(b, alpha, beta)

    in_check = b.is_check()

    # Null-move pruning (skip if in check or near-zugzwang endgame)
    if (not in_check and depth >= 3
            and (b.pieces(chess.KNIGHT, b.turn) or b.pieces(chess.BISHOP, b.turn)
                 or b.pieces(chess.ROOK, b.turn) or b.pieces(chess.QUEEN, b.turn))):
        R = 3 if depth >= 5 else 2
        b.push(chess.Move.null())
        null_score = -_negamax(b, depth - 1 - R, -beta, -beta + 1, ply + 1)
        b.pop()
        if null_score >= beta:
            return beta

    orig_alpha = alpha
    best_score = -_INF
    best_move: chess.Move | None = None
    killers = _killers[ply] if ply < _MAX_PLY else [None, None]

    moves = sorted(
        b.legal_moves,
        key=lambda m: _move_score(b, m, tt_move, killers),
        reverse=True,
    )

    for i, move in enumerate(moves):
        is_capture = b.is_capture(move)
        is_promo = move.promotion is not None
        new_depth = depth - 1  # depth strictly decreases — no extensions

        b.push(move)
        gives_check = b.is_check()

        if i == 0:
            score = -_negamax(b, new_depth, -beta, -alpha, ply + 1)
        elif (i >= 4 and new_depth >= 2
              and not in_check and not gives_check
              and not is_capture and not is_promo):
            # LMR: reduced-depth null-window first
            red = 1 + (i >= 8) + (i >= 16)
            score = -_negamax(b, new_depth - red, -alpha - 1, -alpha, ply + 1)
            if score > alpha:
                score = -_negamax(b, new_depth, -beta, -alpha, ply + 1)
        else:
            # PVS null-window for non-PV
            score = -_negamax(b, new_depth, -alpha - 1, -alpha, ply + 1)
            if alpha < score < beta:
                score = -_negamax(b, new_depth, -beta, -alpha, ply + 1)

        b.pop()

        if score > best_score:
            best_score = score
            best_move = move

        if score >= beta:
            if not is_capture:
                if ply < _MAX_PLY:
                    k = _killers[ply]
                    if move != k[0]:
                        k[1], k[0] = k[0], move
                h = move.from_square << 6 | move.to_square
                _history[h] = _history.get(h, 0) + depth * depth
            if len(_TT) < _TT_MAX:
                _TT[key] = (depth, beta, _LOWER, move)
            return beta

        if score > alpha:
            alpha = score

    if len(_TT) < _TT_MAX:
        flag = _EXACT if best_score > orig_alpha else _UPPER
        _TT[key] = (depth, best_score, flag, best_move)

    return best_score


# ── Iterative deepening root ──────────────────────────────────────────────────

def best_move(board: Board, depth: int = 7, time_limit: float = 10.0) -> chess.Move:
    b = board._board.copy()
    _reset()
    hint: chess.Move | None = None
    t_start = _time.monotonic()

    for d in range(1, depth + 1):
        if hint is not None and _time.monotonic() - t_start >= time_limit:
            print(f"[engine] time limit reached before depth {d}, returning {hint.uci()}", flush=True)
            break

        t0 = _time.monotonic()
        best: chess.Move | None = None
        alpha = -_INF

        moves = sorted(
            b.legal_moves,
            key=lambda m: _move_score(b, m, hint, [None, None]),
            reverse=True,
        )
        for move in moves:
            b.push(move)
            score = -_negamax(b, d - 1, -_INF, -alpha, 1)
            b.pop()
            if score > alpha:
                alpha = score
                best = move
                print(f"[engine] depth {d}  {best.uci()}  score {alpha:+d}", flush=True)

        if best is not None:
            hint = best

        elapsed = _time.monotonic() - t0
        print(f"[engine] depth {d} done → {hint.uci() if hint else '?'}  ({elapsed:.1f}s)", flush=True)

    assert hint is not None
    return hint


# ── UCI move parsing ──────────────────────────────────────────────────────────

def parse_uci_move(board: Board, text: str) -> chess.Move:
    try:
        move = chess.Move.from_uci(text.strip())
    except chess.InvalidMoveError as exc:
        raise ValueError(f"Malformed UCI move '{text}': {exc}") from exc
    if move not in board._board.legal_moves:
        raise ValueError(f"Illegal move '{text}' in current position")
    return move
