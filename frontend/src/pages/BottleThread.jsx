import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError } from "../components/ui";
import { canDeletePosts, formatDateline } from "../format";
import { useI18n } from "../i18n";
import { useLiveRefresh } from "../live";

const actionClass =
  "inline-flex items-center gap-2 border border-black px-4 py-2 font-sans text-[12px] font-medium uppercase tracking-[0.14em] disabled:opacity-50";

export default function BottleThread() {
  const { pickId } = useParams();
  const { user, ready, setUser } = useAuth();
  const { lang, t } = useI18n();
  const navigate = useNavigate();
  const [thread, setThread] = useState(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState(null);
  const [fieldError, setFieldError] = useState("");
  const [missing, setMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [reported, setReported] = useState(false);
  const moderator = canDeletePosts(user);
  const next = `/bottles/picks/${pickId}`;

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate(`/sign-in?next=${encodeURIComponent(next)}`, { replace: true });
  }, [ready, user, navigate, next]);

  const refresh = useCallback(async () => {
    const data = await api.getBottlePick(pickId);
    setThread(data);
    setMissing(false);
    setError(null);
    await api.readBottlePick(pickId);
  }, [pickId]);

  useEffect(() => {
    if (!user || !pickId) return undefined;
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setUser(null);
          navigate(`/sign-in?next=${encodeURIComponent(next)}`);
          return;
        }
        if (err instanceof ApiError && err.status === 404) {
          setMissing(true);
          setThread(null);
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
  }, [user, pickId, navigate, setUser, refresh, next]);

  useLiveRefresh(Boolean(user) && !loading && !missing, refresh);

  function goToSignIn(err) {
    if (err instanceof ApiError && err.status === 401) {
      setUser(null);
      navigate(`/sign-in?next=${encodeURIComponent(next)}`);
      return true;
    }
    return false;
  }

  async function onReply(event) {
    event.preventDefault();
    setSending(true);
    setFieldError("");
    setError(null);
    try {
      await api.replyBottle(pickId, draft);
      setDraft("");
      await refresh();
    } catch (err) {
      if (goToSignIn(err)) return;
      const message = fieldMessage(err, "body");
      if (message) setFieldError(message);
      else setError(err);
    } finally {
      setSending(false);
    }
  }

  async function onReport() {
    if (!window.confirm(t("bottle.reportConfirm"))) return;
    setError(null);
    try {
      await api.reportBottlePick(pickId);
      setReported(true);
    } catch (err) {
      if (!goToSignIn(err)) setError(err);
    }
  }

  async function onDeleteBottle() {
    if (!thread || !window.confirm(t("bottle.deleteConfirm"))) return;
    setError(null);
    try {
      await api.deleteBottle(thread.bottle_id);
      navigate("/bottles");
    } catch (err) {
      if (!goToSignIn(err)) setError(err);
    }
  }

  async function onDeleteMessage(message) {
    const ownReply = message.mine && thread?.role !== "moderator";
    if (!window.confirm(t(ownReply ? "bottle.withdrawConfirm" : "bottle.deleteReplyConfirm"))) return;
    setError(null);
    try {
      await api.deleteBottleMessage(pickId, message.id);
      await refresh();
    } catch (err) {
      if (!goToSignIn(err)) setError(err);
    }
  }

  if (!ready || !user) return null;

  function speaker(message) {
    if (message.mine && thread?.role !== "moderator") return t("bottle.you");
    if (thread?.thrower && thread?.picker) {
      const person = message.from === "thrower" ? thread.thrower : thread.picker;
      return person.display_name;
    }
    return message.mine ? t("bottle.you") : t("bottle.someone");
  }

  const canDeleteBottle = thread && (thread.role === "thrower" || moderator);

  return (
    <div className="mx-auto mt-8 w-full max-w-[42rem]">
      <Link to="/bottles" className="font-sans text-[12px] uppercase tracking-[0.14em] text-[#1A4FBF]">
        {t("bottle.title")}
      </Link>
      <ErrorBanner error={error} />
      {loading ? (
        <p className="mt-6 font-sans text-sm text-neutral-500">{t("bottle.loading")}</p>
      ) : missing || !thread ? (
        <p className="mt-6 font-serif text-2xl">{t("bottle.notFound")}</p>
      ) : (
        <>
          {thread.thrower && thread.picker ? (
            <p className="mt-4 font-sans text-sm text-neutral-600">
              {t("bottle.thrownBy")} {thread.thrower.display_name} · {thread.thrower.email}
              <br />
              {t("bottle.pickedBy")} {thread.picker.display_name} · {thread.picker.email}
            </p>
          ) : null}
          <article className="mt-4 border border-neutral-200 bg-neutral-50 px-4 py-4">
            <p className="font-sans text-[11px] uppercase tracking-[0.14em] text-neutral-500">
              {thread.thrower
                ? thread.thrower.display_name
                : thread.role === "thrower"
                  ? t("bottle.you")
                  : t("bottle.someone")}
            </p>
            <p className="mt-2 whitespace-pre-wrap font-sans text-[16px] leading-7">{thread.bottle_body}</p>
            <p className="mt-2 font-sans text-sm text-neutral-500">{formatDateline(thread.bottle_created_at, lang)}</p>
          </article>
          <ul className="mt-4">
            {thread.messages.map((message) => (
              <li key={message.id} className={`mb-3 flex ${message.mine ? "justify-end" : "justify-start"}`}>
                <div className="max-w-[85%] border border-neutral-200 px-3 py-2">
                  <p className="font-sans text-[11px] uppercase tracking-[0.12em] text-neutral-500">{speaker(message)}</p>
                  <p className="mt-1 whitespace-pre-wrap font-sans text-[15px] leading-7">{message.body}</p>
                  <div className="mt-1 flex items-center justify-between gap-3">
                    <p className="font-sans text-xs text-neutral-500">{formatDateline(message.created_at, lang)}</p>
                    {message.mine || moderator ? (
                      <button
                        type="button"
                        className="font-sans text-[12px] uppercase tracking-[0.12em] text-neutral-500"
                        onClick={() => onDeleteMessage(message)}
                      >
                        {message.mine && thread.role !== "moderator" ? t("bottle.withdraw") : t("bottle.delete")}
                      </button>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {thread.role === "moderator" ? (
            canDeleteBottle ? (
              <button type="button" className={`${actionClass} mt-4`} onClick={onDeleteBottle}>
                {t("bottle.delete")}
              </button>
            ) : null
          ) : (
            <form onSubmit={onReply} className="mt-4">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                rows={3}
                maxLength={500}
                placeholder={t("bottle.replyPlaceholder")}
                className="w-full border border-neutral-300 px-3 py-2 font-sans text-[15px] leading-7 outline-none focus:border-black"
              />
              <FieldError message={fieldError} />
              <div className="mt-3 flex flex-wrap gap-3">
                <button type="submit" className={actionClass} disabled={sending}>
                  {sending ? <ButtonSpinner /> : null}
                  {t("bottle.reply")}
                </button>
                <button type="button" className={actionClass} onClick={onReport}>
                  {t("bottle.report")}
                </button>
                {canDeleteBottle ? (
                  <button type="button" className={actionClass} onClick={onDeleteBottle}>
                    {t("bottle.delete")}
                  </button>
                ) : null}
              </div>
              {reported ? <p className="mt-3 font-sans text-sm text-neutral-600">{t("bottle.reportedDone")}</p> : null}
            </form>
          )}
        </>
      )}
    </div>
  );
}
