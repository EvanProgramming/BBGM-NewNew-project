import { useEffect, useMemo, useRef, useState } from "react";
import ChessBoard, {
  applyDisplayMove,
  clearSquareFen,
  pieceCodeAt,
} from "./ChessBoard.jsx";
import ChessOnline from "./ChessOnline.jsx";
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

const PLAY_URL = gamesUrl("/chess/play");
const FETCH_TIMEOUT_MS = 30000;
const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const USER_SLIDE_MS = 480;
const ENGINE_PAUSE_MS = 600;
const ENGINE_SLIDE_MS = 900;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function formatEval(n) {
  if (n > 0) return `+${n}`;
  return String(n);
}

function resultCopy(result, seat = "white") {
  if (result === "1-0") {
    return seat === "white" ? "将死。你赢了。" : "将死。电脑赢了。";
  }
  if (result === "0-1") {
    return seat === "black" ? "将死。你赢了。" : "将死。电脑赢了。";
  }
  if (result === "1/2-1/2") return "和棋。";
  return "对局结束。";
}

function pairMoves(sans) {
  const rows = [];
  for (let i = 0; i < sans.length; i += 2) {
    rows.push({
      n: i / 2 + 1,
      white: sans[i],
      black: sans[i + 1] || "",
    });
  }
  return rows;
}

async function postPlay(fen, uci = "", difficulty = "easy", side = "white") {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(PLAY_URL, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fen, uci, difficulty, side }),
      signal: controller.signal,
    });
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function GameOverModal({ result, seat, onRestart, onDismiss, onBack, onHome }) {
  const mate = result === "1-0" || result === "0-1";
  const title = mate ? "将死" : "对局结束";
  return (
    <GameOverDialog
      title={title}
      message={resultCopy(result, seat)}
      onRestart={onRestart}
      onDismiss={onDismiss}
      onBack={onBack}
      onHome={onHome}
    />
  );
}

function BrandStrip({ onBack, onHome, seat }) {
  return (
    <GameHeader
      onBack={onBack}
      onHome={onHome}
      slogan={
        seat === "black"
          ? "你执黑。电脑先走白，再轮到你。"
          : "你执白。走一步，电脑回一步。"
      }
    />
  );
}

function ChessAiGame({
  onBack,
  onHome,
  initialSeat = "white",
  initialDifficulty = "",
  onFinish,
}) {
  const [seat, setSeat] = useState(initialSeat === "black" ? "black" : "white");
  const [fen, setFen] = useState(START_FEN);
  const [legalUci, setLegalUci] = useState([]);
  const [selected, setSelected] = useState("");
  const [fromSquare, setFromSquare] = useState("");
  const [toSquare, setToSquare] = useState("");
  const [evalScore, setEvalScore] = useState(0);
  const [sans, setSans] = useState([]);
  const [phase, setPhase] = useState("idle");
  const [gameOver, setGameOver] = useState(false);
  const [result, setResult] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [turn, setTurn] = useState("white");
  const [flight, setFlight] = useState(null);
  const [overOpen, setOverOpen] = useState(false);
  const [difficulty, setDifficulty] = useState(
    initialDifficulty || "easy",
  );
  const requestGen = useRef(0);

  useEffect(() => {
    if (gameOver) onFinish?.({ seat, result });
  }, [gameOver, onFinish, seat, result]);

  const busy = phase !== "idle" || gameOver;

  const targets = useMemo(() => {
    if (!selected) return [];
    return legalUci
      .filter((uci) => uci.startsWith(selected))
      .map((uci) => uci.slice(2, 4));
  }, [legalUci, selected]);

  function applyMeta(data, { appendSans = false } = {}) {
    if (!data || typeof data !== "object") {
      setErrorMessage("下棋服务返回异常。");
      return;
    }
    if (Array.isArray(data.legal_uci)) setLegalUci(data.legal_uci);
    if (data.turn) setTurn(data.turn);
    if (typeof data.eval === "number") setEvalScore(data.eval);
    setGameOver(Boolean(data.game_over));
    setResult(data.result || "");
    setErrorMessage(data.error_message || "");
    if (appendSans) {
      setSans((prev) => {
        const next = [...prev];
        if (data.user_san) next.push(data.user_san);
        if (data.engine_san) next.push(data.engine_san);
        return next;
      });
    }
  }

  async function slidePiece(from, to, sourceFen, duration) {
    const code = pieceCodeAt(sourceFen, from);
    if (!code || !from || !to) return applyDisplayMove(sourceFen, from, to);
    setFlight({ from, to, code, duration });
    setFen(clearSquareFen(sourceFen, from));
    await sleep(duration);
    const landed = applyDisplayMove(sourceFen, from, to);
    setFen(landed);
    setFlight(null);
    setFromSquare(from);
    setToSquare(to);
    return landed;
  }

  async function requestEngineOnly(fromFen = fen, side = seat) {
    const gen = ++requestGen.current;
    setPhase("thinking");
    setErrorMessage("");
    try {
      const data = await postPlay(fromFen, "", difficulty, side);
      if (gen !== requestGen.current) return;
      if (data?.engine_san && data.from_square && data.to_square) {
        setPhase("engine-move");
        await sleep(ENGINE_PAUSE_MS);
        if (gen !== requestGen.current) return;
        await slidePiece(
          data.from_square,
          data.to_square,
          fromFen,
          ENGINE_SLIDE_MS,
        );
      }
      if (gen !== requestGen.current) return;
      if (data?.fen) setFen(data.fen);
      applyMeta(data, { appendSans: Boolean(data?.engine_san) });
    } catch (err) {
      if (gen !== requestGen.current) return;
      setErrorMessage(
        err?.name === "AbortError"
          ? "电脑思考超时，请再试一次。"
          : "连不上下棋服务，请确认后端已启动。",
      );
    } finally {
      if (gen === requestGen.current) setPhase("idle");
    }
  }

  async function playUserMove(from, to) {
    const originFen = fen;
    const uci = `${from}${to}`;
    const gen = ++requestGen.current;
    setSelected("");
    setErrorMessage("");
    setPhase("user-move");
    await slidePiece(from, to, originFen, USER_SLIDE_MS);
    if (gen !== requestGen.current) return;

    setPhase("thinking");
    try {
      const data = await postPlay(originFen, uci, difficulty, seat);
      if (gen !== requestGen.current) return;
      applyMeta(data, { appendSans: true });
      if (data?.engine_san && data.from_square && data.to_square) {
        setPhase("engine-move");
        await sleep(ENGINE_PAUSE_MS);
        if (gen !== requestGen.current) return;
        const afterUser = applyDisplayMove(originFen, from, to);
        await slidePiece(
          data.from_square,
          data.to_square,
          afterUser,
          ENGINE_SLIDE_MS,
        );
      }
      if (gen !== requestGen.current) return;
      if (data?.fen) setFen(data.fen);
      if (data?.from_square) setFromSquare(data.from_square);
      if (data?.to_square) setToSquare(data.to_square);
    } catch (err) {
      if (gen !== requestGen.current) return;
      setFen(originFen);
      setFromSquare("");
      setToSquare("");
      setErrorMessage(
        err?.name === "AbortError"
          ? "电脑思考超时，请再试一次。"
          : "连不上下棋服务，请确认后端已启动。",
      );
    } finally {
      if (gen === requestGen.current) setPhase("idle");
    }
  }

  async function handleRestart(nextSeat = seat) {
    requestGen.current += 1;
    const gen = requestGen.current;
    setSeat(nextSeat);
    setFen(START_FEN);
    setLegalUci([]);
    setSelected("");
    setFromSquare("");
    setToSquare("");
    setEvalScore(0);
    setSans([]);
    setGameOver(false);
    setResult("");
    setOverOpen(false);
    setErrorMessage("");
    setTurn("white");
    setFlight(null);
    setPhase("thinking");
    try {
      const data = await postPlay(START_FEN, "", difficulty, nextSeat);
      if (gen !== requestGen.current) return;
      if (data?.fen) setFen(data.fen);
      applyMeta(data, { appendSans: Boolean(data?.engine_san) });
    } catch {
      if (gen !== requestGen.current) return;
      setErrorMessage("连不上下棋服务，请确认后端已启动。");
    } finally {
      if (gen === requestGen.current) setPhase("idle");
    }
  }

  useEffect(() => {
    let cancelled = false;
    const gen = ++requestGen.current;
    (async () => {
      try {
        const data = await postPlay(START_FEN, "", difficulty, seat);
        if (cancelled || gen !== requestGen.current) return;
        if (data?.fen) setFen(data.fen);
        applyMeta(data, { appendSans: Boolean(data?.engine_san) });
      } catch {
        if (!cancelled && gen === requestGen.current) {
          setErrorMessage("连不上下棋服务，请确认后端已启动。");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // Opening engine move only when entering as black.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (gameOver && phase === "idle") setOverOpen(true);
  }, [gameOver, phase]);

  function handleSquareClick(square) {
    if (busy || turn !== seat) return;
    if (selected && targets.includes(square)) {
      playUserMove(selected, square);
      return;
    }
    const mine = legalUci.some((uci) => uci.startsWith(square));
    if (mine) {
      setSelected(square);
      return;
    }
    setSelected("");
  }

  const statusLine = gameOver
    ? resultCopy(result, seat)
    : phase === "user-move"
      ? "棋子移动中…"
      : phase === "thinking"
        ? "电脑正在想…"
        : phase === "engine-move"
          ? "电脑走子…"
          : turn !== seat
            ? "轮到电脑。"
            : "轮到你走。点自己的棋子，再点落点。";

  const history = pairMoves(sans);
  const waitingForEngine = phase === "idle" && turn !== seat && !gameOver;

  return (
    <GameScreen
      header={<BrandStrip onBack={onBack} onHome={onHome} seat={seat} />}
      board={
        <ChessBoard
          fen={fen}
          from_square={fromSquare}
          to_square={toSquare}
          selected={selected}
          targets={targets}
          flight={flight}
          disabled={busy}
          flipped={seat === "black"}
          onSquareClick={handleSquareClick}
        />
      }
      panel={
        <>
          <p className="text-sm leading-relaxed text-ink">{statusLine}</p>
          <div className="mt-3 text-sm text-muted">
            你执{seat === "black" ? "黑" : "白"} · 评估{" "}
            <span className="font-mono">{formatEval(evalScore)}</span>
          </div>
          <SideSelect
            value={seat}
            disabled={phase !== "idle" || sans.length > 0}
            options={[
              { id: "white", label: "执白" },
              { id: "black", label: "执黑" },
            ]}
            onChange={(next) => handleRestart(next)}
          />
          <DifficultySelect
            value={difficulty}
            disabled={phase !== "idle"}
            onChange={setDifficulty}
          />
          {errorMessage ? (
            <p className="mt-3 text-sm text-red-600">{errorMessage}</p>
          ) : null}
          <GameControls>
            <button
              type="button"
              onClick={() => handleRestart()}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white"
            >
              重新开局
            </button>
            {waitingForEngine ? (
              <button
                type="button"
                onClick={() => requestEngineOnly()}
                className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink"
              >
                让电脑走
              </button>
            ) : null}
          </GameControls>
          <MoveHistory title="着法" empty="还没有走子。">
            {history.length === 0 ? null : (
              <ol className="mt-2 space-y-1 font-mono text-sm">
                {history.map((row) => (
                  <li key={row.n}>
                    {row.n}. {row.white} {row.black}
                  </li>
                ))}
              </ol>
            )}
          </MoveHistory>
        </>
      }
      modal={
        overOpen ? (
          <GameOverModal
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

export default function ChessGame({
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
    defaultSeat: "white",
  });

  if (lobby.mode === "ai") {
    return (
      <ChessAiGame
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
      <ChessOnline
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
      title="国际象棋"
      blurb="自己对电脑，或创建房间把链接发给对方。先选执白或执黑。"
      engineHint={
        lobby.seat === "black" ? "你执黑，电脑先走白" : "你执白，电脑回一手"
      }
      onlineHint={
        lobby.seat === "black" ? "生成房间码和链接，你执黑" : "生成房间码和链接，你执白"
      }
      seat={lobby.seat}
      seats={[
        { id: "white", label: "执白" },
        { id: "black", label: "执黑" },
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
