import { useEffect, useRef, useState } from "react";

const BOARD_SIZE = 15;
const STAR_POINTS = [
  [3, 3],
  [3, 11],
  [7, 7],
  [11, 3],
  [11, 11],
];

function pointName(row, col) {
  return `${String.fromCharCode(65 + col)}${row + 1}`;
}

function cellFromEvent(event) {
  const rect = event.currentTarget.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return null;
  const col = Math.floor(((event.clientX - rect.left) / rect.width) * BOARD_SIZE);
  const row = Math.floor(((event.clientY - rect.top) / rect.height) * BOARD_SIZE);
  if (row < 0 || col < 0 || row >= BOARD_SIZE || col >= BOARD_SIZE) return null;
  return { row, col };
}

function moveKey(move) {
  return `${move.row}:${move.col}`;
}

function reduceMotion() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function StoneGlyph({ player }) {
  const black = player === "black";
  return (
    <svg viewBox="0 0 64 64" className="h-full w-full overflow-visible" aria-hidden="true">
      <circle cx="32" cy="32" r="29.2" fill={black ? "#0b0b0b" : "#cfcfcf"} />
      <circle cx="32" cy="32" r="27.4" fill={black ? "#1d1d1d" : "#f6f4f0"} />
      <ellipse
        cx="24"
        cy="22"
        rx="13"
        ry="9.5"
        fill="#ffffff"
        opacity={black ? 0.2 : 0.72}
      />
      <ellipse
        cx="39"
        cy="41"
        rx="15"
        ry="11"
        fill={black ? "#000000" : "#bdbdb8"}
        opacity={black ? 0.28 : 0.28}
      />
    </svg>
  );
}

function Stone({ player, animate, isLast, onPlaced }) {
  const placedRef = useRef(onPlaced);
  placedRef.current = onPlaced;

  useEffect(() => {
    if (!animate) return undefined;
    const timer = window.setTimeout(() => placedRef.current?.(), 520);
    return () => window.clearTimeout(timer);
  }, [animate]);

  return (
    <span className="gomoku-stone relative block h-[84%] w-[84%]">
      <span
        className={`gomoku-stone-shadow ${
          animate ? "gomoku-stone-shadow-in" : ""
        }`}
      />
      {animate ? <span className="gomoku-stone-ripple" /> : null}
      <span
        className={`gomoku-stone-fly ${animate ? "gomoku-stone-place" : ""}`}
        onAnimationEnd={(event) => {
          if (event.animationName === "gomoku-stone-fall") placedRef.current?.();
        }}
      >
        <span className="gomoku-stone-body relative z-[1] block h-full w-full">
          <StoneGlyph player={player} />
        </span>
        {isLast ? <span className="gomoku-last-mark" /> : null}
      </span>
    </span>
  );
}

export default function GomokuBoard({
  moves,
  disabled,
  onPointClick,
  animateLast = true,
}) {
  const [hover, setHover] = useState(null);
  const [placing, setPlacing] = useState(() => new Set());
  const seenRef = useRef(new Set());
  const movesRef = useRef(moves);
  const occupied = new Map(
    moves.map((move) => [moveKey(move), move.player]),
  );
  const lastMove = moves[moves.length - 1];
  const nextPlayer = moves.length % 2 === 0 ? "black" : "white";

  if (moves !== movesRef.current) {
    movesRef.current = moves;
    if (moves.length === 0) {
      seenRef.current = new Set();
      setPlacing((prev) => (prev.size ? new Set() : prev));
    } else if (animateLast && !reduceMotion()) {
      const fresh = [];
      for (const move of moves) {
        const key = moveKey(move);
        if (!seenRef.current.has(key)) {
          seenRef.current.add(key);
          fresh.push(key);
        }
      }
      if (fresh.length) {
        setPlacing((prev) => {
          const next = new Set(prev);
          for (const key of fresh) next.add(key);
          return next;
        });
      }
    } else {
      for (const move of moves) seenRef.current.add(moveKey(move));
    }
  }

  function handlePlaced(key) {
    setPlacing((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  function handlePointerDown(event) {
    if (disabled) return;
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const cell = cellFromEvent(event);
    if (!cell) return;
    if (occupied.has(`${cell.row}:${cell.col}`)) return;
    event.preventDefault();
    onPointClick(cell.row, cell.col);
  }

  function handlePointerMove(event) {
    if (disabled || event.pointerType !== "mouse") {
      if (hover) setHover(null);
      return;
    }
    const cell = cellFromEvent(event);
    if (!cell || occupied.has(`${cell.row}:${cell.col}`)) {
      if (hover) setHover(null);
      return;
    }
    if (hover?.row !== cell.row || hover?.col !== cell.col) setHover(cell);
  }

  return (
    <div className="board-slot">
      <div
        className={`board-fit-square overflow-visible bg-[#d9a45f] touch-manipulation select-none ${
          disabled ? "cursor-default" : "cursor-pointer"
        }`}
        aria-label="十五乘十五五子棋棋盘"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setHover(null)}
      >
        <svg
          viewBox="-0.5 -0.5 15 15"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          {Array.from({ length: BOARD_SIZE }, (_, index) => (
            <g key={index} stroke="#5b361d" strokeWidth="0.035">
              <line x1="0" y1={index} x2="14" y2={index} />
              <line x1={index} y1="0" x2={index} y2="14" />
            </g>
          ))}
          {STAR_POINTS.map(([row, col]) => (
            <circle
              key={`${row}:${col}`}
              cx={col}
              cy={row}
              r="0.1"
              fill="#5b361d"
            />
          ))}
        </svg>

        <div className="pointer-events-none absolute inset-0 grid grid-cols-[repeat(15,minmax(0,1fr))] grid-rows-[repeat(15,minmax(0,1fr))]">
          {Array.from({ length: BOARD_SIZE * BOARD_SIZE }, (_, index) => {
            const row = Math.floor(index / BOARD_SIZE);
            const col = index % BOARD_SIZE;
            const key = `${row}:${col}`;
            const player = occupied.get(key);
            const isLast = lastMove?.row === row && lastMove?.col === col;
            const isHover = !player && hover?.row === row && hover?.col === col;
            return (
              <div
                key={key}
                aria-hidden="true"
                className={`relative flex items-center justify-center ${
                  placing.has(key) || isLast ? "z-10" : ""
                }`}
              >
                {player ? (
                  <Stone
                    player={player}
                    animate={placing.has(key)}
                    isLast={isLast}
                    onPlaced={() => handlePlaced(key)}
                  />
                ) : isHover ? (
                  <span className="gomoku-stone gomoku-stone-ghost relative block h-[84%] w-[84%]">
                    <StoneGlyph player={nextPlayer} />
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
        <div className="sr-only">
          {moves.map((move) => (
            <span key={moveKey(move)}>
              {pointName(move.row, move.col)}
              {move.player === "black" ? " 黑子" : " 白子"}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
