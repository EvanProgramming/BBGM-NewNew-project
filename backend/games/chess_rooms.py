import chess

try:
    from .board_rooms import build_board_room_router
except ImportError:
    from board_rooms import build_board_room_router


class ChessRules:
    game = "chess"
    first = "white"
    second = "black"
    start_fen = chess.STARTING_FEN

    def turn(self, fen: str) -> str:
        board = chess.Board(fen)
        return "white" if board.turn == chess.WHITE else "black"

    def legal_uci(self, fen: str) -> list[str]:
        return [move.uci() for move in chess.Board(fen).legal_moves]

    def play(self, fen: str, uci: str) -> tuple[str, str, str]:
        board = chess.Board(fen)
        raw = (uci or "").strip().lower()
        candidates = [raw]
        if len(raw) == 4:
            candidates.append(raw + "q")
        move = None
        for candidate in candidates:
            try:
                parsed = chess.Move.from_uci(candidate)
            except ValueError:
                continue
            if parsed in board.legal_moves:
                move = parsed
                break
        if move is None:
            return fen, "", "这步不合法。"
        san = board.san(move)
        board.push(move)
        return board.fen(), san, ""

    def outcome(self, fen: str) -> tuple[bool, str, str]:
        board = chess.Board(fen)
        if not board.is_game_over(claim_draw=True):
            return False, "", ""
        result = board.result(claim_draw=True)
        if result == "1-0":
            return True, "white", "mate" if board.is_checkmate() else "draw"
        if result == "0-1":
            return True, "black", "mate" if board.is_checkmate() else "draw"
        return True, "draw", "draw"


router = build_board_room_router(ChessRules())
