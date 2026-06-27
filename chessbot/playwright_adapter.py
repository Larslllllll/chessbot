from __future__ import annotations

import asyncio
import os
import re
import time as _time
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.engine
from playwright.async_api import Page

from chessbot.engine import Board, best_move, find_stockfish

_engine_pool = ThreadPoolExecutor(max_workers=1)

_STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

_GAME_OVER_STATUSES: frozenset[str] = frozenset({
    "COMPLETED", "FINISHED", "TIMED_OUT", "OVER", "RESIGNED",
    "WON", "LOST", "WIN", "LOSE", "DRAW", "DRAWN",
    "ABANDONED", "FORFEITED", "EXPIRED", "COMPLETE", "ENDED",
})


def _normalize_label(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def _looks_like_restart_action(text: str | None) -> bool:
    normalized = _normalize_label(text)
    if not normalized:
        return False
    return any(
        token in normalized
        for token in ("play again", "rematch", "new game", "new match", "restart")
    )


async def _click_restart_action(page: Page) -> bool:
    return bool(await page.evaluate("""
        () => {
            const labels = ['play again', 'rematch', 'new game', 'new match', 'restart'];
            const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
            for (const el of candidates) {
                const text = [
                    el.innerText,
                    el.textContent,
                    el.getAttribute('aria-label'),
                    el.getAttribute('title'),
                    el.getAttribute('data-testid'),
                ].filter(Boolean).join(' ').toLowerCase();
                if (labels.some(label => text.includes(label))) {
                    el.click();
                    return true;
                }
            }
            return false;
        }
    """))


# ── Stockfish: fresh process per move (no shared state, no pipe corruption) ────

_sf_path: str | None = find_stockfish()


async def _sf_think(
    b: chess.Board,
    time_limit: float,
) -> tuple[chess.Move, int | None, int | None] | None:
    """
    Spawn a fresh Stockfish process, pick the best move, then score the position
    after the move.  Returns (move, score_before, score_after) or None on error.
    A fresh process per call eliminates Windows asyncio pipe-state corruption that
    causes crashes when reusing a persistent subprocess across moves.
    """
    if _sf_path is None:
        return None
    transport = engine = None
    try:
        transport, engine = await chess.engine.popen_uci(_sf_path)
        threads = min(4, max(1, (os.cpu_count() or 2) - 1))
        await engine.configure({
            "Threads": threads,
            "Hash": 128,
            "Skill Level": 20,
        })
        result = await engine.play(
            b,
            chess.engine.Limit(time=time_limit),
            info=chess.engine.INFO_SCORE,
        )
        pov = result.info.get("score")
        score_before = pov.relative.score(mate_score=5000) if pov else None
        print(f"[bot] Stockfish → {result.move.uci()}", flush=True)

        score_after: int | None = None
        try:
            b_after = b.copy()
            b_after.push(result.move)
            info = await engine.analyse(b_after, chess.engine.Limit(depth=10))
            score_after = info["score"].relative.score(mate_score=5000)
        except Exception:
            pass

        return result.move, score_before, score_after
    except Exception as exc:
        print(f"[bot] Stockfish error: {exc}", flush=True)
        return None
    finally:
        if engine is not None:
            try:
                await engine.quit()
            except Exception:
                pass
        if transport is not None:
            try:
                transport.close()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  Duolingo (canvas-based board, React fiber state for game data)
# ══════════════════════════════════════════════════════════════════════════════

def _elo_from_acpl(acpl: float) -> int:
    return max(500, min(3000, round(3000 - 16 * acpl)))


def _cpl_label(cpl: int) -> str:
    if cpl <= 5:   return "best"
    if cpl <= 20:  return "excellent"
    if cpl <= 50:  return "good"
    if cpl <= 100: return "inaccuracy"
    if cpl <= 200: return "mistake"
    return "blunder"


async def _decide_move(
    b: chess.Board,
    depth: int,
    time_limit: float,
) -> tuple[chess.Move, int | None, int | None]:
    """Return (move, score_before, score_after). Uses fresh Stockfish per call; falls back to built-in."""
    result = await _sf_think(b, time_limit)
    if result is not None:
        return result
    print("[bot] Stockfish unavailable — using built-in engine for this move", flush=True)
    loop = asyncio.get_event_loop()
    move = await loop.run_in_executor(_engine_pool, best_move, Board(b), depth, time_limit)
    return move, None, None


def _print_game_stats(our_cpls: list[int], opp_cpls: list[int]) -> None:
    print("[bot] ── Game stats ───────────────────────────────────")
    if our_cpls:
        acpl = sum(our_cpls) / len(our_cpls)
        print(f"[bot]   Bot (us) : ACPL {acpl:5.1f}  |  Est. ELO ~{_elo_from_acpl(acpl)}")
    if opp_cpls:
        acpl = sum(opp_cpls) / len(opp_cpls)
        print(f"[bot]   Opponent : ACPL {acpl:5.1f}  |  Est. ELO ~{_elo_from_acpl(acpl)}")
    print("[bot] ──────────────────────────────────────────────────")


_DUO_CANVAS_SELECTORS = [
    "canvas._3Lbq0",
    "canvas[class*='_3Lbq']",
    "canvas[class*='chess' i]",
    "canvas",
]


class DuolingoChessBot:
    def __init__(self, page: Page) -> None:
        self._page = page
        self._user_id: str | None = None
        self._match_id: str | None = None
        self._orientation: str = "white"
        self._live_state: dict | None = None  # updated by network listener
        self._game_over: bool = False           # set immediately on game-over network event

    def _setup_network_listener(self) -> None:
        import json as _json

        def _ingest(obj: object, source: str) -> None:
            if not isinstance(obj, dict):
                return
            status = str(obj.get("status") or "").upper()
            if "boardFen" in obj:
                print(f"[bot] live state from {source}  moves={len(obj.get('moveHistory') or [])}")
                self._live_state = obj
            if status in _GAME_OVER_STATUSES:
                print(f"[bot] game over from network ({source}): {status}")
                self._game_over = True

        def _scan(data: object, source: str) -> None:
            _ingest(data, source)
            if isinstance(data, dict):
                for v in data.values():
                    _ingest(v, source)

        async def _on_response(response):
            if "json" not in response.headers.get("content-type", ""):
                return
            try:
                _scan(await response.json(), response.url)
            except Exception:
                pass

        def _on_ws(ws):
            def _on_frame(payload: str):
                try:
                    _scan(_json.loads(payload), "WS")
                except Exception:
                    pass
            ws.on("framereceived", lambda frame: _on_frame(frame if isinstance(frame, str) else frame.payload))

        self._page.on("response", _on_response)
        self._page.on("websocket", _on_ws)

    # ── Auth ────────────────────────────────────────────────────────────────

    async def _resolve_user_id(self) -> str:
        if self._user_id:
            return self._user_id
        uid: str | None = await self._page.evaluate(
            """() => {
                const m = document.cookie.match(/jwt_token=([^;]+)/);
                if (!m) return null;
                try {
                    const p = JSON.parse(atob(m[1].split('.')[1]));
                    return p.sub ? String(p.sub) : null;
                } catch (_) { return null; }
            }"""
        )
        if not uid:
            raise RuntimeError(
                "[bot] Cannot read user ID from jwt_token cookie — "
                "make sure you are logged in to Duolingo."
            )
        self._user_id = uid
        return uid

    # ── Game state (React fiber) ─────────────────────────────────────────────
    # The activeMatches REST endpoint only reflects the lobby list and is not
    # updated during a live game.  The live FEN and match metadata live in the
    # React component state of the chess-match page.

    async def _active_match(self) -> dict | None:
        """Read match state directly from the React fiber tree on the page."""
        return await self._page.evaluate(
            """() => {
                const canvas = document.querySelector('canvas._3Lbq0')
                            || document.querySelector('canvas[class*="_3Lbq"]')
                            || document.querySelector('canvas');
                if (!canvas) return null;

                let el = canvas;
                for (let i = 0; i < 20; i++) {
                    const fk = Object.keys(el)
                        .find(k => k.startsWith('__reactFiber'));
                    if (fk) {
                        let fiber = el[fk];
                        for (let j = 0; j < 60 && fiber; j++) {
                            let state = fiber.memoizedState;
                            let d = 0;
                            while (state && d < 25) {
                                const val = state.memoizedState;
                                if (val && typeof val === 'object'
                                        && val.type === 'chessMatch'
                                        && val.match) {
                                    const m = val.match;
                                    // Dump all top-level keys so Python can log them
                                    const allKeys = Object.keys(m);
                                    return {
                                        id: val.id,
                                        boardFen: m.boardFen,
                                        playerColor: m.playerColor,
                                        status: m.status,
                                        moveHistory: m.moveHistory || [],
                                        _allKeys: allKeys,
                                        _sample: JSON.stringify(m).slice(0, 400),
                                    };
                                }
                                state = state.next;
                                d++;
                            }
                            fiber = fiber.return;
                        }
                    }
                    el = el.parentElement;
                    if (!el) break;
                }
                return null;
            }"""
        )

    # ── Public API ───────────────────────────────────────────────────────────

    async def wait_until_ready(self) -> None:
        self._setup_network_listener()
        print("[bot] Waiting for chess canvas…")
        found = False
        for sel in _DUO_CANVAS_SELECTORS:
            try:
                await self._page.wait_for_selector(sel, timeout=300_000)
                print(f"[bot] Canvas found ({sel!r})")
                found = True
                break
            except Exception:
                continue
        if not found:
            raise RuntimeError("[bot] Chess canvas not found after 5 minutes.")
        uid = await self._resolve_user_id()
        print(f"[bot] Logged in — user ID: {uid}")

    async def inspect_board(self) -> str:
        match = await self._active_match()
        if not match:
            print("[bot] No active match.")
            return _STARTPOS_FEN
        self._match_id = match["id"]
        self._orientation = match.get("playerColor", "white")
        fen = match["boardFen"]
        print(f"[bot] FEN: {fen}  (playing as {self._orientation})")
        return fen

    # ── Canvas interaction ───────────────────────────────────────────────────
    # Use query_selector + bounding_box (CDP protocol, not JS main thread) so
    # that intro animations which block JS evaluation don't cause hangs.

    async def _canvas_box(self) -> dict:
        """Return bounding box of the chess canvas via CDP (no JS thread needed)."""
        for sel in _DUO_CANVAS_SELECTORS:
            try:
                el = await asyncio.wait_for(
                    self._page.query_selector(sel), timeout=10
                )
                if not el:
                    continue
                box = await asyncio.wait_for(el.bounding_box(), timeout=10)
                if box and box["width"] > 0:
                    return box
            except Exception:
                continue
        raise RuntimeError("[bot] Chess canvas not found.")

    async def _wait_for_canvas_interactive(self, timeout: float = 30) -> None:
        """Block until the canvas is visible and the intro animation likely done."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                box = await self._canvas_box()
                if box["width"] > 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(1)



    async def _handle_promotion(self) -> None:
        for sel in ("[data-piece='q']", "[data-promotion='q']",
                    "[aria-label*='queen' i]", "[class*='queen' i]"):
            try:
                el = await self._page.wait_for_selector(sel, timeout=2_000)
                if el:
                    await el.click()
                    return
            except Exception:
                continue
        box = await self._canvas_box()
        await self._page.mouse.click(box["x"] + box["width"] / 2, box["y"] + 30)

    async def _square_offset(self, square_name: str) -> dict:
        """Return element-relative {x, y} offset for a square."""
        sq = chess.parse_square(square_name)
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        size: dict = await self._page.evaluate("""() => {
            const c = document.querySelector('canvas._3Lbq0')
                   || document.querySelector('canvas[class*="_3Lbq"]')
                   || document.querySelector('canvas');
            return { w: c.offsetWidth, h: c.offsetHeight };
        }""")
        cell = size["w"] / 8
        if self._orientation == "white":
            ox = file_idx * cell + cell / 2
            oy = (7 - rank_idx) * cell + cell / 2
        else:
            ox = (7 - file_idx) * cell + cell / 2
            oy = rank_idx * cell + cell / 2
        return {"x": ox, "y": oy}

    async def _game_canvas_rect(self) -> dict:
        """Viewport rect of the largest _3Lbq0 canvas (the game board)."""
        return await self._page.evaluate(
            """() => {
                const c = Array.from(document.querySelectorAll('canvas._3Lbq0, canvas[class*="_3Lbq"]'))
                    .reduce((best, el) => (el.offsetWidth * el.offsetHeight) >
                        ((best?.offsetWidth ?? 0) * (best?.offsetHeight ?? 0)) ? el : best, null)
                    || document.querySelector('canvas');
                const r = c.getBoundingClientRect();
                return { x: r.left, y: r.top, w: r.width, h: r.height };
            }"""
        )

    def _sq_viewport(self, rect: dict, sq: int) -> tuple[float, float]:
        # Canvas is 600×750: board is 600×600 centred vertically → 75px header, 75px footer
        board_size = rect["w"]
        y_board = rect["y"] + (rect["h"] - board_size) / 2  # skip header
        cell = board_size / 8
        fi, ri = chess.square_file(sq), chess.square_rank(sq)
        if self._orientation == "white":
            return rect["x"] + fi * cell + cell / 2, y_board + (7 - ri) * cell + cell / 2
        return rect["x"] + (7 - fi) * cell + cell / 2, y_board + ri * cell + cell / 2

    # ── Move execution ───────────────────────────────────────────────────────

    async def play_best_move_from_board(
        self, b: chess.Board, depth: int = 8, time_limit: float = 0.5
    ) -> tuple[str, int | None, int | None]:
        move, score_before, score_after = await _decide_move(b, depth, time_limit)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        print(f"[bot] Playing {move.uci()} ({from_sq} → {to_sq})")
        await self._page.bring_to_front()
        rect = await self._game_canvas_rect()
        fx, fy = self._sq_viewport(rect, move.from_square)
        tx, ty = self._sq_viewport(rect, move.to_square)
        print(f"[bot] drag ({fx:.0f},{fy:.0f}) → ({tx:.0f},{ty:.0f})")
        await self._page.mouse.move(fx, fy)
        await asyncio.sleep(0.03)
        await self._page.mouse.down()
        await asyncio.sleep(0.05)
        await self._page.mouse.move(tx, ty, steps=5)
        await asyncio.sleep(0.03)
        await self._page.mouse.up()
        await self._page.wait_for_timeout(150)
        if move.promotion:
            await self._handle_promotion()
        return move.uci(), score_before, score_after


    async def run_loop(
        self,
        depth: int = 8,
        time_limit: float = 0.5,
        stop_event=None,
        callbacks: dict | None = None,
        xp_farm: bool = False,
    ) -> None:
        print("[bot] Game loop started — press Ctrl+C to stop.")
        print("[bot] Waiting for canvas to become interactive…")
        await self._wait_for_canvas_interactive(timeout=30)
        print("[bot] Canvas ready.")

        callbacks = callbacks or {}
        on_board = callbacks.get("on_board")
        on_move  = callbacks.get("on_move")

        last_played_fen: str | None = None
        last_known_fen:  str | None = None
        s_after_last: int | None = None
        our_cpls: list[int] = []
        opp_cpls: list[int] = []
        bot_move_no = 0

        while True:
            try:
                if stop_event and stop_event.is_set():
                    print("[bot] Stop requested.")
                    break

                if self._game_over:
                    print("[bot] Game over (network event).")
                    _print_game_stats(our_cpls, opp_cpls)
                    if xp_farm:
                        await asyncio.sleep(1.5)
                        if await _click_restart_action(self._page):
                            print("[bot] Restart action clicked — starting next game.")
                            self._game_over = False
                            self._live_state = None
                            last_played_fen = None
                            last_known_fen = None
                            await asyncio.sleep(2)
                            continue
                    break

                state = self._live_state
                self._live_state = None
                if state is None:
                    state = await self._active_match()

                if not state:
                    await asyncio.sleep(1)
                    continue

                self._orientation = state.get("playerColor", "white")
                history: list = state.get("moveHistory") or []
                fen: str = state.get("boardFen") or ""

                if history:
                    b = chess.Board()
                    for uci in history:
                        try:
                            b.push(chess.Move.from_uci(str(uci)))
                        except Exception:
                            break
                elif fen:
                    try:
                        b = chess.Board(fen)
                    except Exception:
                        await asyncio.sleep(0.5)
                        continue
                else:
                    await asyncio.sleep(0.5)
                    continue

                status = str(state.get("status") or "").upper()
                if b.is_game_over() or status in _GAME_OVER_STATUSES:
                    print(f"[bot] Game over — {b.result() or status}")
                    _print_game_stats(our_cpls, opp_cpls)
                    if xp_farm:
                        await asyncio.sleep(1.5)
                        if await _click_restart_action(self._page):
                            print("[bot] Restart action clicked — starting next game.")
                            last_played_fen = None
                            last_known_fen = None
                            self._game_over = False
                            self._live_state = None
                            await asyncio.sleep(2)
                            continue
                    break

                my_color = chess.WHITE if self._orientation == "white" else chess.BLACK
                current_fen = b.fen()
                print(f"[bot] moves={len(history)}  turn={'w' if b.turn == chess.WHITE else 'b'}  my_color={self._orientation}")

                # Board update when opponent moved
                if on_board and current_fen != last_known_fen:
                    last_hist_uci = str(history[-1]) if history else None
                    on_board(current_fen, last_hist_uci, my_color)
                    last_known_fen = current_fen

                if b.turn == my_color and current_fen != last_played_fen:
                    uci, score_before, s_after = await self.play_best_move_from_board(b, depth=depth, time_limit=time_limit)

                    cpl_opp_val: int | None = None
                    cpl_us_val:  int | None = None

                    if s_after_last is not None and score_before is not None:
                        cpl_opp = min(500, max(0, s_after_last + score_before))
                        opp_cpls.append(cpl_opp)
                        cpl_opp_val = cpl_opp
                        acpl_opp = sum(opp_cpls) / len(opp_cpls)
                        print(
                            f"[bot] Opponent : {_cpl_label(cpl_opp)} (CPL {cpl_opp:+d})"
                            f"  ACPL {acpl_opp:.0f}  Est.ELO ~{_elo_from_acpl(acpl_opp)}"
                        )

                    if score_before is not None and s_after is not None:
                        cpl_us = min(500, max(0, score_before + s_after))
                        our_cpls.append(cpl_us)
                        cpl_us_val = cpl_us
                        acpl_us = sum(our_cpls) / len(our_cpls)
                        print(
                            f"[bot] Us (bot)  : {_cpl_label(cpl_us)} (CPL {cpl_us:+d})"
                            f"  ACPL {acpl_us:.0f}  Est.ELO ~{_elo_from_acpl(acpl_us)}"
                        )

                    s_after_last = s_after

                    # Board update after bot's move
                    if on_board:
                        b_after = b.copy()
                        try:
                            b_after.push(chess.Move.from_uci(uci))
                            on_board(b_after.fen(), uci, my_color)
                            last_known_fen = b_after.fen()
                        except Exception:
                            pass

                    if on_move:
                        bot_move_no += 1
                        on_move(bot_move_no, uci, cpl_us_val, cpl_opp_val)

                    last_played_fen = current_fen
                else:
                    await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                print("[bot] Stopped by user.")
                break
            except Exception as exc:
                import traceback
                print(f"[bot] Error: {exc}")
                traceback.print_exc()
                await asyncio.sleep(2)


# ══════════════════════════════════════════════════════════════════════════════
#  Chess.com (DOM-based board: wc-chess-board, piece classes, clock indicators)
# ══════════════════════════════════════════════════════════════════════════════

_CC_PIECE_RE = re.compile(r"\bpiece ([bw])([rnbqkp]) square-(\d)(\d)\b")


def _chesscom_board_from_dom(html: str) -> chess.Board:
    """Parse `piece <color><type> square-<file><rank>` classes into a Board."""
    board = chess.Board(None)
    for m in _CC_PIECE_RE.finditer(html):
        color_ch, type_ch, file_s, rank_s = m.groups()
        color = chess.WHITE if color_ch == "w" else chess.BLACK
        piece_type = chess.Piece.from_symbol(type_ch.upper()).piece_type
        sq = chess.square(int(file_s) - 1, int(rank_s) - 1)
        board.set_piece_at(sq, chess.Piece(piece_type, color))
    return board


class ChessComBot:
    def __init__(self, page: Page) -> None:
        self._page = page
        self._my_color: str = "white"
        self._last_played_fen: str = ""

    # ── Setup ────────────────────────────────────────────────────────────────

    async def wait_until_ready(self) -> None:
        print("[bot] Waiting for chess.com board…")
        await self._page.wait_for_selector("wc-chess-board", timeout=300_000)
        self._my_color = await self._detect_my_color()
        print(f"[bot] Board found — playing as {self._my_color}")

    async def _detect_my_color(self) -> str:
        """White at bottom = white orientation."""
        result: str | None = await self._page.evaluate(
            """() => {
                const bottom = document.querySelector(
                    '.clock-component.clock-bottom');
                if (!bottom) return null;
                return bottom.className.includes('clock-white') ? 'white' : 'black';
            }"""
        )
        return result or "white"

    # ── Board state ──────────────────────────────────────────────────────────

    async def inspect_board(self) -> str:
        html: str = await self._page.evaluate(
            "() => document.querySelector('wc-chess-board')?.innerHTML || ''"
        )
        board = _chesscom_board_from_dom(html)
        board.turn = chess.WHITE if await self._current_turn() == "white" else chess.BLACK
        return board.fen()

    async def _current_turn(self) -> str:
        result: str | None = await self._page.evaluate(
            """() => {
                if (document.querySelector(
                        '.clock-component.clock-white.clock-active'))
                    return 'white';
                if (document.querySelector(
                        '.clock-component.clock-black.clock-active'))
                    return 'black';
                return null;
            }"""
        )
        return result or "white"

    async def is_my_turn(self) -> bool:
        return await self._current_turn() == self._my_color

    # ── Square interaction ───────────────────────────────────────────────────

    async def _board_rect(self) -> dict:
        rect: dict | None = await self._page.evaluate(
            """() => {
                const b = document.querySelector('wc-chess-board');
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return { x: r.left, y: r.top, w: r.width, h: r.height };
            }"""
        )
        if not rect:
            raise RuntimeError("[bot] chess.com board element not found.")
        return rect

    async def _click_square(self, square_name: str) -> None:
        sq = chess.parse_square(square_name)
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        size: dict = await self._page.evaluate("""() => {
            const b = document.querySelector('wc-chess-board');
            return { w: b.offsetWidth, h: b.offsetHeight };
        }""")
        cell = size["w"] / 8
        if self._my_color == "white":
            ox = file_idx * cell + cell / 2
            oy = (7 - rank_idx) * cell + cell / 2
        else:
            ox = (7 - file_idx) * cell + cell / 2
            oy = rank_idx * cell + cell / 2
        print(f"[bot] click {square_name} → offset ({ox:.0f}, {oy:.0f}) in {size['w']}×{size['h']} board")
        await self._page.locator("wc-chess-board").first.click(
            position={"x": ox, "y": oy}, timeout=5_000
        )


    async def _handle_promotion(self) -> None:
        for sel in ("[class*='promotion' i] [class*='queen' i]",
                    "[data-piece='wq'], [data-piece='bq']",
                    "[class*='promote' i][class*='queen' i]"):
            try:
                el = await self._page.wait_for_selector(sel, timeout=2_000)
                if el:
                    await el.click()
                    return
            except Exception:
                continue

    # ── Move execution ───────────────────────────────────────────────────────

    async def play_best_move(self, b: chess.Board, depth: int = 8, time_limit: float = 0.5) -> tuple[str, int | None, int | None]:
        move, score_before, score_after = await _decide_move(b, depth, time_limit)
        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)
        print(f"[bot] Playing {move.uci()} ({from_sq} → {to_sq})")
        await self._page.bring_to_front()
        await self._click_square(from_sq)
        await self._page.wait_for_timeout(150)
        await self._click_square(to_sq)
        await self._page.wait_for_timeout(200)
        if move.promotion:
            await self._handle_promotion()
        self._last_played_fen = b.fen()
        return move.uci(), score_before, score_after

    async def run_loop(
        self,
        depth: int = 8,
        time_limit: float = 0.5,
        stop_event=None,
        callbacks: dict | None = None,
        xp_farm: bool = False,
    ) -> None:
        print("[bot] Game loop started — press Ctrl+C to stop.")

        callbacks = callbacks or {}
        on_board = callbacks.get("on_board")
        on_move  = callbacks.get("on_move")

        s_after_last: int | None = None
        our_cpls: list[int] = []
        opp_cpls: list[int] = []
        last_known_fen: str | None = None
        bot_move_no = 0
        my_color = chess.WHITE if self._my_color == "white" else chess.BLACK

        while True:
            try:
                if stop_event and stop_event.is_set():
                    print("[bot] Stop requested.")
                    break

                if not await self.is_my_turn():
                    # Board update when waiting for opponent
                    fen = await self.inspect_board()
                    if on_board and fen != last_known_fen:
                        on_board(fen, None, my_color)
                        last_known_fen = fen
                    await asyncio.sleep(0.1)
                    continue

                fen = await self.inspect_board()
                b = chess.Board(fen)
                if b.is_game_over():
                    print(f"[bot] Game over: {b.result()}")
                    _print_game_stats(our_cpls, opp_cpls)
                    if xp_farm:
                        await asyncio.sleep(1.5)
                        if await _click_restart_action(self._page):
                            print("[bot] Restart action clicked — starting next game.")
                            self._last_played_fen = ""
                            last_known_fen = None
                            await asyncio.sleep(2)
                            continue
                    break

                if fen != self._last_played_fen:
                    uci, score_before, s_after = await self.play_best_move(b, depth=depth, time_limit=time_limit)

                    cpl_opp_val: int | None = None
                    cpl_us_val:  int | None = None

                    if s_after_last is not None and score_before is not None:
                        cpl_opp = min(500, max(0, s_after_last + score_before))
                        opp_cpls.append(cpl_opp)
                        cpl_opp_val = cpl_opp
                        acpl_opp = sum(opp_cpls) / len(opp_cpls)
                        print(
                            f"[bot] Opponent : {_cpl_label(cpl_opp)} (CPL {cpl_opp:+d})"
                            f"  ACPL {acpl_opp:.0f}  Est.ELO ~{_elo_from_acpl(acpl_opp)}"
                        )

                    if score_before is not None and s_after is not None:
                        cpl_us = min(500, max(0, score_before + s_after))
                        our_cpls.append(cpl_us)
                        cpl_us_val = cpl_us
                        acpl_us = sum(our_cpls) / len(our_cpls)
                        print(
                            f"[bot] Us (bot)  : {_cpl_label(cpl_us)} (CPL {cpl_us:+d})"
                            f"  ACPL {acpl_us:.0f}  Est.ELO ~{_elo_from_acpl(acpl_us)}"
                        )
                    s_after_last = s_after

                    # Board update after bot's move
                    if on_board:
                        b_after = b.copy()
                        try:
                            b_after.push(chess.Move.from_uci(uci))
                            on_board(b_after.fen(), uci, my_color)
                            last_known_fen = b_after.fen()
                        except Exception:
                            pass

                    if on_move:
                        bot_move_no += 1
                        on_move(bot_move_no, uci, cpl_us_val, cpl_opp_val)
                else:
                    await asyncio.sleep(0.5)
            except KeyboardInterrupt:
                print("[bot] Stopped by user.")
                break
            except Exception as exc:
                print(f"[bot] Error: {exc}")
                await asyncio.sleep(2)
