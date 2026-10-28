import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";
import { useLiveRefresh } from "../live";

const actionClass =
  "inline-flex items-center gap-2 border border-black px-4 py-2 font-sans text-[12px] font-medium uppercase tracking-[0.14em] disabled:opacity-50";

const votedClass =
  "inline-flex items-center border border-[#1A4FBF] bg-[#1A4FBF] px-4 py-2 font-sans text-[12px] font-medium uppercase tracking-[0.14em] text-white";

const RANK_CLASS = {
  1: "flex h-14 w-14 shrink-0 items-center justify-center bg-[#C6A15B] font-serif text-[28px] leading-none text-[#111111]",
  2: "flex h-12 w-12 shrink-0 items-center justify-center bg-[#8E96A3] font-serif text-[22px] leading-none text-[#111111]",
  3: "flex h-12 w-12 shrink-0 items-center justify-center bg-[#A56B3C] font-serif text-[22px] leading-none text-white",
  4: "flex h-12 w-12 shrink-0 items-center justify-center bg-[#1A4FBF] font-serif text-[22px] leading-none text-white",
};

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

function coverSrc(url) {
  const match = /^https:\/\/y\.qq\.com\/music\/photo_new\/T002R300x300M000([0-9A-Za-z]{1,32})\.jpg$/.exec(url || "");
  return match ? `${API_BASE}/bell/covers/${match[1]}` : "";
}

function toUtcStamp(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(String(value || "").trim());
  if (!match) return "";
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5]),
    Number(match[6] || 0),
  );
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function formatWhen(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("en-US", {
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function Bell() {
  const { user, ready } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [board, setBoard] = useState(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [purpose, setPurpose] = useState("");
  const [error, setError] = useState(null);
  const [fieldError, setFieldError] = useState("");
  const [notice, setNotice] = useState("");
  const [highlightId, setHighlightId] = useState("");
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [burstId, setBurstId] = useState("");
  const manage = Boolean(board?.can_manage);
  const round = board?.round || null;
  const open = round?.status === "open";
  const voting = open && round?.starts_at && new Date(round.starts_at).getTime() <= Date.now();

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/bell", { replace: true });
  }, [ready, user, navigate]);

  const refresh = useCallback(async () => {
    const next = await api.bell();
    setBoard(next);
    setError(null);
  }, []);

  useEffect(() => {
    if (!ready || !user) return undefined;
    let cancelled = false;
    refresh()
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/sign-in?next=/bell", { replace: true });
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
  }, [ready, user, navigate, refresh]);

  useEffect(() => {
    if (!highlightId) return;
    document.getElementById(`bell-${highlightId}`)?.scrollIntoView({ block: "center" });
  }, [highlightId, board]);

  useLiveRefresh(Boolean(user), async () => {
    try {
      setBoard(await api.bell());
    } catch {
      /* keep the list already on screen */
    }
  });

  async function run(action) {
    setBusy(true);
    setError(null);
    setFieldError("");
    setNotice("");
    try {
      return await action();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        navigate("/sign-in?next=/bell", { replace: true });
        return null;
      }
      if (err instanceof ApiError && err.code === "track_taken") {
        const existingId = fieldMessage(err, "song_id");
        setHighlightId(existingId);
        setNotice(t("bell.duplicate"));
        return null;
      }
      if (err instanceof ApiError && err.status === 422) {
        setFieldError(
          fieldMessage(err, "song_id") ||
            fieldMessage(err, "q") ||
            fieldMessage(err, "starts_at") ||
            fieldMessage(err, "ends_at") ||
            fieldMessage(err, "description") ||
            fieldMessage(err, "track_id") ||
            fieldMessage(err, "round") ||
            err.message,
        );
        return null;
      }
      setError(err);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(event) {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      setFieldError(t("bell.searchPlaceholder"));
      return;
    }
    const found = await run(() => api.searchBell(q));
    if (found) {
      setResults(found.items || []);
      setSearched(true);
    }
  }

  async function onAdd(songId) {
    const next = await run(() => api.addBellTrack(songId));
    if (next) {
      setBoard(next);
      setBurstId(next.my_vote_track_id || "");
      setResults([]);
      setQuery("");
      setSearched(false);
    }
  }

  async function onVote(trackId) {
    const next = await run(() => api.voteBell(trackId));
    if (next) {
      setBoard(next);
      setBurstId(trackId);
    }
  }

  async function onWithdraw() {
    const next = await run(() => api.withdrawBellVote());
    if (next) {
      setBoard(next);
      setBurstId("");
    }
  }

  async function onRemove(trackId) {
    const next = await run(() => api.deleteBellTrack(trackId));
    if (next) setBoard(next);
  }

  async function onOpen(event) {
    event.preventDefault();
    const startsAt = toUtcStamp(starts);
    const endsAt = toUtcStamp(ends);
    const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    if (!startsAt || !endsAt) {
      setFieldError(t("bell.timeInvalid"));
      return;
    }
    if (endsAt <= now) {
      setFieldError(t("bell.timeFuture"));
      return;
    }
    if (endsAt <= startsAt) {
      setFieldError(t("bell.timeOrder"));
      return;
    }
    const next = await run(() => api.openBellRound(startsAt, endsAt, purpose.trim()));
    if (next) {
      setBoard(next);
      setStarts("");
      setEnds("");
      setPurpose("");
    }
  }

  async function onClose() {
    if (!round?.id) return;
    const next = await run(() => api.closeBellRound(round.id));
    if (next) setBoard(next);
  }

  if (!user) return null;

  const tracks = board?.tracks || [];
  const history = board?.history || [];
  const usedToday = Boolean(board?.my_vote_track_id);
  const alreadyNominated = Boolean(board?.my_track_id) && !manage;
  const canAddSong = !usedToday && !alreadyNominated;

  const managerCard = manage ? (
    <aside className="order-1 w-full shrink-0 border border-black p-4 lg:order-2 lg:w-72">
      {open ? (
        <button type="button" className={actionClass} disabled={busy} onClick={onClose}>
          {t("bell.close")}
        </button>
      ) : (
        <form className="flex flex-col gap-3" onSubmit={onOpen}>
          <label className="font-sans text-[12px] uppercase tracking-[0.14em]">
            {t("bell.description")}
            <textarea
              maxLength={500}
              rows={4}
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              className="mt-1 block w-full border border-black px-2 py-2 font-sans text-sm normal-case tracking-normal"
            />
          </label>
          <label className="font-sans text-[12px] uppercase tracking-[0.14em]">
            {t("bell.starts")}
            <input
              type="datetime-local"
              value={starts}
              onChange={(event) => setStarts(event.target.value)}
              className="mt-1 block w-full border border-black px-2 py-2 font-sans text-sm normal-case tracking-normal"
            />
          </label>
          <label className="font-sans text-[12px] uppercase tracking-[0.14em]">
            {t("bell.ends")}
            <input
              type="datetime-local"
              value={ends}
              onChange={(event) => setEnds(event.target.value)}
              className="mt-1 block w-full border border-black px-2 py-2 font-sans text-sm normal-case tracking-normal"
            />
          </label>
          <button type="submit" className={actionClass} disabled={busy}>
            {busy ? <ButtonSpinner /> : null}
            {t("bell.open")}
          </button>
        </form>
      )}
      <FieldError message={fieldError} />
      <p className="mt-6 font-sans text-[12px] font-medium uppercase tracking-[0.14em]">{t("bell.history")}</p>
      <ul className="mt-3 border-t border-neutral-300">
        {history.length === 0 ? (
          <li className="pt-3 font-sans text-sm">{t("bell.historyEmpty")}</li>
        ) : (
          history.map((item) => (
            <li key={item.id} className="border-b border-neutral-300 py-3 font-sans text-sm leading-6">
              <p className="uppercase tracking-[0.14em]">
                {item.status === "open" ? t("bell.statusOpen") : t("bell.statusClosed")}
              </p>
              <p>
                {t("bell.starts")} {formatWhen(item.starts_at)}
              </p>
              <p>
                {t("bell.ends")} {formatWhen(item.ends_at)}
              </p>
              {item.closed_at ? (
                <p>
                  {t("bell.statusClosed")} {formatWhen(item.closed_at)}
                </p>
              ) : null}
            </li>
          ))
        )}
      </ul>
    </aside>
  ) : null;

  return (
    <main className="mx-auto w-full max-w-[68rem] px-4 py-8">
      <SectionRule first>{t("bell.title")}</SectionRule>
      <div className="mt-4 flex flex-col gap-8 lg:flex-row lg:items-start">
        <div className="order-2 min-w-0 w-full max-w-[42rem] flex-1 lg:order-1">
      <p className="font-serif text-[15px] leading-6">{t("bell.lead")}</p>
      <ErrorBanner error={error} />
      {notice ? <p className="mt-3 text-sm text-red-700">{notice}</p> : null}
      {loading ? <p className="mt-6 font-sans text-sm">…</p> : null}

      {!loading && !round ? <p className="mt-6 font-serif text-[18px]">{t("bell.empty")}</p> : null}
      {round ? (
        <p className="mt-4 font-sans text-[16px] uppercase tracking-[0.12em]">
          {t("bell.starts")} {formatWhen(round.starts_at)}
          {" · "}
          {t("bell.ends")} {formatWhen(round.ends_at)}
          {open ? "" : ` · ${t("bell.closed")}`}
        </p>
      ) : null}
      {round?.description ? (
        <p className="mt-2 whitespace-pre-wrap font-serif text-[24px] leading-8">{round.description}</p>
      ) : null}
      {open && !voting ? <p className="mt-2 font-sans text-sm">{t("bell.notStarted")}</p> : null}

      <ul className="mt-8">
        {tracks.map((track) => {
          const ownVote = board?.my_vote_track_id === track.id;
          const ownSong = Boolean(track.mine);
          const first = track.rank === 1;
          return (
            <li
              key={track.id}
              id={`bell-${track.id}`}
              className={`border-t border-neutral-300 py-4 ${highlightId === track.id ? "bg-neutral-100" : ""}`}
            >
                <div className="flex items-start gap-4">
                <span
                  className={
                    RANK_CLASS[track.rank] ||
                    "flex h-12 w-12 shrink-0 items-center justify-center border border-black font-serif text-[22px] leading-none"
                  }
                >
                  {track.rank}
                </span>
                {coverSrc(track.cover_url) ? (
                  <img src={coverSrc(track.cover_url)} alt="" className="h-14 w-14 shrink-0 object-cover" />
                ) : null}
                <div className="min-w-0 flex-1">
                  <p className={`font-serif leading-7 ${first ? "text-[26px]" : "text-[20px]"}`}>
                    {track.title}
                    {track.qualified ? (
                      <span className="ml-2 font-sans text-[12px] uppercase tracking-[0.14em]">{t("bell.qualified")}</span>
                    ) : null}
                  </p>
                  <p className="mt-1 font-sans text-sm">{track.artists}</p>
                  <p className="mt-1 font-sans text-[12px] uppercase tracking-[0.14em]">
                    <span className={ownVote ? "text-[#1A4FBF]" : ""}>{t("bell.votes", { count: track.vote_count })}</span>
                    {" · "}
                    {t("bell.addedBy", { name: track.nominated_by?.display_name || "" })}
                  </p>
                  <a className="mt-2 inline-block font-sans text-sm underline" href={track.external_url} target="_blank" rel="noreferrer">
                    {t("bell.listen")}
                  </a>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  {ownVote ? (
                    <span className={`${votedClass} ${burstId === track.id ? "bell-voted-in" : ""}`}>
                      {t("bell.voted")}
                    </span>
                  ) : null}
                  {voting && ownVote ? (
                    <button type="button" className={actionClass} disabled={busy} onClick={onWithdraw}>
                      {t("bell.withdraw")}
                    </button>
                  ) : null}
                  {voting && !ownVote ? (
                    <button type="button" className={actionClass} disabled={busy} onClick={() => onVote(track.id)}>
                      {t("bell.vote")}
                    </button>
                  ) : null}
                  {(manage || ownSong) && open ? (
                    <button type="button" className={actionClass} disabled={busy} onClick={() => onRemove(track.id)}>
                      {t("bell.remove")}
                    </button>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {open ? (
        <form className="mt-8 flex flex-wrap items-end gap-3" onSubmit={onSearch}>
          <label className="min-w-[16rem] flex-1 font-sans text-[12px] uppercase tracking-[0.14em]">
            {t("bell.search")}
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("bell.searchPlaceholder")}
              className="mt-1 block w-full border border-black px-2 py-2 font-sans text-sm normal-case tracking-normal"
            />
          </label>
          <button type="submit" className={actionClass} disabled={busy}>
            {t("bell.search")}
          </button>
        </form>
      ) : null}
      <FieldError message={fieldError} />
      {open && searched && results.length === 0 ? (
        <p className="mt-4 font-sans text-sm">{t("bell.noResults")}</p>
      ) : null}

      {open && results.length ? (
        <ul className="mt-4 divide-y divide-neutral-300 border-y border-neutral-300">
          {results.map((item) => {
            const already = tracks.find((track) => track.song_id === item.song_id);
            return (
              <li key={item.song_id} className="flex items-center justify-between gap-4 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  {coverSrc(item.cover_url) ? (
                    <img src={coverSrc(item.cover_url)} alt="" className="h-12 w-12 shrink-0 object-cover" />
                  ) : null}
                  <div>
                  <p className="font-serif text-[18px]">{item.title}</p>
                  <p className="font-sans text-sm">{item.artists}</p>
                  <a className="font-sans text-sm underline" href={item.external_url} target="_blank" rel="noreferrer">
                    {t("bell.listen")}
                  </a>
                  </div>
                </div>
                {already && board?.my_vote_track_id === already.id ? (
                  <span className={`${votedClass} ${burstId === already.id ? "bell-voted-in" : ""}`}>
                    {t("bell.voted")}
                  </span>
                ) : null}
                {already && voting && board?.my_vote_track_id !== already.id ? (
                  <button type="button" className={actionClass} disabled={busy} onClick={() => onVote(already.id)}>
                    {t("bell.vote")}
                  </button>
                ) : null}
                {!already && canAddSong ? (
                  <button type="button" className={actionClass} disabled={busy} onClick={() => onAdd(item.song_id)}>
                    {t("bell.add")}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
        </div>
        {managerCard}
      </div>
    </main>
  );
}
