import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { ChessMark, GomokuMark } from "../play/marks";
import { useI18n } from "../i18n";
import ChessGame from "../play/ChessGame";
import GomokuGame from "../play/GomokuGame";

export default function Play() {
  const { user, ready } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const game = params.get("game");
  const picked = game === "gomoku" || game === "chess" ? game : "";
  const room = (params.get("r") || "").toUpperCase();

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/play", { replace: true });
  }, [ready, user, navigate]);

  if (!ready || !user) return null;

  return (
    <div className="mt-8">
      <Link
        to="/forum"
        className="font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]"
      >
        {t("play.backForum")}
      </Link>
      {picked === "" ? (
        <>
          <h1 className="mt-6 font-serif text-4xl">{t("play.choose")}</h1>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setParams({ game: "gomoku" })}
              className="border border-black px-6 py-8 text-left"
            >
              <span className="flex items-center justify-between gap-4">
                <span className="font-serif text-3xl font-bold">{t("play.gomoku")}</span>
                <GomokuMark className="h-14 w-14 shrink-0" />
              </span>
              <span className="mt-2 block font-sans text-sm text-neutral-600">
                {t("play.gomokuNote")}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setParams({ game: "chess" })}
              className="border border-black px-6 py-8 text-left"
            >
              <span className="flex items-center justify-between gap-4">
                <span className="font-serif text-3xl font-bold">{t("play.chess")}</span>
                <ChessMark className="h-14 w-14 shrink-0" />
              </span>
              <span className="mt-2 block font-sans text-sm text-neutral-600">
                {t("play.chessNote")}
              </span>
            </button>
          </div>
        </>
      ) : picked === "gomoku" ? (
        <div className="mt-6">
          <GomokuGame onBack={() => setParams({})} initialRoomCode={room} />
        </div>
      ) : (
        <div className="mt-6">
          <ChessGame onBack={() => setParams({})} initialRoomCode={room} />
        </div>
      )}
    </div>
  );
}
