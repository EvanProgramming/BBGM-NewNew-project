import asyncio
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from deps import get_current_user
from games.access import websocket_user
from models import User

BOARD_SIZE = 15
ROOM_TTL_SECONDS = 2 * 60 * 60
CLOCK_LIMIT_MS = 60 * 1000
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4

router = APIRouter()


class GomokuRoomMove(BaseModel):
    row: int = Field(ge=0, lt=BOARD_SIZE)
    col: int = Field(ge=0, lt=BOARD_SIZE)
    player: Literal["black", "white"]


class CreateRoomRequest(BaseModel):
    seat: Literal["black", "white"] = "black"
    clock: bool = True


class JoinRoomRequest(BaseModel):
    token: str = ""


class RoomMoveRequest(BaseModel):
    row: int = Field(ge=0, lt=BOARD_SIZE)
    col: int = Field(ge=0, lt=BOARD_SIZE)


class RoomResponse(BaseModel):
    status: Literal["success", "error"]
    error_message: str
    code: str = ""
    seat: Literal["black", "white", ""] = ""
    token: str = ""
    black_ready: bool = False
    white_ready: bool = False
    moves: list[GomokuRoomMove] = Field(default_factory=list)
    turn: Literal["black", "white", ""] = ""
    game_over: bool = False
    result: Literal["black", "white", "draw", ""] = ""
    end_reason: Literal["", "five", "draw", "resign", "timeout"] = ""
    clock_ms: int = CLOCK_LIMIT_MS
    clock_limit_ms: int = CLOCK_LIMIT_MS
    restart_black: bool = False
    restart_white: bool = False
    black_name: str = ""
    white_name: str = ""


def _winner(moves: list[dict]) -> str:
    occupied = {(move["row"], move["col"]): move["player"] for move in moves}
    for move in moves:
        for row_step, col_step in ((1, 0), (0, 1), (1, 1), (1, -1)):
            count = 1
            for direction in (-1, 1):
                row = move["row"] + row_step * direction
                col = move["col"] + col_step * direction
                while occupied.get((row, col)) == move["player"]:
                    count += 1
                    row += row_step * direction
                    col += col_step * direction
            if count >= 5:
                return move["player"]
    return ""


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


class Room:
    def __init__(
        self,
        code: str,
        creator_seat: str,
        token: str,
        clock_limit_ms: int = CLOCK_LIMIT_MS,
    ):
        self.code = code
        self.black_token = token if creator_seat == "black" else None
        self.white_token = token if creator_seat == "white" else None
        self.moves: list[dict] = []
        self.last_active = time.monotonic()
        self.sockets: set[WebSocket] = set()
        self.ended_by: str = ""
        self.winner: str = ""
        self.turn_started = time.monotonic()
        self.clock_gen = 0
        self.clock_task: asyncio.Task | None = None
        self.clock_limit_ms = clock_limit_ms if clock_limit_ms > 0 else 0
        self.restart_black = False
        self.restart_white = False
        self.names = {"black": "", "white": ""}

    def both_ready(self) -> bool:
        return bool(self.black_token and self.white_token)

    def touch(self) -> None:
        self.last_active = time.monotonic()

    def seat_for(self, token: str) -> str:
        if token and token == self.black_token:
            return "black"
        if token and token == self.white_token:
            return "white"
        return ""

    def reset_board(self) -> None:
        self.moves = []
        self.ended_by = ""
        self.winner = ""
        self.turn_started = time.monotonic()
        self.restart_black = False
        self.restart_white = False

    def clock_ms(self) -> int:
        if self.clock_limit_ms <= 0 or self.ended_by or not self.both_ready():
            return self.clock_limit_ms
        elapsed = int((time.monotonic() - self.turn_started) * 1000)
        return max(0, self.clock_limit_ms - elapsed)

    def snapshot(self) -> dict:
        winner = _winner(self.moves)
        full = len(self.moves) == BOARD_SIZE * BOARD_SIZE
        if self.ended_by:
            game_over = True
            result = self.winner
            end_reason = self.ended_by
        elif winner:
            game_over = True
            result = winner
            end_reason = "five"
        elif full:
            game_over = True
            result = "draw"
            end_reason = "draw"
        else:
            game_over = False
            result = ""
            end_reason = ""
        turn = "" if game_over else ("black" if len(self.moves) % 2 == 0 else "white")
        return {
            "type": "state",
            "status": "success",
            "error_message": "",
            "code": self.code,
            "black_ready": bool(self.black_token),
            "white_ready": bool(self.white_token),
            "moves": list(self.moves),
            "turn": turn,
            "game_over": game_over,
            "result": result,
            "end_reason": end_reason,
            "clock_ms": 0 if game_over else self.clock_ms(),
            "clock_limit_ms": self.clock_limit_ms,
            "restart_black": self.restart_black,
            "restart_white": self.restart_white,
            "black_name": self.names.get("black", ""),
            "white_name": self.names.get("white", ""),
        }


class RoomStore:
    def __init__(self):
        self._rooms: dict[str, Room] = {}
        self._lock = asyncio.Lock()

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [
            code
            for code, room in self._rooms.items()
            if now - room.last_active > ROOM_TTL_SECONDS
        ]
        for code in expired:
            self._rooms.pop(code, None)

    async def create(self, seat: str = "black", clock: bool = True, name: str = "") -> tuple[Room, str, str]:
        creator_seat = seat if seat in {"black", "white"} else "black"
        clock_limit_ms = CLOCK_LIMIT_MS if clock else 0
        async with self._lock:
            self._purge()
            for _ in range(20):
                code = _new_code()
                if code not in self._rooms:
                    token = secrets.token_urlsafe(16)
                    room = Room(code, creator_seat, token, clock_limit_ms)
                    room.names[creator_seat] = name
                    self._rooms[code] = room
                    return room, token, creator_seat
            raise RuntimeError("无法分配房间码")

    async def get(self, code: str) -> Room | None:
        async with self._lock:
            self._purge()
            return self._rooms.get(code.upper())

    async def join(self, code: str, token: str, name: str = "") -> tuple[Room | None, str, str]:
        async with self._lock:
            self._purge()
            room = self._rooms.get(code.upper())
            if room is None:
                return None, "", ""
            room.touch()
            existing = room.seat_for(token)
            if existing:
                if name:
                    room.names[existing] = name
                return room, existing, token
            if room.black_token is None:
                black_token = secrets.token_urlsafe(16)
                room.black_token = black_token
                room.names["black"] = name
                return room, "black", black_token
            if room.white_token is None:
                white_token = secrets.token_urlsafe(16)
                room.white_token = white_token
                room.names["white"] = name
                return room, "white", white_token
            return room, "", ""


store = RoomStore()


def _response(
    room: Room | None,
    *,
    error: str = "",
    seat: str = "",
    token: str = "",
) -> RoomResponse:
    if room is None:
        return RoomResponse(status="error", error_message=error or "房间不存在。")
    data = room.snapshot()
    return RoomResponse(
        status="error" if error else "success",
        error_message=error,
        code=data["code"],
        seat=seat,
        token=token,
        black_ready=data["black_ready"],
        white_ready=data["white_ready"],
        moves=[GomokuRoomMove(**move) for move in data["moves"]],
        turn=data["turn"],
        game_over=data["game_over"],
        result=data["result"],
        end_reason=data["end_reason"],
        clock_ms=data["clock_ms"],
        clock_limit_ms=data["clock_limit_ms"],
        restart_black=data["restart_black"],
        restart_white=data["restart_white"],
        black_name=data["black_name"],
        white_name=data["white_name"],
    )


def _cancel_clock(room: Room) -> None:
    task = room.clock_task
    room.clock_task = None
    if task and not task.done():
        task.cancel()


async def _arm_clock(room: Room) -> None:
    _cancel_clock(room)
    if room.ended_by or not room.both_ready() or room.clock_limit_ms <= 0:
        return
    if _winner(room.moves) or len(room.moves) == BOARD_SIZE * BOARD_SIZE:
        return
    room.turn_started = time.monotonic()
    room.clock_gen += 1
    gen = room.clock_gen

    async def _timeout() -> None:
        try:
            await asyncio.sleep(room.clock_limit_ms / 1000)
        except asyncio.CancelledError:
            return
        async with store._lock:
            if room.clock_gen != gen or room.ended_by or not room.both_ready():
                return
            room.ended_by = "timeout"
            room.winner = "white" if len(room.moves) % 2 == 0 else "black"
        await _broadcast(room)

    room.clock_task = asyncio.create_task(_timeout())


async def _broadcast(room: Room, extra: dict | None = None) -> None:
    payload = extra or room.snapshot()
    dead: list[WebSocket] = []
    for socket in list(room.sockets):
        try:
            await socket.send_json(payload)
        except Exception:
            dead.append(socket)
    for socket in dead:
        room.sockets.discard(socket)


@router.post("/api/v1/games/gomoku/rooms", response_model=RoomResponse)
async def create_room(
    payload: CreateRoomRequest = CreateRoomRequest(),
    user: User = Depends(get_current_user),
) -> RoomResponse:
    seat = payload.seat
    try:
        room, token, creator_seat = await store.create(
            seat, clock=payload.clock, name=user.display_name
        )
    except RuntimeError as exc:
        return RoomResponse(status="error", error_message=str(exc))
    return _response(room, seat=creator_seat, token=token)


@router.get("/api/v1/games/gomoku/rooms/{code}", response_model=RoomResponse)
async def get_room(
    code: str,
    token: str = "",
    _: User = Depends(get_current_user),
) -> RoomResponse:
    room = await store.get(code)
    if room is None:
        return _response(None, error="房间不存在或已过期。")
    seat = room.seat_for(token)
    return _response(room, seat=seat, token=token if seat else "")


@router.post("/api/v1/games/gomoku/rooms/{code}/join", response_model=RoomResponse)
async def join_room(
    code: str,
    payload: JoinRoomRequest,
    user: User = Depends(get_current_user),
) -> RoomResponse:
    room, seat, token = await store.join(
        code, (payload.token or "").strip(), name=user.display_name
    )
    if room is None:
        return _response(None, error="房间不存在或已过期。")
    if not seat:
        return _response(room, error="房间已满。")
    just_filled = (
        room.both_ready()
        and not room.ended_by
        and not room.moves
        and (room.clock_task is None or room.clock_task.done())
    )
    if just_filled:
        await _arm_clock(room)
    await _broadcast(room)
    return _response(room, seat=seat, token=token)


@router.websocket("/api/v1/games/gomoku/rooms/{code}/ws")
async def room_socket(websocket: WebSocket, code: str, token: str = "") -> None:
    if websocket_user(websocket) is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "请先登录。"})
        await websocket.close()
        return
    room = await store.get(code)
    seat = room.seat_for(token) if room else ""
    if room is None or not seat:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "status": "error",
                "error_message": "无法进入房间，请检查链接或房间码。",
            }
        )
        await websocket.close()
        return

    await websocket.accept()
    room.sockets.add(websocket)
    room.touch()
    await _broadcast(room)

    try:
        while True:
            message = await websocket.receive_json()
            room.touch()
            kind = message.get("type") if isinstance(message, dict) else ""
            if kind == "move":
                async with store._lock:
                    error = _apply_move(room, seat, message)
                if error:
                    await websocket.send_json(
                        {"type": "error", "status": "error", "error_message": error}
                    )
                    continue
                await _arm_clock(room)
                await _broadcast(room)
            elif kind == "resign":
                async with store._lock:
                    error = _apply_resign(room, seat)
                if error:
                    await websocket.send_json(
                        {"type": "error", "status": "error", "error_message": error}
                    )
                    continue
                _cancel_clock(room)
                await _broadcast(room)
            elif kind == "restart":
                async with store._lock:
                    error, started = _apply_restart(room, seat)
                if error:
                    await websocket.send_json(
                        {"type": "error", "status": "error", "error_message": error}
                    )
                    continue
                if started:
                    await _arm_clock(room)
                await _broadcast(room)
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "status": "error",
                        "error_message": "无法识别的消息。",
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        room.sockets.discard(websocket)


def _apply_move(room: Room, seat: str, message: dict) -> str:
    if not room.both_ready():
        return "对方还没加入。"
    state = room.snapshot()
    if state["game_over"]:
        return "对局已经结束。"
    if state["turn"] != seat:
        return "还没轮到你走。"
    try:
        row = int(message.get("row"))
        col = int(message.get("col"))
    except (TypeError, ValueError):
        return "落点无效。"
    if not (0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE):
        return "落点越界。"
    if any(move["row"] == row and move["col"] == col for move in room.moves):
        return "这里已经有子了。"
    room.moves.append({"row": row, "col": col, "player": seat})
    room.restart_black = False
    room.restart_white = False
    return ""


def _apply_restart(room: Room, seat: str) -> tuple[str, bool]:
    if not room.both_ready():
        return "对方还没加入。", False
    if seat == "black":
        room.restart_black = True
    elif seat == "white":
        room.restart_white = True
    else:
        return "无法认座。", False
    if room.restart_black and room.restart_white:
        room.reset_board()
        return "", True
    return "", False


def _apply_resign(room: Room, seat: str) -> str:
    if not room.both_ready():
        return "对方还没加入。"
    state = room.snapshot()
    if state["game_over"]:
        return "对局已经结束。"
    room.ended_by = "resign"
    room.winner = "white" if seat == "black" else "black"
    return ""
