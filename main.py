from chessbot.engine import Board, best_move, parse_uci_move


def main() -> None:
    board = Board.startpos()
    print("Chessbot CLI")
    print("Enter moves in UCI format, for example e2e4 or g1f3.")
    print("Type 'quit' to exit.\n")

    while True:
        print(board.unicode_board())
        result = board.result()
        if result:
            print(f"Game over: {result}")
            break

        if board.turn == "w":
            move_text = input("White > ").strip()
            if move_text.lower() in {"quit", "exit"}:
                break
            try:
                move = parse_uci_move(board, move_text)
            except ValueError as exc:
                print(f"Invalid move: {exc}\n")
                continue
        else:
            move = best_move(board, depth=3)
            print(f"Black plays: {move.uci()}")

        board = board.push(move)
        print()


if __name__ == "__main__":
    main()
