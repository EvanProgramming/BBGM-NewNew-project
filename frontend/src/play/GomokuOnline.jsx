import { useEffect, useMemo, useRef, useState } from "react";
import { copyTextToClipboard } from "./clipboard.js";
import GomokuBoard from "./GomokuBoard.jsx";
import { postJson, roomSocketUrl } from "./http.js";
import {
  GameControls,
  GameHeader,
  GameOverDialog,
  GameScreen,
  MoveHistory,
} from "./GameShell.jsx";

const SEAT_KEY = "elegram-gomoku-seat";

function coordinate(move) {
  if (!move) return "";
  return `${String.fromCharCode(65 + move.col)}${move.row + 1}`;
}

function resultCopy(result, seat, endReason) {
  if (endReason === "resign") {
    if (result === seat) return "对方认输。你赢了。";
    return "你认输了。";
  }
  if (endReason === "timeout") {
    if (result === seat) return "对方超时。你赢了。";
    return "你超时了。";
  }
  if (result === "draw") return "棋盘已满，和棋。";
  if (result === "black" || result === "white") {
    if (result === seat) return "五子连珠。你赢了。";
    return "五子连珠。对方赢了。";
  }
  return "对局结束。";
}

function formatClock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function loadSeat(code) {
  try {
    const raw = JSON.parse(sessionStorage.getItem(SEAT_KEY) || "null");
    if (raw && raw.code === code && raw.token && raw.seat) return raw;
  } catch {
    /* ignore */
  }
  return null;
}

function saveSeat(payload) {
  sessionStorage.setItem(SEAT_KEY, JSON.stringify(payload));
}

function roomShareUrl(code) {
  const url = new URL(window.location.href);
  url.searchParams.set("game", "gomoku");
  url.searchParams.set("r", code);
  return url.toString();
}

function roomWsUrl(code, token) {
  return roomSocketUrl("gomoku", code, token);
}

export default function GomokuOnline({
  initialCode,
  initialToken = "",
  initialSeat = "",
  createSeat = "black",
  clockEnabled = true,
  onBack,
  onHome,
  onRoomCode,
  onFinish,
  compact = false,
  opponentName = "",
}) {
  const [code, setCode] = useState((initialCode || "").toUpperCase());
  const [seat, setSeat] = useState("");
  const [names, setNames] = useState({ black: "", white: "" });
  const [token, setToken] = useState("");
  const [moves, setMoves] = useState([]);
  const [turn, setTurn] = useState("black");
  const [blackReady, setBlackReady] = useState(false);
  const [whiteReady, setWhiteReady] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [result, setResult] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [overOpen, setOverOpen] = useState(false);
  const [copied, setCopied] = useState("");
  const [connected, setConnected] = useState(false);
  const [endReason, setEndReason] = useState("");
  const [clockLimitMs, setClockLimitMs] = useState(60_000);
  const [displayClockMs, setDisplayClockMs] = useState(60_000);
  const [restartBlack, setRestartBlack] = useState(false);
  const [restartWhite, setRestartWhite] = useState(false);
  const [opponentLeft, setOpponentLeft] = useState(false);
  const socketRef = useRef(null);
  const seatRef = useRef("");
  const pendingRef = useRef(null);
  const applyStateRef = useRef(null);

  useEffect(() => {
    if (gameOver) onFinish?.({ seat, result });
  }, [gameOver, onFinish, seat, result]);
  const clockSyncRef = useRef({ remain: 60_000, at: 0, running: false });

  function rollbackPending() {
    const pending = pendingRef.current;
    if (!pending) return;
    pendingRef.current = null;
    setMoves((prev) =>
      prev.filter(
        (move) => !(move.row === pending.row && move.col === pending.col),
      ),
    );
    setTurn(seatRef.current);
  }

  function applyState(data) {
    if (data?.type === "error" || data?.status === "error") {
      rollbackPending();
      setErrorMessage(data?.error_message || "房间状态异常。");
      return;
    }
    if (Array.isArray(data.moves) && pendingRef.current) {
      const pending = pendingRef.current;
      const confirmed = data.moves.some(
        (move) =>
          move.row === pending.row &&
          move.col === pending.col &&
          move.player === pending.player,
      );
      if (!confirmed) {
        if (data.code) setCode(data.code);
        setNames({
          black: data.black_name || "",
          white: data.white_name || "",
        });
        setBlackReady(Boolean(data.black_ready));
        setWhiteReady(Boolean(data.white_ready));
        setRestartBlack(Boolean(data.restart_black));
        setRestartWhite(Boolean(data.restart_white));
        return;
      }
      pendingRef.current = null;
    }
    if (data.code) setCode(data.code);
    setNames({
      black: data.black_name || "",
      white: data.white_name || "",
    });
    if (Array.isArray(data.moves)) setMoves(data.moves);
    if (data.turn !== undefined) setTurn(data.turn || "");
    setBlackReady(Boolean(data.black_ready));
    setWhiteReady(Boolean(data.white_ready));
    setRestartBlack(Boolean(data.restart_black));
    setRestartWhite(Boolean(data.restart_white));
    setGameOver(Boolean(data.game_over));
    setResult(data.result || "");
    setEndReason(data.end_reason || "");
    const limit =
      typeof data.clock_limit_ms === "number" ? data.clock_limit_ms : clockLimitMs;
    if (typeof data.clock_limit_ms === "number") {
      setClockLimitMs(data.clock_limit_ms);
    }
    if (typeof data.clock_ms === "number") {
      setDisplayClockMs(data.clock_ms);
      clockSyncRef.current = {
        remain: data.clock_ms,
        at: performance.now(),
        running:
          Boolean(data.black_ready) &&
          Boolean(data.white_ready) &&
          !data.game_over &&
          limit > 0,
      };
    }
    if (data.error_message) setErrorMessage(data.error_message);
    else setErrorMessage("");
    if (data.game_over) setOverOpen(true);
    else setOverOpen(false);
  }

  applyStateRef.current = applyState;

  useEffect(() => {
    const timer = window.setInterval(() => {
      const sync = clockSyncRef.current;
      if (!sync.running) return;
      const remain = Math.max(0, sync.remain - (performance.now() - sync.at));
      setDisplayClockMs(remain);
    }, 200);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const saved = loadSeat((initialCode || "").toUpperCase());

    (async () => {
      try {
        let data;
        if (initialCode) {
          data = await postJson(
            `/gomoku/rooms/${encodeURIComponent(initialCode)}/join`,
            { token: initialToken || saved?.token || "" },
          );
        } else {
          data = await postJson("/gomoku/rooms", {
            seat: createSeat === "white" ? "white" : "black",
            clock: clockEnabled !== false,
          });
        }
        if (cancelled) return;
        if (data.status !== "success" || !data.token || !data.code) {
          setErrorMessage(data.error_message || "无法进入房间。");
          return;
        }
        setToken(data.token);
        setSeat(initialSeat || data.seat);
        seatRef.current = initialSeat || data.seat;
        setCode(data.code);
        saveSeat({ code: data.code, token: data.token, seat: data.seat });
        onRoomCode?.(data.code);
        applyStateRef.current?.(data);

        const socket = new WebSocket(roomWsUrl(data.code, data.token));
        socketRef.current = socket;
        socket.onopen = () => {
          if (!cancelled) setConnected(true);
        };
        socket.onmessage = (event) => {
          try {
            applyStateRef.current?.(JSON.parse(event.data));
          } catch {
            setErrorMessage("房间消息无法解析。");
          }
        };
        socket.onclose = () => {
          if (!cancelled) setConnected(false);
        };
        socket.onerror = () => {
          if (!cancelled) setErrorMessage("房间连接失败，请确认后端已启动。");
        };
      } catch {
        if (!cancelled) setErrorMessage("连不上房间服务，请确认后端已启动。");
      }
    })();

    return () => {
      cancelled = true;
      socketRef.current?.close();
      socketRef.current = null;
    };
    // Enter the room once per invite/create; parent callback is not a dep.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCode]);

  const bothReady = blackReady && whiteReady;
  const myTurn = bothReady && !gameOver && turn === seat;
  const myRestart = seat === "white" ? restartWhite : restartBlack;
  const oppRestart = seat === "white" ? restartBlack : restartWhite;
  const shareUrl = code ? roomShareUrl(code) : "";

  useEffect(() => {
    if (!compact) return;
    if (!gameOver) {
      setOpponentLeft(false);
      return;
    }
    if (!myRestart || oppRestart) return;
    const timer = window.setTimeout(() => setOpponentLeft(true), 2000);
    return () => window.clearTimeout(timer);
  }, [compact, gameOver, myRestart, oppRestart]);

  function rematchLabel() {
    if (compact && opponentLeft) return "对方离开了";
    if (myRestart && !oppRestart) return "已申请，等待对方";
    if (oppRestart && !myRestart) return "同意再来一局";
    return gameOver ? "再来一局" : "重新开局";
  }

  function rematchHint() {
    if (myRestart && !oppRestart) return "已申请再来一局，等待对方同意。";
    if (oppRestart && !myRestart) return "对方想再来一局。点同意后开下。";
    return "";
  }

  const history = useMemo(() => {
    const rows = [];
    for (let index = 0; index < moves.length; index += 2) {
      rows.push({
        number: index / 2 + 1,
        black: coordinate(moves[index]),
        white: coordinate(moves[index + 1]),
      });
    }
    return rows;
  }, [moves]);

  function send(payload) {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setErrorMessage("房间未连接。");
      return;
    }
    socket.send(JSON.stringify(payload));
  }

  function handlePointClick(row, col) {
    if (!myTurn || pendingRef.current) return;
    if (moves.some((move) => move.row === row && move.col === col)) return;
    const move = { row, col, player: seat };
    pendingRef.current = move;
    setMoves((prev) => [...prev, move]);
    setTurn(seat === "black" ? "white" : "black");
    clockSyncRef.current = {
      remain: clockLimitMs,
      at: performance.now(),
      running: clockLimitMs > 0,
    };
    if (clockLimitMs > 0) setDisplayClockMs(clockLimitMs);
    setErrorMessage("");
    send({ type: "move", row, col });
  }

  function handleRestart() {
    if (myRestart) return;
    pendingRef.current = null;
    if (seat === "white") setRestartWhite(true);
    else setRestartBlack(true);
    send({ type: "restart" });
  }

  function handleResign() {
    if (!bothReady || gameOver) return;
    send({ type: "resign" });
  }

  function forfeitIfNeeded() {
    if (!compact || !bothReady || gameOver) return;
    handleResign();
    const winner = seat === "black" ? "white" : "black";
    onFinish?.({ seat, result: winner });
  }

  function handleLeave() {
    forfeitIfNeeded();
    if (compact && onHome) onHome();
    else onBack?.();
  }

  function handleGoHome() {
    forfeitIfNeeded();
    onHome?.();
  }

  async function copyText(label, value) {
    try {
      await copyTextToClipboard(value);
      setCopied(label);
      setErrorMessage("");
      setTimeout(() => setCopied(""), 1500);
    } catch {
      setErrorMessage("无法复制，请手动选中下面的链接。");
    }
  }

  const rematchLine = rematchHint();
  const statusLine = !token
    ? errorMessage || "正在进入房间…"
    : rematchLine
      ? rematchLine
      : gameOver
        ? resultCopy(result, seat, endReason)
        : !bothReady
          ? "把房间码或链接发给对方。对方加入后开下。"
          : !connected
            ? "连接断开，请刷新页面。"
            : myTurn
              ? "轮到你走。"
              : "轮到对方。";

  return (
    <GameScreen
      header={
        <GameHeader
          onBack={handleLeave}
          onHome={handleGoHome}
          backLabel="返回"
          slogan={
            compact
              ? ""
              : seat === "white"
                ? "你执白。把链接发给对方，对方执黑先走。"
                : "你执黑。把链接发给对方，对方执白。"
          }
        />
      }
      board={
        <GomokuBoard
          moves={moves}
          disabled={!myTurn}
          onPointClick={handlePointClick}
          animateLast={moves.length > 0}
        />
      }
      panel={
        compact ? (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex min-h-0 flex-1 flex-col justify-center">
              <p className="text-xs font-semibold tracking-wide text-muted">
                对手
              </p>
              <p className="mt-1 text-2xl font-bold text-ink">
                {opponentName || (seat === "white" ? names.black : names.white) || "对手"}
              </p>
              {bothReady && clockLimitMs > 0 ? (
                <div className="mt-6 flex items-baseline justify-between rounded-lg border border-line bg-page px-3 py-2">
                  <span className="text-xs font-semibold tracking-wide text-muted">
                    {gameOver ? "步时" : myTurn ? "你的步时" : "对方步时"}
                  </span>
                  <span
                    className={`font-mono text-2xl tabular-nums ${
                      !gameOver && displayClockMs <= 10_000
                        ? "text-red-600"
                        : "text-ink"
                    }`}
                  >
                    {formatClock(gameOver ? 0 : displayClockMs)}
                  </span>
                </div>
              ) : (
                <p className="mt-6 text-sm text-muted">等待开局…</p>
              )}
            </div>
            <button
              type="button"
              onClick={handleResign}
              disabled={!token || !bothReady || gameOver}
              className="mt-4 w-full rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink disabled:opacity-50"
            >
              认输
            </button>
          </div>
        ) : (
        <>
          <p className="text-sm leading-relaxed text-ink">{statusLine}</p>
          <div className="mt-3 text-sm text-muted">
            15×15 自由规则 · 你执{seat === "white" ? "白" : "黑"}
            {names[seat] ? ` ${names[seat]}` : ""}
            {bothReady
              ? ` · 对方 ${(seat === "white" ? names.black : names.white) || "已加入"}`
              : " · 等待对方"}
            {bothReady
              ? clockLimitMs > 0
                ? ` · 每手 ${Math.round(clockLimitMs / 1000)} 秒`
                : " · 不限时"
              : ""}
          </div>
          {bothReady && clockLimitMs > 0 ? (
            <div className="mt-3 flex items-baseline justify-between rounded-lg border border-line bg-page px-3 py-2">
              <span className="text-xs font-semibold tracking-wide text-muted">
                {gameOver ? "步时" : myTurn ? "你的步时" : "对方步时"}
              </span>
              <span
                className={`font-mono text-2xl tabular-nums ${
                  !gameOver && displayClockMs <= 10_000
                    ? "text-red-600"
                    : "text-ink"
                }`}
              >
                {formatClock(gameOver ? 0 : displayClockMs)}
              </span>
            </div>
          ) : null}
          {code ? (
            <div className="mt-4 rounded-lg border border-line bg-page px-3 py-3">
              <p className="text-xs font-semibold tracking-wide text-muted">
                房间码
              </p>
              <p className="mt-1 font-mono text-2xl tracking-[0.3em] text-ink">
                {code}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => copyText("code", code)}
                  className="rounded-lg border border-line px-3 py-1.5 text-sm"
                >
                  {copied === "code" ? "已复制" : "复制房间码"}
                </button>
                <button
                  type="button"
                  onClick={() => copyText("link", shareUrl)}
                  className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white"
                >
                  {copied === "link" ? "已复制" : "复制链接"}
                </button>
              </div>
              <p className="mt-2 break-all font-mono text-xs leading-relaxed text-muted select-all">
                {shareUrl}
              </p>
            </div>
          ) : null}
          {errorMessage ? (
            <p className="mt-3 text-sm text-red-600">{errorMessage}</p>
          ) : null}
          <GameControls>
            <button
              type="button"
              onClick={handleResign}
              disabled={!token || !bothReady || gameOver}
              className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink disabled:opacity-50"
            >
              认输
            </button>
            <button
              type="button"
              onClick={handleRestart}
              disabled={!token || !bothReady || myRestart}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {rematchLabel()}
            </button>
          </GameControls>
          <MoveHistory title="着法" empty="还没有落子。">
            {history.length === 0 ? null : (
              <ol className="mt-2 space-y-1 font-mono text-sm">
                {history.map((row) => (
                  <li key={row.number}>
                    {row.number}. {row.black} {row.white}
                  </li>
                ))}
              </ol>
            )}
          </MoveHistory>
        </>
        )
      }
      modal={
        overOpen ? (
          <GameOverDialog
            title="对局结束"
            message={
              compact && opponentLeft
                ? `${resultCopy(result, seat, endReason)} 对方离开了。`
                : rematchLine
                  ? `${resultCopy(result, seat, endReason)} ${rematchLine}`
                  : resultCopy(result, seat, endReason)
            }
            onRestart={handleRestart}
            onDismiss={() => setOverOpen(false)}
            onBack={onBack}
            onHome={onHome}
            restartLabel={rematchLabel()}
            restartDisabled={
              !token || !bothReady || myRestart || (compact && opponentLeft)
            }
          />
        ) : null
      }
    />
  );
}
