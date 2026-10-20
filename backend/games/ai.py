import json
import os
import subprocess
from typing import Literal

import chess
import httpx
from pydantic import BaseModel, Field

from games.rapfi import get_rapfi_engine

CHESS_API_URL = os.getenv("CHESS_API_URL", "https://chess-api.com/v1")
CHESS_TIMEOUT = 8.0
PLAY_DEPTH = 6
CHESS_DIFFICULTY = {
    "beginner": (2, 20, 5, 63),
    "easy": (3, 30, 5, 37),
    "normal": (6, 45, 2, 9),
    "hard": (10, 75, 1, 0),
}
GOMOKU_BOARD_SIZE = 15
GOMOKU_SEARCH_MS = {
    "beginner": 800,
    "easy": 1000,
    "normal": 1200,
    "hard": 1500,
}
GOMOKU_DIFFICULTY_STRENGTH = {
    "beginner": 20,
    "easy": 45,
    "normal": 75,
    "hard": 100,
}
GOMOKU_MISTAKE_PERCENT = {
    "beginner": 22,
    "easy": 10,
    "normal": 0,
    "hard": 0,
}


def parse_eval(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("+", "")
    try:
        return float(text)
    except ValueError:
        return None


def call_chess_api(
    fen: str,
    depth: int | None = None,
    max_thinking_time: int = 50,
    variants: int = 1,
) -> dict | list:
    response = httpx.post(
        os.getenv("CHESS_API_URL", CHESS_API_URL),
        json={
            "fen": fen,
            "depth": PLAY_DEPTH if depth is None else depth,
            "maxThinkingTime": max_thinking_time,
            "variants": max(1, min(5, int(variants))),
        },
        timeout=CHESS_TIMEOUT,
        headers={"Content-Type": "application/json"},
    )
    if response.status_code == 429:
        raise RuntimeError("chess api 429")
    response.raise_for_status()
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("chess api non-json") from exc
    if not isinstance(payload, (dict, list)):
        raise RuntimeError("chess api non-json")
    return payload

class PlayRequest(BaseModel):
    fen: str = ""
    uci: str = ""
    difficulty: Literal["beginner", "easy", "normal", "hard"] = "easy"
    side: Literal["white", "black"] = "white"


class PlayResponse(BaseModel):
    status: str
    error_message: str
    fen: str
    turn: str
    legal_uci: list[str]
    user_san: str
    user_uci: str
    engine_san: str
    engine_uci: str
    from_square: str
    to_square: str
    eval: float
    game_over: bool
    result: str


def legal_uci_list(board: chess.Board) -> list[str]:
    return [move.uci() for move in board.legal_moves]


def parse_user_uci(board: chess.Board, uci: str) -> chess.Move | None:
    raw = uci.strip().lower()
    candidates = [raw]
    if len(raw) == 4:
        candidates.append(raw + "q")
    for candidate in candidates:
        try:
            move = chess.Move.from_uci(candidate)
        except ValueError:
            continue
        if move in board.legal_moves:
            return move
    return None


def parse_engine_move(board: chess.Board, payload: dict) -> chess.Move | None:
    uci = str(payload.get("move") or payload.get("lan") or "").strip()
    if uci:
        try:
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                return move
        except ValueError:
            pass
    san = payload.get("san")
    if san:
        try:
            move = board.parse_san(str(san))
            if move in board.legal_moves:
                return move
        except ValueError:
            pass
    return None


def chess_variant_payloads(payload: dict | list) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("variants", "moves", "pvs"):
        nested = payload.get(key)
        if isinstance(nested, list) and nested:
            return [item for item in nested if isinstance(item, dict)]
    return [payload]


def find_chess_mate_in_one(board: chess.Board) -> chess.Move | None:
    for move in board.legal_moves:
        board.push(move)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move
    return None


def chess_position_seed(fen: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(fen))


def force_engine_mate(difficulty: str) -> bool:
    return difficulty in {"normal", "hard"}


def weaker_chess_move(
    board: chess.Board,
    best: chess.Move,
    mistake_percent: int,
    *,
    force_mate: bool = True,
) -> chess.Move:
    if force_mate:
        mate = find_chess_mate_in_one(board)
        if mate is not None:
            return mate
    if mistake_percent <= 0:
        return best
    if chess_position_seed(board.fen()) % 100 >= mistake_percent:
        return best

    piece_value = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }
    candidates: list[chess.Move] = []
    for move in board.legal_moves:
        if move == best:
            continue
        candidates.append(move)
    if not candidates:
        return best

    def weakness_key(move: chess.Move) -> tuple[int, int, str]:
        captured = board.piece_at(move.to_square)
        capture_score = piece_value.get(captured.piece_type, 0) if captured else 0
        board.push(move)
        gives_check = board.is_check()
        board.pop()
        return (1 if gives_check else 0, capture_score, move.uci())

    ordered = sorted(candidates, key=weakness_key)
    pool = ordered[: max(1, len(ordered) // 3)]
    return pool[chess_position_seed(board.fen()) % len(pool)]


def play_state(
    board: chess.Board,
    *,
    error: str = "",
    user_san: str = "",
    user_uci: str = "",
    engine_san: str = "",
    engine_uci: str = "",
    from_square: str = "",
    to_square: str = "",
    eval_score: float = 0,
) -> PlayResponse:
    game_over = board.is_game_over(claim_draw=True)
    return PlayResponse(
        status="error" if error else "success",
        error_message=error,
        fen=board.fen(),
        turn="white" if board.turn == chess.WHITE else "black",
        legal_uci=legal_uci_list(board),
        user_san=user_san,
        user_uci=user_uci,
        engine_san=engine_san,
        engine_uci=engine_uci,
        from_square=from_square,
        to_square=to_square,
        eval=float(eval_score),
        game_over=game_over,
        result=board.result(claim_draw=True) if game_over else "",
    )


def apply_engine_move(
    board: chess.Board,
    difficulty: str,
) -> tuple[str, str, str, str, float]:
    depth, max_thinking_time, variants, mistake_percent = CHESS_DIFFICULTY[difficulty]
    payload = call_chess_api(
        board.fen(),
        depth=depth,
        max_thinking_time=max_thinking_time,
        variants=variants,
    )
    variant_payloads = chess_variant_payloads(payload)
    score = 0.0
    ranked_moves: list[chess.Move] = []
    for item in variant_payloads:
        parsed = parse_engine_move(board, item)
        if parsed is None:
            continue
        if parsed not in ranked_moves:
            ranked_moves.append(parsed)
        if score == 0.0:
            score = parse_eval(item.get("eval")) or 0.0

    if not ranked_moves:
        legal = list(board.legal_moves)
        if not legal:
            raise RuntimeError("engine no move")
        ranked_moves = [legal[0]]

    # Prefer later (weaker) multipv entries for lower difficulties when API provides them.
    if difficulty == "beginner" and len(ranked_moves) >= 4:
        move = ranked_moves[min(len(ranked_moves) - 1, 3 + chess_position_seed(board.fen()) % 2)]
    elif difficulty == "easy" and len(ranked_moves) >= 3:
        move = ranked_moves[2]
    else:
        move = ranked_moves[0]

    move = weaker_chess_move(
        board,
        move,
        mistake_percent,
        force_mate=force_engine_mate(difficulty),
    )
    engine_san = board.san(move)
    engine_uci = move.uci()
    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    board.push(move)
    return engine_san, engine_uci, from_square, to_square, score


def play(payload: PlayRequest) -> PlayResponse:
    fen = (payload.fen or "").strip() or chess.STARTING_FEN
    try:
        board = chess.Board(fen)
    except ValueError:
        return play_state(chess.Board(), error="局面无效。")

    user_san = ""
    user_uci = ""
    engine_san = ""
    engine_uci = ""
    from_square = ""
    to_square = ""
    eval_score = 0.0

    user_turn = chess.WHITE if payload.side != "black" else chess.BLACK
    uci = (payload.uci or "").strip()
    if uci:
        if board.turn != user_turn:
            return play_state(board, error="还没轮到你走。")
        move = parse_user_uci(board, uci)
        if move is None:
            return play_state(board, error="这步不合法。")
        user_san = board.san(move)
        user_uci = move.uci()
        from_square = chess.square_name(move.from_square)
        to_square = chess.square_name(move.to_square)
        board.push(move)
        if board.is_game_over(claim_draw=True):
            return play_state(
                board,
                user_san=user_san,
                user_uci=user_uci,
                from_square=from_square,
                to_square=to_square,
            )

    if board.turn != user_turn and not board.is_game_over(claim_draw=True):
        try:
            engine_san, engine_uci, from_square, to_square, eval_score = apply_engine_move(
                board,
                payload.difficulty,
            )
        except (httpx.HTTPError, httpx.RequestError, RuntimeError, KeyError, TypeError, ValueError):
            if user_uci:
                board.pop()
            return play_state(board, error="下棋引擎暂时不可用，点「让电脑走」再试。")

    return play_state(
        board,
        user_san=user_san,
        user_uci=user_uci,
        engine_san=engine_san,
        engine_uci=engine_uci,
        from_square=from_square,
        to_square=to_square,
        eval_score=eval_score,
    )


class GomokuMove(BaseModel):
    row: int = Field(ge=0, lt=GOMOKU_BOARD_SIZE)
    col: int = Field(ge=0, lt=GOMOKU_BOARD_SIZE)
    player: Literal["black", "white"]


class GomokuPlayRequest(BaseModel):
    moves: list[GomokuMove] = Field(default_factory=list, max_length=225)
    difficulty: Literal["beginner", "easy", "normal", "hard"] = "easy"
    side: Literal["black", "white"] = "black"


class GomokuPlayResponse(BaseModel):
    status: Literal["success", "error"]
    error_message: str
    moves: list[GomokuMove]
    turn: Literal["black", "white", ""]
    user_move: GomokuMove | None
    engine_move: GomokuMove | None
    game_over: bool
    result: Literal["black", "white", "draw", ""]


def gomoku_winner(moves: list[GomokuMove]) -> str:
    occupied = {(move.row, move.col): move.player for move in moves}
    for move in moves:
        for row_step, col_step in ((1, 0), (0, 1), (1, 1), (1, -1)):
            count = 1
            for direction in (-1, 1):
                row = move.row + row_step * direction
                col = move.col + col_step * direction
                while occupied.get((row, col)) == move.player:
                    count += 1
                    row += row_step * direction
                    col += col_step * direction
            if count >= 5:
                return move.player
    return ""


def gomoku_history_seed(moves: list[GomokuMove]) -> int:
    return sum(
        (index + 1)
        * (
            (move.row + 1) * 31
            + (move.col + 1) * 17
            + (1 if move.player == "black" else 2)
        )
        for index, move in enumerate(moves)
    )


def weakened_gomoku_move(
    moves: list[GomokuMove],
    rapfi_row: int,
    rapfi_col: int,
    mistake_percent: int,
    *,
    force_mate: bool = True,
) -> tuple[int, int]:
    if mistake_percent <= 0:
        return rapfi_row, rapfi_col
    if gomoku_history_seed(moves) % 100 >= mistake_percent:
        return rapfi_row, rapfi_col

    occupied = {(move.row, move.col) for move in moves}
    legal_points = [
        (row, col)
        for row in range(GOMOKU_BOARD_SIZE)
        for col in range(GOMOKU_BOARD_SIZE)
        if (row, col) not in occupied
    ]
    engine_player = "white" if moves and moves[-1].player == "black" else "black"
    opponent = "black" if engine_player == "white" else "white"

    def wins_for(player: str, point: tuple[int, int]) -> bool:
        return (
            gomoku_winner(
                [
                    *moves,
                    GomokuMove(row=point[0], col=point[1], player=player),
                ]
            )
            == player
        )

    immediate_wins = [point for point in legal_points if wins_for(engine_player, point)]
    if force_mate and immediate_wins:
        rapfi = (rapfi_row, rapfi_col)
        return rapfi if rapfi in immediate_wins else sorted(immediate_wins)[0]

    immediate_blocks = [point for point in legal_points if wins_for(opponent, point)]
    if force_mate and immediate_blocks:
        rapfi = (rapfi_row, rapfi_col)
        return rapfi if rapfi in immediate_blocks else sorted(immediate_blocks)[0]

    candidates: set[tuple[int, int]] = set()
    for move in moves:
        for row_delta in range(-2, 3):
            for col_delta in range(-2, 3):
                row = move.row + row_delta
                col = move.col + col_delta
                if (
                    0 <= row < GOMOKU_BOARD_SIZE
                    and 0 <= col < GOMOKU_BOARD_SIZE
                    and (row, col) not in occupied
                ):
                    candidates.add((row, col))

    if not candidates:
        candidates = set(legal_points)

    def weakness_key(point: tuple[int, int]) -> tuple[int, int, int, int]:
        row, col = point
        adjacent = sum(
            (row + row_delta, col + col_delta) in occupied
            for row_delta in (-1, 0, 1)
            for col_delta in (-1, 0, 1)
            if row_delta or col_delta
        )
        center_distance = abs(row - 7) + abs(col - 7)
        return adjacent, -center_distance, row, col

    ordered = sorted(candidates, key=weakness_key)
    weaker_pool = ordered[: max(1, len(ordered) // 3)]
    stable_seed = gomoku_history_seed(moves)
    return weaker_pool[stable_seed % len(weaker_pool)]


def validate_gomoku_moves(moves: list[GomokuMove]) -> str:
    occupied: set[tuple[int, int]] = set()
    for index, move in enumerate(moves):
        expected = "black" if index % 2 == 0 else "white"
        if move.player != expected:
            return f"第 {index + 1} 手颜色顺序不正确。"
        point = (move.row, move.col)
        if point in occupied:
            return f"第 {index + 1} 手落在已有棋子的位置。"
        occupied.add(point)
        if index < len(moves) - 1 and gomoku_winner(moves[: index + 1]):
            return "棋局结束后不能继续落子。"
    return ""


def gomoku_response(
    moves: list[GomokuMove],
    *,
    error: str = "",
    user_move: GomokuMove | None = None,
    engine_move: GomokuMove | None = None,
) -> GomokuPlayResponse:
    winner = gomoku_winner(moves)
    full = len(moves) == GOMOKU_BOARD_SIZE * GOMOKU_BOARD_SIZE
    game_over = bool(winner) or full
    result = winner or ("draw" if full else "")
    turn = "" if game_over else ("black" if len(moves) % 2 == 0 else "white")
    return GomokuPlayResponse(
        status="error" if error else "success",
        error_message=error,
        moves=moves,
        turn=turn,
        user_move=user_move,
        engine_move=engine_move,
        game_over=game_over,
        result=result,
    )


def gomoku_play(payload: GomokuPlayRequest) -> GomokuPlayResponse:
    moves = list(payload.moves)
    validation_error = validate_gomoku_moves(moves)
    if validation_error:
        return gomoku_response(moves, error=validation_error)

    if gomoku_winner(moves) or len(moves) == GOMOKU_BOARD_SIZE**2:
        return gomoku_response(moves)

    turn = "black" if len(moves) % 2 == 0 else "white"
    if turn == payload.side:
        return gomoku_response(moves)

    user_move = moves[-1] if moves else None
    try:
        row, col = get_rapfi_engine().best_move(
            [
                {"row": move.row, "col": move.col, "player": move.player}
                for move in moves
            ],
            timeout_ms=GOMOKU_SEARCH_MS[payload.difficulty],
            strength_level=GOMOKU_DIFFICULTY_STRENGTH[payload.difficulty],
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        return gomoku_response(
            moves,
            error=f"五子棋引擎暂时不可用：{exc}",
            user_move=user_move,
        )

    if not (0 <= row < GOMOKU_BOARD_SIZE and 0 <= col < GOMOKU_BOARD_SIZE):
        return gomoku_response(
            moves,
            error="五子棋引擎返回了越界坐标，请重试。",
            user_move=user_move,
        )
    if any(move.row == row and move.col == col for move in moves):
        return gomoku_response(
            moves,
            error="五子棋引擎返回了已有棋子的位置，请重试。",
            user_move=user_move,
        )

    if payload.difficulty in GOMOKU_MISTAKE_PERCENT:
        row, col = weakened_gomoku_move(
            moves,
            row,
            col,
            GOMOKU_MISTAKE_PERCENT[payload.difficulty],
            force_mate=True,
        )

    engine_move = GomokuMove(row=row, col=col, player=turn)
    moves.append(engine_move)
    return gomoku_response(
        moves,
        user_move=user_move,
        engine_move=engine_move,
    )
