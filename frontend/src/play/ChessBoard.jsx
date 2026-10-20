import { useEffect, useState } from "react";

export function squaresFromFen(fen) {
  const placement = (fen || "").split(" ")[0];
  if (!placement) return [];

  const ranks = placement.split("/");
  const squares = [];

  for (let rankIndex = 0; rankIndex < 8; rankIndex += 1) {
    const rank = 8 - rankIndex;
    const row = ranks[rankIndex] || "";
    let fileIndex = 0;
    for (const ch of row) {
      if (fileIndex >= 8) break;
      if (ch >= "1" && ch <= "8") {
        const empty = Number(ch);
        for (let i = 0; i < empty && fileIndex < 8; i += 1) {
          const file = String.fromCharCode(97 + fileIndex);
          squares.push({ name: `${file}${rank}`, code: "" });
          fileIndex += 1;
        }
      } else {
        const file = String.fromCharCode(97 + fileIndex);
        squares.push({
          name: `${file}${rank}`,
          code: ch,
        });
        fileIndex += 1;
      }
    }
    while (fileIndex < 8) {
      const file = String.fromCharCode(97 + fileIndex);
      squares.push({ name: `${file}${rank}`, code: "" });
      fileIndex += 1;
    }
  }

  return squares;
}

export function pieceCodeAt(fen, square) {
  return squaresFromFen(fen).find((sq) => sq.name === square)?.code || "";
}

function boardMapFromFen(fen) {
  const map = {};
  for (const sq of squaresFromFen(fen)) map[sq.name] = sq.code;
  return map;
}

function fenFromBoardMap(map, rest) {
  let placement = "";
  for (let rank = 8; rank >= 1; rank -= 1) {
    let empty = 0;
    for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
      const name = `${String.fromCharCode(97 + fileIndex)}${rank}`;
      const code = map[name] || "";
      if (!code) {
        empty += 1;
      } else {
        if (empty) {
          placement += String(empty);
          empty = 0;
        }
        placement += code;
      }
    }
    if (empty) placement += String(empty);
    if (rank > 1) placement += "/";
  }
  return rest ? `${placement} ${rest}` : placement;
}

export function clearSquareFen(fen, square) {
  const rest = fen.split(" ").slice(1).join(" ");
  const map = boardMapFromFen(fen);
  map[square] = "";
  return fenFromBoardMap(map, rest);
}

export function applyDisplayMove(fen, from, to) {
  const rest = fen.split(" ").slice(1).join(" ");
  const map = boardMapFromFen(fen);
  let piece = map[from];
  if (!piece) return fen;
  map[from] = "";
  if (piece === "K" && from === "e1" && to === "g1") {
    map.h1 = "";
    map.f1 = "R";
  } else if (piece === "K" && from === "e1" && to === "c1") {
    map.a1 = "";
    map.d1 = "R";
  } else if (piece === "k" && from === "e8" && to === "g8") {
    map.h8 = "";
    map.f8 = "r";
  } else if (piece === "k" && from === "e8" && to === "c8") {
    map.a8 = "";
    map.d8 = "r";
  }
  if (piece === "P" && to[1] === "8") piece = "Q";
  if (piece === "p" && to[1] === "1") piece = "q";
  map[to] = piece;
  return fenFromBoardMap(map, rest);
}

function isDark(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]);
  return (file + rank) % 2 === 1;
}

function squareBox(square) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]);
  return {
    left: `${file * 12.5}%`,
    top: `${(8 - rank) * 12.5}%`,
  };
}

export function PieceGlyph({ code, flying = false }) {
  if (!code) return null;
  const white = code === code.toUpperCase();
  const kind = code.toUpperCase();
  const fill = white ? "#fff8ee" : "#1c1410";
  const stroke = white ? "#1c1410" : "#f3e6cf";
  return (
    <svg
      viewBox="0 0 45 45"
      className={`h-[84%] w-[84%] ${flying ? "chess-piece-fly" : ""}`}
      aria-hidden="true"
    >
      {kind === "P" ? (
        <path
          d="M22.5 9c-2.21 0-4 1.79-4 4 0 .89.29 1.71.78 2.38C17.33 16.5 16 18.59 16 21c0 2.03.94 3.84 2.41 5.03-3 1.06-7.41 5.55-7.41 13.47h23c0-7.92-4.41-12.41-7.41-13.47 1.47-1.19 2.41-3 2.41-5.03 0-2.41-1.33-4.5-3.28-5.62.49-.67.78-1.49.78-2.38 0-2.21-1.79-4-4-4z"
          fill={fill}
          stroke={stroke}
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      ) : null}
      {kind === "R" ? (
        <g fill={fill} stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 39h27v-3H9v3zM12 36v-4h21v4H12zM11 14V9h4v2h5V9h5v2h5V9h4v5" />
          <path d="M34 14l-3 3H14l-3-3" />
          <path d="M31 17v12.5H14V17" />
          <path d="M31 29.5l1.5 2.5h-20l1.5-2.5" />
          <path d="M14 17h17" fill="none" />
        </g>
      ) : null}
      {kind === "N" ? (
        <g fill={fill} stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 10c10.5 1 16.5 8 16 29H15c0-9 10-6.5 8-21" />
          <path d="M24 18c.38 2.91-5.55 7.37-8 9-3 2-2.82 4.34-5 4-1.04-.94 1.41-3.04 0-3-1 0 .19 1.23-1 2-1 0-4.003 1-4-4 0-2 6-12 6-12s1.89-1.9 2-3.5c-.73-.994-.5-2 .5-3s3 2.5 3 2.5h2s.78-1.992 2.5-3c1 0 1 3 1 3" />
        </g>
      ) : null}
      {kind === "B" ? (
        <g fill={fill} stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 36c3.39-3.39 10.08.07 10.5-4H15c0-2.5 2-4 4-4 .5 0 1 .07 1.5.22.5-.15 1-.22 1.5-.22 2 0 4 1.5 4 4h-4.5c.42 4.07 7.11.61 10.5 4" />
          <path d="M15 32c2.5 2.5 12.5 2.5 15 0 .5-1.5 0-2 0-2 0-2.5-2.5-4-2.5-4 5.5-1.5 6-11.5-5-15.5-3.5 4-12.5 2-8.5 11.5 0 0-2.5 1.5-2.5 4 0 0-.5.5 0 2z" />
          <path d="M25 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 1 1 5 0z" />
          <path d="M17.5 26h10M15 30h15" fill="none" />
        </g>
      ) : null}
      {kind === "Q" ? (
        <g fill={fill} stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="6" cy="12" r="2.75" />
          <circle cx="22.5" cy="6" r="2.75" />
          <circle cx="39" cy="12" r="2.75" />
          <circle cx="14" cy="9" r="2.75" />
          <circle cx="31" cy="9" r="2.75" />
          <path d="M9 26c8.5-9 18.5-9 27 0l2.5-12.5L31 25l-.5-14.5-9 16.5-9-16.5L12 25 6.5 13.5 9 26z" />
          <path d="M9 26c0 2 1.5 2 2.5 4 1 1.5 1 1 .5 3.5-1.5 1-1.5 4.5-1.5 4.5h21s0-3.5-1.5-4.5c-.5-2.5-.5-2 .5-3.5 1-2 2.5-2 2.5-4-8.5-1.5-18.5-1.5-27 0z" />
          <path d="M11.5 30c5-1 16-1 21 0M11 33.5c6-1 16-1 22 0" fill="none" />
        </g>
      ) : null}
      {kind === "K" ? (
        <g fill={fill} stroke={stroke} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22.5 11.63V6M20 8h5" fill="none" />
          <path d="M22.5 25s4.5-7.5 3-10.5c0 0-1-2.5-3-2.5s-3 2.5-3 2.5c-1.5 3 3 10.5 3 10.5" />
          <path d="M12.5 37c5.5 3.5 14.5 3.5 20 0v-7s9-4.5 6-10.5c-4-6.5-13.5-3.5-16 4V27v-3.5c-2.5-7.5-12-6.5-16 4-3 6 6 10.5 6 10.5v7" />
          <path d="M12.5 30c5.5-3 14.5-3 20 0M12.5 33.5c5.5-3 14.5-3 20 0M12.5 37c5.5-3 14.5-3 20 0" fill="none" />
        </g>
      ) : null}
    </svg>
  );
}

function FlyingPiece({ from, to, code, duration, flipped = false }) {
  const [pos, setPos] = useState(squareBox(from));
  const [moving, setMoving] = useState(false);

  useEffect(() => {
    setMoving(false);
    setPos(squareBox(from));
    const frame = requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setMoving(true);
        setPos(squareBox(to));
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [from, to, code, duration]);

  return (
    <div
      className="pointer-events-none absolute z-10 flex h-[12.5%] w-[12.5%] items-center justify-center"
      style={{
        left: pos.left,
        top: pos.top,
        transition: moving
          ? `left ${duration}ms ease-in-out, top ${duration}ms ease-in-out`
          : "none",
      }}
    >
      <span
        className="flex h-full w-full items-center justify-center"
        style={flipped ? { transform: "rotate(180deg)" } : undefined}
      >
        <PieceGlyph code={code} flying />
      </span>
    </div>
  );
}

export default function ChessBoard({
  fen,
  from_square,
  to_square,
  selected,
  targets = [],
  flight = null,
  onSquareClick,
  disabled = false,
  flipped = false,
}) {
  const squares = squaresFromFen(fen);
  const clickable = typeof onSquareClick === "function" && !disabled;

  return (
    <div className="board-slot">
      <div
        className="board-fit-square grid grid-cols-8 grid-rows-8"
        aria-label="棋盘"
        style={flipped ? { transform: "rotate(180deg)" } : undefined}
      >
      {squares.map((sq) => {
        const lastMove = sq.name === from_square || sq.name === to_square;
        const isSelected = sq.name === selected;
        const isTarget = targets.includes(sq.name);
        const hiddenByFlight = flight && sq.name === flight.from;
        return (
          <button
            key={sq.name}
            type="button"
            data-square={sq.name}
            disabled={!clickable}
            onClick={() => onSquareClick?.(sq.name)}
            className={`relative flex touch-manipulation items-center justify-center ${
              isDark(sq.name) ? "bg-[#b58863]" : "bg-[#f0d9b5]"
            } ${lastMove || isSelected ? "ring-2 ring-inset ring-red-600" : ""} ${
              isTarget ? "bg-red-600/35" : ""
            } ${clickable ? "cursor-pointer" : "cursor-default"}`}
          >
            {hiddenByFlight ? null : (
              <span
                className="flex h-full w-full items-center justify-center"
                style={flipped ? { transform: "rotate(180deg)" } : undefined}
              >
                <PieceGlyph code={sq.code} />
              </span>
            )}
            {isTarget && !sq.code ? (
              <span className="absolute h-[22%] w-[22%] max-h-3 max-w-3 min-h-[0.4rem] min-w-[0.4rem] rounded-full bg-red-600" />
            ) : null}
          </button>
        );
      })}
      {flight ? (
        <FlyingPiece
          key={`${flight.from}${flight.to}${flight.code}`}
          from={flight.from}
          to={flight.to}
          code={flight.code}
          duration={flight.duration}
          flipped={flipped}
        />
      ) : null}
      </div>
    </div>
  );
}
