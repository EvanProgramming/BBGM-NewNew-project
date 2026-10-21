import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError, SectionRule } from "../components/ui";
import { canDeletePosts, formatDateline } from "../format";
import { useI18n } from "../i18n";
import { useLiveRefresh } from "../live";

const actionClass =
  "inline-flex items-center gap-2 border border-black px-4 py-2 font-sans text-[12px] font-medium uppercase tracking-[0.14em] disabled:opacity-50";

export default function Bottles() {
  const { user, ready, setUser } = useAuth();
  const { lang, t } = useI18n();
  const navigate = useNavigate();
  const [body, setBody] = useState("");
  const [thrown, setThrown] = useState([]);
  const [picked, setPicked] = useState([]);
  const [reports, setReports] = useState([]);
  const [pane, setPane] = useState("thrown");
  const [error, setError] = useState(null);
  const [fieldError, setFieldError] = useState("");
  const [seaEmpty, setSeaEmpty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [throwing, setThrowing] = useState(false);
  const [picking, setPicking] = useState(false);
  const moderator = canDeletePosts(user);

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/bottles", { replace: true });
  }, [ready, user, navigate]);

  const refresh = useCallback(async () => {
    const mine = await api.myBottles();
    setThrown(mine.thrown || []);
    setPicked(mine.picked || []);
    if (moderator) {
      const reported = await api.bottleReports();
      setReports(reported.items || []);
    }
    setError(null);
  }, [moderator]);

  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setUser(null);
          navigate("/sign-in?next=/bottles");
          return;
        }
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, navigate, setUser, refresh]);

  useLiveRefresh(Boolean(user) && !loading, refresh);

  function goToSignIn(err) {
    if (err instanceof ApiError && err.status === 401) {
      setUser(null);
      navigate("/sign-in?next=/bottles");
      return true;
    }
    return false;
  }

  async function onThrow(event) {
    event.preventDefault();
    setThrowing(true);
    setFieldError("");
    setSeaEmpty(false);
    setError(null);
    try {
      await api.throwBottle(body);
      setBody("");
      await refresh();
    } catch (err) {
      if (goToSignIn(err)) return;
      const message = fieldMessage(err, "body");
      if (message) setFieldError(message);
      else setError(err);
    } finally {
      setThrowing(false);
    }
  }

  async function onPick() {
    setPicking(true);
    setSeaEmpty(false);
    setError(null);
    try {
      const data = await api.pickBottle();
      if (!data?.pick?.id) {
        setSeaEmpty(true);
        return;
      }
      navigate(`/bottles/picks/${data.pick.id}`);
    } catch (err) {
      if (!goToSignIn(err)) setError(err);
    } finally {
      setPicking(false);
    }
  }

  async function onDeleteBottle(bottleId) {
    if (!window.confirm(t("bottle.deleteConfirm"))) return;
    setError(null);
    try {
      await api.deleteBottle(bottleId);
      await refresh();
    } catch (err) {
      if (!goToSignIn(err)) setError(err);
    }
  }

  if (!ready || !user) return null;

  const panes = [
    ["thrown", "bottle.thrown"],
    ["picked", "bottle.picked"],
  ];
  if (moderator) panes.push(["reported", "bottle.reported"]);
  const rows = pane === "picked" ? picked : pane === "reported" ? reports : thrown;

  return (
    <div className="mx-auto mt-8 w-full max-w-[42rem]">
      <SectionRule>{t("bottle.title")}</SectionRule>
      <ErrorBanner error={error} />
      <form onSubmit={onThrow}>
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={4}
          maxLength={500}
          placeholder={t("bottle.placeholder")}
          className="w-full border border-neutral-300 px-3 py-2 font-sans text-[15px] leading-7 outline-none focus:border-black"
        />
        <FieldError message={fieldError} />
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="submit" className={actionClass} disabled={throwing}>
            {throwing ? <ButtonSpinner /> : null}
            {t("bottle.throw")}
          </button>
          <button type="button" className={actionClass} disabled={picking} onClick={onPick}>
            {picking ? <ButtonSpinner /> : null}
            {t("bottle.pick")}
          </button>
        </div>
      </form>
      {seaEmpty ? <p className="mt-4 font-sans text-sm text-neutral-600">{t("bottle.emptySea")}</p> : null}

      <div className="mt-8 flex gap-6 border-b border-neutral-200">
        {panes.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`pb-2 font-sans text-[13px] ${pane === id ? "text-[#1A4FBF] underline decoration-2 underline-offset-[7px]" : "text-neutral-900"}`}
            onClick={() => setPane(id)}
          >
            {t(label)}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="mt-6 font-sans text-sm text-neutral-500">{t("bottle.loading")}</p>
      ) : rows.length === 0 ? (
        <p className="mt-6 font-sans text-sm text-neutral-600">
          {pane === "picked"
            ? t("bottle.emptyPicked")
            : pane === "reported"
              ? t("bottle.emptyReported")
              : t("bottle.emptyThrown")}
        </p>
      ) : (
        <ul className="mt-2 border-t border-black">
          {rows.map((item) => {
            const pickId = item.pick_id;
            const key = pane === "reported" ? item.id : `${item.bottle_id}:${pickId || "open"}`;
            return (
              <li key={key} className="flex items-start justify-between gap-4 border-b border-neutral-200 py-4">
                <div className="min-w-0">
                  {pickId ? (
                    <Link to={`/bottles/picks/${pickId}`} className="font-sans text-[16px] leading-7 text-inherit">
                      {item.excerpt}
                      {item.unread === 1 ? (
                        <span className="ml-2 inline-flex h-[15px] min-w-[15px] items-center justify-center rounded-full bg-[#E10600] px-[4px] font-sans text-[9px] font-bold text-white">
                          1
                        </span>
                      ) : null}
                    </Link>
                  ) : (
                    <p className="font-sans text-[16px] leading-7">{item.excerpt}</p>
                  )}
                  <p className="mt-1 font-sans text-sm text-neutral-500">
                    {formatDateline(item.created_at, lang)}
                    {pane !== "reported" && pickId ? ` · ${item.reply_count} ${t("bottle.replies")}` : ""}
                    {pane === "thrown" && !pickId ? ` · ${t("bottle.waiting")}` : ""}
                  </p>
                </div>
                {pane === "thrown" ? (
                  <button
                    type="button"
                    className="shrink-0 font-sans text-[12px] uppercase tracking-[0.12em] text-neutral-500"
                    onClick={() => onDeleteBottle(item.bottle_id)}
                  >
                    {t("bottle.delete")}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
