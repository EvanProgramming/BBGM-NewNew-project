import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { Avatar } from "../components/Avatar";
import { ForumLikeButton } from "../components/CommunityCard";
import { AiBadge, ErrorBanner, FieldError, FrontPageLink, Headline, ImageWell, Kicker, SafeImage, TitleLine, ButtonSpinner } from "../components/ui";
import { canDeletePosts, canPinPosts, formatDateline, forumListPath, newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { mergeLiveFloors, useLiveRefresh } from "../live";

export default function PostDetail() {
  const { postId } = useParams();
  const location = useLocation();
  const { user, setUser } = useAuth();
  const { lang, t } = useI18n();
  const navigate = useNavigate();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [comments, setComments] = useState([]);
  const [commentTotal, setCommentTotal] = useState(0);
  const [commentPage, setCommentPage] = useState(1);
  const [commentError, setCommentError] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [pinning, setPinning] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [commentBody, setCommentBody] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [withdrawingCommentId, setWithdrawingCommentId] = useState(null);
  const [ready, setReady] = useState(false);
  const commentPageRef = useRef(1);
  commentPageRef.current = commentPage;

  useEffect(() => {
    let cancelled = false;
    let denied = false;
    setLoading(true);
    setReady(false);
    setPost(null);
    setComments([]);
    setCommentError(null);
    api
      .getPost(postId)
      .then((data) => {
        if (cancelled) return;
        setPost(data);
        setError(null);
        if (data.category === "forum") {
          return api.listComments(postId).then((thread) => {
            if (cancelled) return;
            setComments(thread.items);
            setCommentPage(thread.page);
            setCommentTotal(thread.total);
          });
        }
        return null;
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          denied = true;
          navigate(`/sign-in?next=${encodeURIComponent(`/posts/${postId}`)}`, { replace: true });
          return;
        }
        setPost(null);
        setError(err);
      })
      .finally(() => {
        if (cancelled || denied) return;
        setLoading(false);
        setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [navigate, postId]);

  const refreshThread = useCallback(async () => {
    const data = await api.getPost(postId);
    setPost(data);
    setError(null);
    if (data.category !== "forum") return;
    const pageSize = 20;
    const loadedPages = commentPageRef.current;
    let floors = [];
    let total = 0;
    for (let page = 1; page <= loadedPages; page += 1) {
      const chunk = await api.listComments(postId, { page, pageSize });
      floors = mergeLiveFloors(floors, chunk.items);
      total = chunk.total;
    }
    if (total > floors.length) {
      const extra = await api.listComments(postId, { page: loadedPages + 1, pageSize });
      floors = mergeLiveFloors(floors, extra.items);
      total = extra.total;
      setCommentPage(loadedPages + 1);
    }
    setComments(floors);
    setCommentTotal(total);
  }, [postId]);

  const notFound = error instanceof ApiError && error.code === "not_found";
  const isForum = post?.category === "forum";
  const forumBack = forumListPath(location.state?.forumBack) || (isForum ? "/forum" : null);

  useLiveRefresh(ready && !commentSubmitting && !notFound, refreshThread);

  async function onWithdraw() {
    if (!post || !window.confirm(t("post.withdrawConfirm"))) return;
    setWithdrawing(true);
    setError(null);
    try {
      await api.withdrawNewsSubmission(postId);
      const topic = post.news_categories?.[0];
      navigate(topic ? `/?topic=${encodeURIComponent(topic)}` : "/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=/posts/${postId}`);
        return;
      }
      setError(err);
    } finally {
      setWithdrawing(false);
    }
  }

  async function onPin() {
    if (!post) return;
    setPinning(true);
    setError(null);
    try {
      setPost(await api.pinPost(postId, !post.pinned));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=/posts/${postId}`);
        return;
      }
      setError(err);
    } finally {
      setPinning(false);
    }
  }

  async function onDelete() {
    if (!post || !window.confirm(t("post.deleteConfirm"))) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deletePost(postId);
      const ownForum = post.category === "forum" && post.author?.id === user?.id;
      const back = post.category === "news" ? "/" : ownForum ? "/forum/mine" : "/forum";
      navigate(back);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=/posts/${postId}`);
        return;
      }
      setError(err);
    } finally {
      setDeleting(false);
    }
  }

  async function onComment(event) {
    event.preventDefault();
    if (!user) {
      navigate(`/sign-in?next=/posts/${postId}`);
      return;
    }
    setCommentSubmitting(true);
    setCommentError(null);
    try {
      await api.createComment(postId, {
        body: commentBody,
      });
      const thread = await api.listComments(postId, { page: 1 });
      setComments(thread.items);
      setCommentPage(thread.page);
      setCommentTotal(thread.total);
      setCommentBody("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=/posts/${postId}`);
        return;
      }
      setCommentError(err);
    } finally {
      setCommentSubmitting(false);
    }
  }

  async function onWithdrawComment(commentId, authorId) {
    if (withdrawingCommentId) return;
    const own = authorId === user?.id;
    if (!window.confirm(t(own ? "post.withdrawCommentConfirm" : "post.deleteCommentConfirm"))) return;
    setWithdrawingCommentId(commentId);
    setCommentError(null);
    try {
      await api.deleteComment(postId, commentId);
      const isFloor = comments.some((item) => item.id === commentId);
      setComments((current) =>
        current
          .filter((item) => item.id !== commentId)
          .map((item) => ({
            ...item,
            replies: (item.replies || []).filter((reply) => reply.id !== commentId),
          })),
      );
      if (isFloor) setCommentTotal((count) => Math.max(0, count - 1));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=/posts/${postId}`);
        return;
      }
      setCommentError(err);
    } finally {
      setWithdrawingCommentId(null);
    }
  }

  async function loadOlderComments() {
    const next = commentPage + 1;
    try {
      const thread = await api.listComments(postId, { page: next });
      setComments((current) => [...current, ...thread.items]);
      setCommentPage(thread.page);
      setCommentTotal(thread.total);
    } catch (err) {
      setCommentError(err);
    }
  }

  return (
    <article className="mx-auto mt-10 min-w-0 max-w-[46rem]">
      <FrontPageLink to={forumBack || "/"} labelKey={forumBack ? "link.forum" : "link.front"} />
      {loading ? (
        <>
          <ImageWell className="h-64" />
          <TitleLine className="mt-6 w-full" />
          <TitleLine className="mt-3 w-2/3" />
        </>
      ) : notFound ? (
        <h1 className="font-serif text-4xl">{t("post.missing")}</h1>
      ) : error ? (
        <ErrorBanner error={error} />
      ) : (
        <>
          {post.pinned ? (
            <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">{t("post.pinned")}</p>
          ) : null}
          <Kicker category={post.category} />
          <Headline className="mt-2 text-4xl [overflow-wrap:anywhere] sm:text-5xl">{post.title}</Headline>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {isForum ? <Avatar avatar={post.author?.avatar} size={48} /> : null}
            {post.author?.is_agent ? <AiBadge /> : null}
            <p className="font-sans text-[15px] font-semibold text-neutral-600">
              {post.author?.display_name}
              {post.created_at ? ` · ${formatDateline(post.created_at, lang)}` : ""}
            </p>
          </div>
          {post.images?.length ? (
              <div className="mt-6 grid gap-3">
                {post.images.map((src) => (
                  <div key={src} className="zoom-frame border border-black bg-[#D6DEEE]">
                    <SafeImage src={uploadSrc(src)} className="w-full object-contain" />
                  </div>
                ))}
              </div>
            ) : null}
          {post.category === "news" && post.news_categories?.length ? (
            <p className="mt-4 font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>
          ) : null}
          {post.category === "news" && post.blocks?.length && !post.news_categories?.length ? (
            <div className="mt-8 space-y-8">
              {post.blocks.map((block) => (
                <section key={block.id} className="border-b border-neutral-300 pb-8 last:border-b-0">
                  <h2 className="font-serif text-3xl font-bold">{block.heading}</h2>
                  <div className="mt-3 whitespace-pre-wrap font-sans text-[17px] font-medium leading-8 text-neutral-900">
                    {block.body}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className={`mt-8 whitespace-pre-wrap font-sans text-[17px] font-medium leading-8 text-neutral-900 [overflow-wrap:anywhere] ${isForum ? "rounded-2xl bg-[#F4F5F7] p-5" : ""}`}>
              {post.body}
            </div>
          )}

          {isForum ? (
            <ForumLikeButton post={post} signInNext={`/sign-in?next=/posts/${post.id}`} className="mt-6" />
          ) : null}

          {canPinPosts(user) ? (
            <button
              type="button"
              onClick={onPin}
              disabled={pinning || deleting || withdrawing}
              className="mt-8 mr-6 inline-flex items-center gap-2 font-sans text-[11px] uppercase tracking-[0.18em] text-[#1A4FBF] disabled:opacity-40"
            >
              {pinning ? <ButtonSpinner /> : null}
              {post.pinned ? t("post.unpin") : t("post.pin")}
            </button>
          ) : null}

          {canDeletePosts(user) && post.category === "news" && post.news_categories?.length ? (
            <button
              type="button"
              onClick={onWithdraw}
              disabled={withdrawing || deleting}
              className="mt-8 mr-6 inline-flex items-center gap-2 font-sans text-[11px] uppercase tracking-[0.18em] text-[#1A4FBF] disabled:opacity-40"
            >
              {withdrawing ? <ButtonSpinner /> : null}
              {t("post.withdraw")}
            </button>
          ) : null}

          {canDeletePosts(user) || (isForum && post.author?.id === user?.id) ? (
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting || withdrawing}
              className="mt-8 inline-flex items-center gap-2 font-sans text-[11px] uppercase tracking-[0.18em] text-red-700 disabled:opacity-40"
            >
              {deleting ? <ButtonSpinner /> : null}
              {t("post.delete")}
            </button>
          ) : null}

          {isForum ? (
            <section className="mt-12 border-t border-black pt-8">
              <h2 className="font-serif text-2xl">{t("post.comments")}</h2>
              <ErrorBanner error={commentError && !commentError.fields?.length ? commentError : null} />
              {comments.length === 0 ? (
                <p className="mt-4 font-sans text-sm text-neutral-500">{t("post.none")}</p>
              ) : (
                comments.map((item) => (
                  <div key={item.id} className="mt-6 border-t border-neutral-200 pt-4">
                    <div className="flex items-center gap-3">
                      <Avatar avatar={item.author?.avatar} size={28} />
                      <p className="font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]">
                        {item.author?.display_name}
                      </p>
                      {item.author?.is_agent ? <AiBadge /> : null}
                      {user?.id && (item.author?.id === user.id || canDeletePosts(user)) ? (
                        <button
                          type="button"
                          onClick={() => onWithdrawComment(item.id, item.author?.id)}
                          disabled={withdrawingCommentId === item.id}
                          className="ml-auto font-sans text-[11px] uppercase tracking-[0.14em] text-red-700 disabled:opacity-40"
                        >
                          {t(item.author?.id === user.id ? "post.withdrawComment" : "post.delete")}
                        </button>
                      ) : null}
                    </div>
                    <p className="mt-2 whitespace-pre-wrap font-sans text-sm leading-6 [overflow-wrap:anywhere]">{item.body}</p>
                    {item.replies?.map((reply) => (
                      <div key={reply.id} className="mt-3 ml-6 flex min-w-0 gap-2 border-l border-black pl-4">
                        <Avatar avatar={reply.author?.avatar} size={22} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <p className="font-sans text-[11px] text-neutral-500">{reply.author?.display_name}</p>
                            {reply.author?.is_agent ? <AiBadge /> : null}
                            {user?.id && (reply.author?.id === user.id || canDeletePosts(user)) ? (
                              <button
                                type="button"
                                onClick={() => onWithdrawComment(reply.id, reply.author?.id)}
                                disabled={withdrawingCommentId === reply.id}
                                className="ml-auto font-sans text-[11px] uppercase tracking-[0.14em] text-red-700 disabled:opacity-40"
                              >
                                {t(reply.author?.id === user.id ? "post.withdrawComment" : "post.delete")}
                              </button>
                            ) : null}
                          </div>
                          <p className="mt-1 min-w-0 whitespace-pre-wrap font-sans text-sm leading-6 [overflow-wrap:anywhere]">{reply.body}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ))
              )}
              {commentTotal > comments.length ? (
                <button
                  type="button"
                  onClick={loadOlderComments}
                  className="mt-6 font-sans text-sm uppercase tracking-[0.14em] text-[#1A4FBF]"
                >
                  {t("post.older")}
                </button>
              ) : null}

              {user ? (
                <form onSubmit={onComment} className="mt-8">
                  <label className="block font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="comment-body">
                    {t("post.comment")}
                  </label>
                  <textarea
                    id="comment-body"
                    value={commentBody}
                    onChange={(event) => setCommentBody(event.target.value)}
                    rows={4}
                    className="mt-2 w-full resize-y overflow-x-hidden border border-black p-3 font-sans text-sm outline-none [overflow-wrap:anywhere]"
                  />
                  <FieldError message={fieldMessage(commentError, "body")} />
                  <button
                    type="submit"
                    disabled={commentSubmitting}
                    className="mt-4 inline-flex items-center gap-2 rounded-[2px] bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.18em] text-white disabled:opacity-40"
                  >
                    {commentSubmitting ? <ButtonSpinner /> : null}
                    {t("post.postComment")}
                  </button>
                </form>
              ) : (
                <p className="mt-6 font-sans text-sm text-neutral-500">
                  <Link to={`/sign-in?next=/posts/${postId}`} className="text-[#1A4FBF]">
                    {t("post.signInToComment")}
                  </Link>{" "}
                  {t("post.toComment")}
                </p>
              )}
            </section>
          ) : null}
        </>
      )}
    </article>
  );
}
