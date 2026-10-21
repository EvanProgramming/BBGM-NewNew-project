import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { CommunityCard, CommunityCardSkeleton } from "../components/CommunityCard";
import ComposeForm from "../components/ComposeForm";
import { EmptyCategory, StoryRow, StoryRowSkeleton } from "../components/StoryRow";
import { ErrorBanner, FrontPageLink, SectionRule } from "../components/ui";
import { canDeletePosts } from "../format";
import { useI18n } from "../i18n";
import { ChessMark } from "../play/marks";
import { mergeLivePosts, useLiveRefresh } from "../live";

function forumQueryKey(userKey) {
  return `elegram_forum_q:${userKey}`;
}

function readForumQuery(userKey) {
  try {
    return localStorage.getItem(forumQueryKey(userKey)) || "";
  } catch {
    return "";
  }
}

function writeForumQuery(userKey, value) {
  try {
    if (value) localStorage.setItem(forumQueryKey(userKey), value);
    else localStorage.removeItem(forumQueryKey(userKey));
  } catch {
    /* private mode */
  }
}

function SearchIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[15px] w-[15px] shrink-0 text-[#1A4FBF]"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16.2 16.2 4.3 4.3" />
    </svg>
  );
}

function ComposeFab({ to, onClick }) {
  const { t } = useI18n();
  const className =
    "fixed bottom-6 right-6 z-20 flex h-14 w-14 items-center justify-center rounded-full bg-[#1A4FBF] text-[2rem] leading-none text-white";
  if (to) {
    return (
      <Link to={to} className={className} aria-label={t("forum.write")}>
        +
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={className} aria-label={t("forum.write")}>
      +
    </button>
  );
}

function recommendScore(post) {
  return 0.6 * (post.like_count ?? 0) + 0.4 * (post.reply_count ?? 0);
}

function placePublished(current, post, feed) {
  const rest = current.filter((item) => item.id !== post.id);
  if (feed === "recommended") {
    const next = [...rest, post];
    next.sort((left, right) => {
      const score = recommendScore(right) - recommendScore(left);
      if (score) return score;
      return String(right.created_at).localeCompare(String(left.created_at));
    });
    return next.slice(0, 10);
  }
  if (feed === "latest") return [post, ...rest].slice(0, 10);
  return [post, ...rest];
}

export default function Category({ category, title, feed }) {
  const { user, ready: authReady } = useAuth();
  const navigate = useNavigate();
  const { t } = useI18n();
  const heading = category === "forum" ? t("nav.forum") : title;
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [writing, setWriting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [ready, setReady] = useState(false);

  const isForum = category === "forum";
  const userKey = user?.id || "guest";
  const [draft, setDraft] = useState("");
  const [keyword, setKeyword] = useState("");
  const [syncedKey, setSyncedKey] = useState(null);
  const searchReady = !isForum || (authReady && syncedKey === userKey);

  if (isForum && authReady && syncedKey !== userKey) {
    const stored = readForumQuery(userKey);
    setDraft(stored);
    setKeyword(stored);
    setSyncedKey(userKey);
  }

  useEffect(() => {
    if (!searchReady) return undefined;
    if (feed === "mine" && !authReady) return undefined;
    if (feed === "mine" && !user) {
      navigate("/sign-in?next=/forum/mine", { replace: true });
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setReady(false);
    setWriting(false);
    api
      .listPosts({ category, feed, page: 1, pageSize: 20, q: keyword })
      .then((data) => {
        if (cancelled) return;
        setItems(data.items);
        setPage(data.page);
        setPageSize(data.page_size);
        setTotal(data.total);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        setError(err);
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, category, feed, keyword, navigate, searchReady, user]);

  const refreshList = useCallback(
    () =>
      api.listPosts({ category, feed, page: 1, pageSize, q: keyword }).then((data) => {
        setItems((current) => (feed === "all" ? mergeLivePosts(current, data.items) : data.items));
        setPageSize(data.page_size);
        setTotal(data.total);
        setError(null);
      }),
    [category, feed, keyword, pageSize],
  );

  useLiveRefresh(ready && (feed !== "mine" || Boolean(user)), refreshList);

  useEffect(() => {
    if (!writing) return undefined;
    function onKey(event) {
      if (event.key === "Escape" && !publishing) setWriting(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [writing, publishing]);

  function loadOlder() {
    const next = page + 1;
    setLoadingMore(true);
    api
      .listPosts({ category, feed, page: next, pageSize, q: keyword })
      .then((data) => {
        setItems((current) => [...current, ...data.items]);
        setPage(data.page);
        setPageSize(data.page_size);
        setTotal(data.total);
        setError(null);
      })
      .catch((err) => setError(err))
      .finally(() => setLoadingMore(false));
  }

  async function removeOwn(post) {
    if (!window.confirm(t("post.deleteConfirm"))) return;
    try {
      await api.deletePost(post.id);
      setItems((current) => current.filter((item) => item.id !== post.id));
      setTotal((current) => Math.max(0, current - 1));
      setError(null);
    } catch (err) {
      setError(err);
    }
  }

  function onPublished(post) {
    setItems((current) => placePublished(current, post, feed));
    setTotal((current) => (feed === "recommended" || feed === "latest" ? Math.min(10, current + 1) : current + 1));
    setWriting(false);
  }

  function onSearch(event) {
    event.preventDefault();
    const next = draft.trim();
    setDraft(next);
    setKeyword(next);
    writeForumQuery(userKey, next);
  }

  function onClearSearch() {
    setDraft("");
    setKeyword("");
    writeForumQuery(userKey, "");
  }

  const hasOlder = feed === "all" && total > page * pageSize;
  const column = isForum ? "mx-auto w-full max-w-[42rem]" : "";

  return (
    <div className="mt-8">
      <FrontPageLink />
      <div className={isForum ? "relative" : ""}>
      <div className={column}>
      <SectionRule>{heading}</SectionRule>
      {isForum ? (
        <Link
          to="/play"
          aria-label={t("play.markLabel")}
          className="mb-6 inline-flex flex-col items-center text-black min-[1120px]:hidden"
        >
          <ChessMark className="h-14 w-14" />
          <span className="mt-1 text-center font-sans text-[12px] font-semibold tracking-[0.02em]">
            {t("play.markLabel")}
          </span>
        </Link>
      ) : null}
      {isForum ? (
        <form onSubmit={onSearch} className="mb-6 flex items-end gap-3">
          <div className="flex min-w-0 max-w-[18rem] flex-1 items-end gap-2">
            <label className="sr-only" htmlFor="forum-search">
              {t("forum.search")}
            </label>
            <SearchIcon />
            <input
              id="forum-search"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("forum.searchPlaceholder")}
              className="w-full border-0 border-b border-black bg-transparent pb-[3px] font-sans text-[13px] font-normal text-[#111111] outline-none placeholder:text-neutral-400"
            />
          </div>
          {draft || keyword ? (
            <button
              type="button"
              onClick={onClearSearch}
              className="shrink-0 font-sans text-[11px] uppercase tracking-[0.12em] text-neutral-500"
            >
              {t("forum.searchClear")}
            </button>
          ) : null}
        </form>
      ) : null}
      <ErrorBanner error={error} />
      {loading ? (
        isForum ? (
          <>
            <CommunityCardSkeleton />
            <CommunityCardSkeleton />
            <CommunityCardSkeleton />
          </>
        ) : (
          <>
            <StoryRowSkeleton />
            <StoryRowSkeleton />
            <StoryRowSkeleton />
          </>
        )
      ) : items.length === 0 ? (
        feed === "mine" ? (
          <p className="mt-6 font-serif text-2xl">{t("forum.mineEmpty")}</p>
        ) : (
          <EmptyCategory name={heading} />
        )
      ) : (
        <>
          {items.map((post) =>
            isForum ? (
              <CommunityCard
                key={post.id}
                post={post}
                onDelete={feed === "mine" || canDeletePosts(user) ? () => removeOwn(post) : null}
              />
            ) : (
              <StoryRow key={post.id} post={post} />
            ),
          )}
          {hasOlder ? (
            <button
              type="button"
              onClick={loadOlder}
              disabled={loadingMore}
              className="mt-6 font-sans text-sm uppercase tracking-[0.14em] text-[#1A4FBF]"
            >
              {t("forum.older")}
            </button>
          ) : null}
        </>
      )}
      </div>
      {isForum ? (
        <Link
          to="/play"
          aria-label={t("play.markLabel")}
          className="absolute right-0 top-12 hidden flex-col items-center text-black min-[1120px]:flex"
        >
          <ChessMark className="h-16 w-16" />
          <span className="mt-1 text-center font-sans text-[12px] font-semibold tracking-[0.02em]">
            {t("play.markLabel")}
          </span>
        </Link>
      ) : null}
      </div>
      {isForum && !writing ? (
        user ? (
          <ComposeFab onClick={() => setWriting(true)} />
        ) : (
          <ComposeFab to="/sign-in?next=/forum" />
        )
      ) : null}
      {isForum && writing ? (
        <div className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-10">
          <button
            type="button"
            className="absolute inset-0 cursor-default"
            aria-label={t("forum.close")}
            onClick={() => {
              if (!publishing) setWriting(false);
            }}
          />
          <div className="relative z-10 w-full max-w-2xl bg-white p-8">
            <ComposeForm
              category={category}
              onPublished={onPublished}
              onCancel={() => {
                if (!publishing) setWriting(false);
              }}
              onBusy={setPublishing}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function StaticCategory() {
  const { t } = useI18n();
  const title = t("nav.opinion");
  return (
    <div className="mt-8">
      <FrontPageLink />
      <SectionRule>{title}</SectionRule>
      <EmptyCategory name={title} />
    </div>
  );
}
