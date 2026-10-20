"""Shared in-memory rooms for UCI board games (chess, xiangqi)."""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Literal, Protocol

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from deps import get_current_user
from games.access import websocket_user
from models import User

ROOM_TTL_SECONDS = 2 * 60 * 60
CLOCK_LIMIT_MS = 60 * 1000
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4


class BoardRules(Protocol):
    game: str
    first: str
    second: str
    start_fen: str

    def turn(self, fen: str) -> str: ...
    def legal_uci(self, fen: str) -> list[str]: ...
    def play(self, fen: str, uci: str) -> tuple[str, str, str]: ...
    def outcome(self, fen: str) -> tuple[bool, str, str]: ...
    def move_squares(self, uci: str) -> tuple[str, str]: ...


class CreateRoomRequest(BaseModel):
    seat: str = ""
    clock: bool = True


class JoinRoomRequest(BaseModel):
    token: str = ""


class BoardRoomResponse(BaseModel):
    status: Literal["success", "error"]
    error_message: str
    code: str = ""
    seat: str = ""
    token: str = ""
    fen: str = ""
    turn: str = ""
    legal_uci: list[str] = Field(default_factory=list)
    sans: list[str] = Field(default_factory=list)
    from_square: str = ""
    to_square: str = ""
    last_uci: str = ""
    game_over: bool = False
    result: str = ""
    end_reason: Literal["", "mate", "draw", "resign", "timeout"] = ""
    clock_ms: int = CLOCK_LIMIT_MS
    clock_limit_ms: int = CLOCK_LIMIT_MS
    white_ready: bool = False
    black_ready: bool = False
    red_ready: bool = False
    restart_white: bool = False
    restart_black: bool = False
    restart_red: bool = False
    black_name: str = ""
    white_name: str = ""


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


class BoardRoom:
    def __init__(
        self,
        code: str,
        creator_seat: str,
        token: str,
        rules: BoardRules,
        clock_limit_ms: int = CLOCK_LIMIT_MS,
    ):
        self.code = code
        self.rules = rules
        self.tokens = {rules.first: None, rules.second: None}
        if creator_seat not in self.tokens:
            creator_seat = rules.first
        self.tokens[creator_seat] = token
        self.fen = rules.start_fen
        self.sans: list[str] = []
        self.last_active = time.monotonic()
        self.sockets: set[WebSocket] = set()
        self.ended_by = ""
        self.winner = ""
        self.from_square = ""
        self.to_square = ""
        self.last_uci = ""
        self.turn_started = time.monotonic()
        self.clock_gen = 0
        self.clock_task: asyncio.Task | None = None
        self.clock_limit_ms = clock_limit_ms if clock_limit_ms > 0 else 0
        self.restart = {rules.first: False, rules.second: False}
        self.names = {rules.first: "", rules.second: ""}

    def both_ready(self) -> bool:
        return all(self.tokens.values())

    def touch(self) -> None:
        self.last_active = time.monotonic()

    def seat_for(self, token: str) -> str:
        if not token:
            return ""
        for seat, stored in self.tokens.items():
            if stored and stored == token:
                return seat
        return ""

    def reset_board(self) -> None:
        self.fen = self.rules.start_fen
        self.sans = []
        self.ended_by = ""
        self.winner = ""
        self.from_square = ""
        self.to_square = ""
        self.last_uci = ""
        self.turn_started = time.monotonic()
        self.restart = {self.rules.first: False, self.rules.second: False}

    def clock_ms(self) -> int:
        if self.clock_limit_ms <= 0 or self.ended_by or not self.both_ready():
            return self.clock_limit_ms
        elapsed = int((time.monotonic() - self.turn_started) * 1000)
        return max(0, self.clock_limit_ms - elapsed)

    def snapshot(self) -> dict:
        over, result, end_reason = self.rules.outcome(self.fen)
        if self.ended_by:
            over = True
            result = self.winner
            end_reason = self.ended_by
        turn = "" if over else self.rules.turn(self.fen)
        ready = {
            "white_ready": False,
            "black_ready": False,
            "red_ready": False,
            "restart_white": False,
            "restart_black": False,
            "restart_red": False,
        }
        for seat, token in self.tokens.items():
            ready[f"{seat}_ready"] = bool(token)
            ready[f"restart_{seat}"] = bool(self.restart.get(seat))
        return {
            "type": "state",
            "status": "success",
            "error_message": "",
            "code": self.code,
            "fen": self.fen,
            "turn": turn,
            "legal_uci": [] if over else self.rules.legal_uci(self.fen),
            "sans": list(self.sans),
            "from_square": self.from_square,
            "to_square": self.to_square,
            "last_uci": self.last_uci,
            "game_over": over,
            "result": result,
            "end_reason": end_reason,
            "clock_ms": 0 if over else self.clock_ms(),
            "clock_limit_ms": self.clock_limit_ms,
            "black_name": self.names.get("black", ""),
            "white_name": self.names.get("white", ""),
            **ready,
        }


class RoomStore:
    def __init__(self, rules: BoardRules):
        self.rules = rules
        self._rooms: dict[str, BoardRoom] = {}
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

    async def create(self, seat: str, clock: bool = True, name: str = "") -> tuple[BoardRoom, str, str]:
        creator = seat if seat in {self.rules.first, self.rules.second} else self.rules.first
        clock_limit_ms = CLOCK_LIMIT_MS if clock else 0
        async with self._lock:
            self._purge()
            for _ in range(20):
                code = _new_code()
                if code not in self._rooms:
                    token = secrets.token_urlsafe(16)
                    room = BoardRoom(code, creator, token, self.rules, clock_limit_ms)
                    room.names[creator] = name
                    self._rooms[code] = room
                    return room, token, creator
            raise RuntimeError("无法分配房间码")

    async def get(self, code: str) -> BoardRoom | None:
        async with self._lock:
            self._purge()
            return self._rooms.get(code.upper())

    async def join(self, code: str, token: str, name: str = "") -> tuple[BoardRoom | None, str, str]:
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
            for seat in (self.rules.first, self.rules.second):
                if room.tokens[seat] is None:
                    next_token = secrets.token_urlsafe(16)
                    room.tokens[seat] = next_token
                    room.names[seat] = name
                    return room, seat, next_token
            return room, "", ""


def _response(
    room: BoardRoom | None,
    *,
    error: str = "",
    seat: str = "",
    token: str = "",
) -> BoardRoomResponse:
    if room is None:
        return BoardRoomResponse(status="error", error_message=error or "房间不存在。")
    data = room.snapshot()
    return BoardRoomResponse(
        status="error" if error else "success",
        error_message=error,
        code=data["code"],
        seat=seat,
        token=token,
        fen=data["fen"],
        turn=data["turn"],
        legal_uci=data["legal_uci"],
        sans=data["sans"],
        from_square=data["from_square"],
        to_square=data["to_square"],
        last_uci=data.get("last_uci", ""),
        game_over=data["game_over"],
        result=data["result"],
        end_reason=data["end_reason"],
        clock_ms=data["clock_ms"],
        clock_limit_ms=data["clock_limit_ms"],
        white_ready=data["white_ready"],
        black_ready=data["black_ready"],
        red_ready=data["red_ready"],
        restart_white=data["restart_white"],
        restart_black=data["restart_black"],
        restart_red=data["restart_red"],
        black_name=data["black_name"],
        white_name=data["white_name"],
    )


def build_board_room_router(rules: BoardRules) -> APIRouter:
    router = APIRouter()
    store = RoomStore(rules)
    prefix = f"/api/v1/games/{rules.game}/rooms"

    def _cancel_clock(room: BoardRoom) -> None:
        task = room.clock_task
        room.clock_task = None
        if task and not task.done():
            task.cancel()

    async def _arm_clock(room: BoardRoom) -> None:
        _cancel_clock(room)
        if room.ended_by or not room.both_ready() or room.clock_limit_ms <= 0:
            return
        over, _result, _reason = rules.outcome(room.fen)
        if over:
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
                mover = rules.turn(room.fen)
                room.winner = rules.second if mover == rules.first else rules.first
            await _broadcast(room)

        room.clock_task = asyncio.create_task(_timeout())

    async def _broadcast(room: BoardRoom, extra: dict | None = None) -> None:
        payload = extra or room.snapshot()
        dead: list[WebSocket] = []
        for socket in list(room.sockets):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            room.sockets.discard(socket)

    def _apply_move(room: BoardRoom, seat: str, message: dict) -> str:
        if not room.both_ready():
            return "对方还没加入。"
        state = room.snapshot()
        if state["game_over"]:
            return "对局已经结束。"
        if state["turn"] != seat:
            return "还没轮到你走。"
        uci = str(message.get("uci") or "").strip().lower()
        new_fen, san, error = rules.play(room.fen, uci)
        if error:
            return error
        room.fen = new_fen
        room.sans.append(san)
        squares = getattr(rules, "move_squares", None)
        if callable(squares):
            room.from_square, room.to_square = squares(uci)
        else:
            room.from_square = uci[:2] if len(uci) >= 4 else ""
            room.to_square = uci[2:4] if len(uci) >= 4 else ""
        room.last_uci = uci
        room.restart = {rules.first: False, rules.second: False}
        return ""

    def _apply_resign(room: BoardRoom, seat: str) -> str:
        if not room.both_ready():
            return "对方还没加入。"
        if room.snapshot()["game_over"]:
            return "对局已经结束。"
        room.ended_by = "resign"
        room.winner = rules.second if seat == rules.first else rules.first
        return ""

    def _apply_restart(room: BoardRoom, seat: str) -> tuple[str, bool]:
        if not room.both_ready():
            return "对方还没加入。", False
        if seat not in room.restart:
            return "无法认座。", False
        room.restart[seat] = True
        if all(room.restart.values()):
            room.reset_board()
            return "", True
        return "", False

    @router.post(prefix, response_model=BoardRoomResponse)
    async def create_room(
        payload: CreateRoomRequest = CreateRoomRequest(),
        user: User = Depends(get_current_user),
    ) -> BoardRoomResponse:
        try:
            room, token, creator_seat = await store.create(
                payload.seat, clock=payload.clock, name=user.display_name
            )
        except RuntimeError as exc:
            return BoardRoomResponse(status="error", error_message=str(exc))
        return _response(room, seat=creator_seat, token=token)

    @router.get(prefix + "/{code}", response_model=BoardRoomResponse)
    async def get_room(
        code: str,
        token: str = "",
        _: User = Depends(get_current_user),
    ) -> BoardRoomResponse:
        room = await store.get(code)
        if room is None:
            return _response(None, error="房间不存在或已过期。")
        seat = room.seat_for(token)
        return _response(room, seat=seat, token=token if seat else "")

    @router.post(prefix + "/{code}/join", response_model=BoardRoomResponse)
    async def join_room(
        code: str,
        payload: JoinRoomRequest,
        user: User = Depends(get_current_user),
    ) -> BoardRoomResponse:
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
            and not room.sans
            and (room.clock_task is None or room.clock_task.done())
        )
        if just_filled:
            await _arm_clock(room)
        await _broadcast(room)
        return _response(room, seat=seat, token=token)

    @router.websocket(prefix + "/{code}/ws")
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

    return router
