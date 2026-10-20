import { useMemo, useState } from "react";
import BoardOnline from "./BoardOnline.jsx";
import ChessBoard, { applyDisplayMove, clearSquareFen, pieceCodeAt } from "./ChessBoard.jsx";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function resultCopy(result, seat, endReason) {
  if (endReason === "resign") {
    if (result === seat) return "对方认输。你赢了。";
    return "你认输了。";
  }
  if (endReason === "timeout") {
    if (result === seat) return "对方超时。你赢了。";
    return "你超时了。";
  }
  if (result === "draw") return "和棋。";
  if (result === seat) return "将死。你赢了。";
  if (result === "white" || result === "black") return "将死。对方赢了。";
  return "对局结束。";
}

function pairHistory(sans) {
  const rows = [];
  for (let i = 0; i < sans.length; i += 2) {
    rows.push({ n: i / 2 + 1, a: sans[i], b: sans[i + 1] || "" });
  }
  return rows;
}

function ChessOnlineBoard({
  fen,
  legalUci,
  fromSquare,
  toSquare,
  myTurn,
  seat,
  flight,
  onMove,
}) {
  const [selected, setSelected] = useState("");
  const targets = useMemo(() => {
    if (!selected) return [];
    return legalUci
      .filter((uci) => uci.startsWith(selected))
      .map((uci) => uci.slice(2, 4));
  }, [legalUci, selected]);

  function handleSquareClick(square) {
    if (!myTurn) return;
    if (selected && targets.includes(square)) {
      const uci = `${selected}${square}`;
      onMove(uci, applyDisplayMove(fen, selected, square));
      setSelected("");
      return;
    }
    if (legalUci.some((uci) => uci.startsWith(square))) {
      setSelected(square);
      return;
    }
    setSelected("");
  }

  return (
    <ChessBoard
      fen={fen}
      from_square={fromSquare}
      to_square={toSquare}
      selected={selected}
      targets={targets}
      flight={flight}
      disabled={!myTurn}
      flipped={seat === "black"}
      onSquareClick={handleSquareClick}
    />
  );
}

export default function ChessOnline({
  initialCode,
  initialToken = "",
  initialSeat = "",
  createSeat = "white",
  clockEnabled = true,
  onBack,
  onHome,
  onRoomCode,
  onFinish,
  compact = false,
  opponentName = "",
}) {
  return (
    <BoardOnline
      game="chess"
      compact={compact}
      opponentName={opponentName}
      initialCode={initialCode}
      initialToken={initialToken}
      initialSeat={initialSeat}
      createSeat={createSeat}
      onGameOver={(result, seat) => onFinish?.({ seat, result })}
      clockEnabled={clockEnabled}
      firstSeat="white"
      secondSeat="black"
      startFen={START_FEN}
      storageKey="elegram-chess-seat"
      pairHistory={pairHistory}
      resultCopy={resultCopy}
      readPiece={pieceCodeAt}
      clearSquare={clearSquareFen}
      sloganFor={(seat) =>
        seat === "black"
          ? "你执黑。把链接发给对方，对方执白先走。"
          : "你执白。把链接发给对方，对方执黑。"
      }
      metaFor={(seat, bothReady, clockLimitMs) =>
        `你执${seat === "black" ? "黑" : "白"}${
          bothReady ? " · 对方已加入" : " · 等待对方"
        }${
          bothReady
            ? clockLimitMs > 0
              ? ` · 每手 ${Math.round(clockLimitMs / 1000)} 秒`
              : " · 不限时"
            : ""
        }`
      }
      onBack={onBack}
      onHome={onHome}
      onRoomCode={onRoomCode}
      renderBoard={(props) => <ChessOnlineBoard {...props} />}
    />
  );
}
