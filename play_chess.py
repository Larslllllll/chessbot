from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from chessbot.engine import ensure_stockfish, find_stockfish
from chessbot.playwright_adapter import ChessComBot, DuolingoChessBot

_SITES = [
    ("Duolingo", "https://www.duolingo.com/chess-matches"),
    ("Chess.com", "https://www.chess.com/play/online/new"),
]


async def _menu(title: str, choices: list[str]) -> int:
    print(f"\n{title}")
    for i, choice in enumerate(choices, 1):
        print(f"  {i}. {choice}")

    def _read() -> int:
        while True:
            raw = input("> ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(choices):
                return int(raw)
            print(f"  Please enter 1–{len(choices)}.")

    return await asyncio.get_event_loop().run_in_executor(None, _read)


async def _ask_url() -> str:
    labels = [f"{name}  ({url})" for name, url in _SITES] + ["Custom URL"]
    choice = await _menu("Select site", labels)
    if choice <= len(_SITES):
        return _SITES[choice - 1][1]

    def _read() -> str:
        while True:
            raw = input("URL: ").strip()
            if raw:
                return raw if "://" in raw else f"https://{raw}"
            print("  Please enter a URL.")

    return await asyncio.get_event_loop().run_in_executor(None, _read)


async def _launch_browser(pw, profile_dir: str):
    if sys.platform == "win32":
        channels = ["chrome", "msedge"]
    elif sys.platform == "darwin":
        channels = ["chrome"]
    else:
        channels = ["chrome", "chromium"]

    for channel in channels:
        try:
            ctx = await pw.chromium.launch_persistent_context(
                profile_dir,
                channel=channel,
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )
            print(f"[bot] Browser: {channel}")
            return ctx
        except Exception as exc:
            print(f"[bot] {channel} not available: {exc}")

    # Fallback: bundled Playwright Chromium
    try:
        ctx = await pw.chromium.launch_persistent_context(
            profile_dir,
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        print("[bot] Browser: playwright chromium")
        return ctx
    except Exception as exc:
        raise RuntimeError(f"No browser found: {exc}") from exc


async def _play_game(
    page,
    url: str,
    depth: int,
    time_limit: float,
    stop_event=None,
    callbacks: dict | None = None,
    wait_for_input: bool = True,
    xp_farm: bool = False,
) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    if wait_for_input:
        print("\n[bot] Log in and start a chess game.")
        print("[bot] Press ENTER when ready...")
        await asyncio.get_event_loop().run_in_executor(None, input)
    else:
        print("[bot] Browser geöffnet — melde dich an und starte ein Spiel.")

    bot: DuolingoChessBot | ChessComBot = (
        ChessComBot(page) if "chess.com" in url else DuolingoChessBot(page)
    )
    await bot.wait_until_ready()
    await bot.run_loop(
        depth=depth,
        time_limit=time_limit,
        stop_event=stop_event,
        callbacks=callbacks,
        xp_farm=xp_farm,
    )


async def run_bot(
    url: str,
    depth: int,
    time_limit: float,
    stop_event,
    callbacks: dict,
    xp_farm: bool = False,
) -> None:
    """GUI entry point — runs the bot without interactive menus."""
    profile_dir = str(Path(__file__).parent / "browser-profile")
    on_status = callbacks.get("on_status")

    sf = ensure_stockfish()
    if sf:
        print(f"[Engine] Stockfish: {sf}")
    else:
        print(f"[Engine] Built-in engine (Tiefe {depth})")

    if on_status:
        on_status("Browser startet…")

    async with async_playwright() as pw:
        ctx = await _launch_browser(pw, profile_dir)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        if on_status:
            on_status("Warte auf Spiel…")
        await _play_game(
            page, url, depth, time_limit,
            stop_event=stop_event,
            callbacks=callbacks,
            wait_for_input=False,
            xp_farm=xp_farm,
        )
        if on_status:
            on_status("Fertig")
        await ctx.close()


async def _run(depth: int, time_limit: float, xp_farm: bool = False) -> None:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: __file__ is inside _internal/ inside Program Files.
        # Writing there requires admin on every launch — use LOCALAPPDATA instead.
        profile_dir = str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Chessbot" / "browser-profile")
    else:
        profile_dir = str(Path(__file__).parent / "browser-profile")

    print("\n╔══════════════════════╗")
    print("║     Chess Bot CLI    ║")
    print("╚══════════════════════╝")
    sf = ensure_stockfish()
    if sf:
        print(f"  Engine : Stockfish  ({sf})")
    else:
        if sys.platform == "win32":
            install_hint = "winget install Stockfish.Stockfish"
        elif sys.platform == "darwin":
            install_hint = "brew install stockfish"
        else:
            install_hint = "sudo apt install stockfish"
        print(f"  Engine : built-in Python engine (depth {depth})")
        print("  Tip    : install Stockfish for 2000+ ELO play")
        print(f"           {install_hint}")
    print(f"  Time   : {time_limit:.0f}s per move")
    print(f"  XP farm: {'on' if xp_farm else 'off'}")

    async with async_playwright() as pw:
        ctx = None
        url: str | None = None

        while True:
            choice = await _menu("Main menu", ["Play game", "Quit"])
            if choice == 2:
                print("[bot] Bye!")
                break

            url = await _ask_url()

            if ctx is None:
                ctx = await _launch_browser(pw, profile_dir)

            while True:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                try:
                    await _play_game(page, url, depth, time_limit, xp_farm=xp_farm)
                except KeyboardInterrupt:
                    print("\n[bot] Interrupted.")

                post = await _menu(
                    "Game over",
                    ["Play again", "Main menu", "Quit"],
                )
                if post == 1:
                    continue
                elif post == 2:
                    break
                else:
                    print("[bot] Bye!")
                    await ctx.close()
                    return

        if ctx:
            await ctx.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chess bot for Duolingo and Chess.com.")
    parser.add_argument(
        "--depth", type=int, default=8,
        help="Search depth for built-in engine (default: %(default)s, ignored when Stockfish is found).",
    )
    parser.add_argument(
        "--time", type=float, default=0.5,
        help="Seconds to think per move (default: %(default)s).",
    )
    parser.add_argument(
        "--xp-farm", action="store_true",
        help="Auto-click restart/rematch after a finished game so the bot keeps farming XP.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.depth, args.time, args.xp_farm))


if __name__ == "__main__":
    main()
