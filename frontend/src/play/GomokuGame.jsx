import { useEffect, useMemo, useRef, useState } from "react";
import GomokuBoard from "./GomokuBoard.jsx";
import GomokuOnline from "./GomokuOnline.jsx";
import GameLobby, { useLobbyMode } from "./GameLobby.jsx";
import { gamesUrl } from "./http.js";
import {
  DifficultySelect,
  GameControls,
  GameHeader,
  GameOverDialog,
  GameScreen,
  MoveHistory,
  SideSelect,
} from "./GameShell.jsx";

const GOMOKU_URL = gamesUrl("/gomoku/play");
const FETCH_TIMEOUT_MS = 30000;
const AI_THINK_MIN_MS = 2000;
const AI_THINK_MAX_MS = 4000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function aiThinkMs() {
  return (
    AI_THINK_MIN_MS +
    Math.floor(Math.random() * (AI_THINK_MAX_MS - AI_THINK_MIN_MS + 1))
  );
}

function coordinate(move) {
  if (!move) return "";
  return `${String.fromCharCode(65 + move.col)}${move.row + 1}`;
}

function resultCopy(result, seat) {
  if (result === "draw") return "棋盘已满，和棋。";
  if (result === "black" || result === "white") {
    if (result === seat) return "五子连珠。你赢了。";
    return "五子连珠。电脑赢了。";
  }
  return "对局结束。";
}

async function postGomoku(moves, difficulty, side) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(GOMOKU_URL, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moves, difficulty, side }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function GomokuHeader({ onBack, onHome, seat }) {
  return (
    <GameHeader
      onBack={onBack}
      onHome={onHome}
      slogan={
        seat === "white"
          ? "你执白。电脑先落黑子，再轮到你。"
          : "你执黑。落一子，电脑回一子。"
      }
    />
  );
}

function GomokuGameOver({ result, seat, onRestart, onDismiss, onBack, onHome }) {
  return (
    <GameOverDialog
      title="对局结束"
      message={resultCopy(result, seat)}
      onRestart={onRestart}
      onDismiss={onDismiss}
      onBack={onBack}
      onHome={onHome}
    />
  );
}

function GomokuAiGame({
  onBack,
  onHome,
  initialSeat = "black",
  initialDifficulty = "",
  onFinish,
}) {
  const [seat, setSeat] = useState(initialSeat === "white" ? "white" : "black");
  const [started, setStarted] = useState(false);
  const [moves, setMoves] = useState([]);
  const [phase, setPhase] = useState("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [gameOver, setGameOver] = useState(false);
  const [result, setResult] = useState("");
  const [overOpen, setOverOpen] = useState(false);
  const [difficulty, setDifficulty] = useState(initialDifficulty || "easy");
  const requestGeneration = useRef(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (gameOver) onFinish?.({ seat, result });
  }, [gameOver, onFinish, seat, result]);

  const turn = moves.length % 2 === 0 ? "black" : "white";
  const waitingForEngine = started && turn !== seat && !gameOver;
  const busy = !started || phase !== "idle" || gameOver || waitingForEngine;
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

  function applyResponse(data) {
    if (!data || !Array.isArray(data.moves)) {
      setErrorMessage("五子棋服务返回异常。");
      return;
    }
    setMoves(data.moves);
    setErrorMessage(data.error_message || "");
    setGameOver(Boolean(data.game_over));
    setResult(data.result || "");
    if (data.game_over) setOverOpen(true);
  }

  async function askRapfi(nextMoves, side = seat) {
    const generation = ++requestGeneration.current;
    const startedAt = performance.now();
    const thinkFor = aiThinkMs();
    setPhase("thinking");
    setErrorMessage("");
    try {
      const data = await postGomoku(nextMoves, difficulty, side);
      if (generation !== requestGeneration.current) return;
      const aiReplied =
        Array.isArray(data.moves) && data.moves.length > nextMoves.length;
      if (aiReplied) {
        const remaining = thinkFor - (performance.now() - startedAt);
        if (remaining > 0) await sleep(remaining);
      }
      if (generation !== requestGeneration.current) return;
      applyResponse(data);
    } catch (error) {
      if (generation !== requestGeneration.current) return;
      setErrorMessage(
        error?.name === "AbortError"
          ? "电脑思考超时，请重试。"
          : "连不上五子棋服务，请确认后端已启动。",
      );
    } finally {
      if (generation === requestGeneration.current) setPhase("idle");
    }
  }

  function handlePointClick(row, col) {
    if (busy) return;
    if (moves.some((move) => move.row === row && move.col === col)) return;
    const nextMoves = [...moves, { row, col, player: seat }];
    setMoves(nextMoves);
    askRapfi(nextMoves);
  }

  function handleStart() {
    if (startedRef.current) return;
    startedRef.current = true;
    setStarted(true);
    setErrorMessage("");
    if (seat === "white") {
      askRapfi([], "white");
    }
  }

  function handleRestart(nextSeat = seat) {
    requestGeneration.current += 1;
    startedRef.current = false;
    setStarted(false);
    setSeat(nextSeat);
    setMoves([]);
    setPhase("idle");
    setErrorMessage("");
    setGameOver(false);
    setResult("");
    setOverOpen(false);
  }

  const statusLine = !started
    ? "先选执棋和难度，再点开始游戏。"
    : gameOver
      ? resultCopy(result, seat)
      : phase === "thinking"
        ? "电脑正在想…"
        : waitingForEngine
          ? "轮到电脑。"
          : `轮到你走。点击棋盘交叉点落下${seat === "white" ? "白" : "黑"}子。`;

  return (
    <GameScreen
      header={<GomokuHeader onBack={onBack} onHome={onHome} seat={seat} />}
      board={
        <GomokuBoard
          moves={moves}
          disabled={busy}
          onPointClick={handlePointClick}
          animateLast={moves.length > 0}
        />
      }
      panel={
        <>
          <p className="text-sm leading-relaxed text-ink">
            {statusLine}
          </p>
          <div className="mt-3 text-sm text-muted">
            15×15 自由规则 · 你执{seat === "white" ? "白" : "黑"}
          </div>
          <SideSelect
            value={seat}
            disabled={started}
            options={[
              { id: "black", label: "执黑" },
              { id: "white", label: "执白" },
            ]}
            onChange={setSeat}
          />
          <DifficultySelect
            value={difficulty}
            disabled={started}
            onChange={setDifficulty}
          />
          {started ? (
            <p className="mt-1 text-xs text-muted">对局开始后不能改难度。</p>
          ) : null}
          {errorMessage ? (
            <p className="mt-3 text-sm text-red-600">{errorMessage}</p>
          ) : null}
          <GameControls>
            {started ? (
              <button
                type="button"
                onClick={() => handleRestart()}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white"
              >
                重新开局
              </button>
            ) : (
              <button
                type="button"
                onClick={handleStart}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white"
              >
                开始游戏
              </button>
            )}
            {waitingForEngine && phase === "idle" ? (
              <button
                type="button"
                onClick={() => askRapfi(moves)}
                className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink"
              >
                让电脑走
              </button>
            ) : null}
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
      }
      modal={
        overOpen ? (
          <GomokuGameOver
            result={result}
            seat={seat}
            onRestart={() => handleRestart()}
            onDismiss={() => setOverOpen(false)}
            onBack={onBack}
            onHome={onHome}
          />
        ) : null
      }
    />
  );
}

export default function GomokuGame({
  onBack,
  initialRoomCode = "",
  onRoomCode,
  initialMode = "",
  initialDifficulty = "",
  initialToken = "",
  initialSeat = "",
  onFinish,
  compact = false,
  opponentName = "",
}) {
  const lobby = useLobbyMode({
    initialRoomCode,
    initialMode,
    initialSeat,
    onRoomCode,
    defaultSeat: "black",
  });

  if (lobby.mode === "ai") {
    return (
      <GomokuAiGame
        onBack={() => (onFinish ? onBack() : lobby.setMode(""))}
        onHome={onBack}
        initialSeat={lobby.seat}
        initialDifficulty={initialDifficulty}
        onFinish={onFinish}
      />
    );
  }
  if (lobby.mode === "online") {
    return (
      <GomokuOnline
        initialCode={lobby.roomCode}
        initialToken={initialToken}
        initialSeat={initialSeat}
        createSeat={lobby.seat}
        clockEnabled={lobby.clockEnabled}
        onBack={lobby.leaveRoom}
        onHome={() => {
          lobby.leaveRoom();
          onBack();
        }}
        onRoomCode={onRoomCode}
        onFinish={onFinish}
        compact={compact}
        opponentName={opponentName}
      />
    );
  }

  return (
    <GameLobby
      title="五子棋"
      blurb="自己对电脑，或创建房间把链接发给对方。先选执黑或执白。"
      engineHint={
        lobby.seat === "white" ? "你执白，电脑先走黑" : "你执黑，电脑回一手"
      }
      onlineHint={
        lobby.seat === "white" ? "生成房间码和链接，你执白" : "生成房间码和链接，你执黑"
      }
      seat={lobby.seat}
      seats={[
        { id: "black", label: "执黑" },
        { id: "white", label: "执白" },
      ]}
      onSeat={lobby.setSeat}
      onBack={onBack}
      onAi={() => lobby.setMode("ai")}
      onCreate={lobby.createRoom}
      joinDraft={lobby.joinDraft}
      onJoinDraft={lobby.setJoinDraft}
      onJoin={lobby.joinRoom}
      errorMessage={lobby.lobbyError}
      clockEnabled={lobby.clockEnabled}
      onClockEnabled={lobby.setClockEnabled}
    />
  );
}
