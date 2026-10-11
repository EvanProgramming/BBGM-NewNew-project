import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { Avatar } from "../components/Avatar";
import { LikeIcon } from "../components/CommunityCard";
import { ErrorBanner, FieldError, FrontPageLink, Headline, ImageWell, Kicker, TitleLine, ButtonSpinner } from "../components/ui";
import { canDeletePosts, formatDateline } from "../format";
import { useI18n } from "../i18n";
import { mergeLiveFloors, useLiveRefresh } from "../live";

function ForumLike({ post }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [likeCount, setLikeCount] = useState(post.like_count ?? 0);
  const [liked, setLiked] = useState(Boolean(post.liked));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (saving) return;
    setLikeCount(post.like_count ?? 0);
    setLiked(Boolean(post.liked));
  }, [post.id, post.like_count, post.liked, saving]);

  async function onLike() {
    if (!user) {
      navigate(`/sign-in?next=/posts/${post.id}`);
      return;
    }
    if (saving) return;
    setSaving(true);
    try {
      const result = liked ? await api.unlikePost(post.id) : await api.likePost(post.id);
      setLikeCount(result.like_count);
      setLiked(result.liked);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        navigate(`/sign-in?next=/posts/${post.id}`);
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <button
      type="button"
      onClick={onLike}
      disabled={saving}
      className={`mt-6 flex items-center gap-1.5 font-sans text-sm ${liked ? "text-[#1A4FBF]" : "text-neutral-500"}`}
      aria-label={liked ? t("forum.unlike") : t("forum.like")}
      aria-pressed={liked}
    >
      <LikeIcon filled={liked} />
      {saving ? <ButtonSpinner /> : null}
      <span>{likeCount}</span>
    </button>
  );
}

export default function PostDetail() {
  const { postId } = useParams();
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
  const [commentBody, setCommentBody] = useState("");
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [ready, setReady] = useState(false);
  const commentPageRef = useRef(1);
  commentPageRef.current = commentPage;

  useEffect(() => {
    let cancelled = false;
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
        setPost(null);
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
  }, [postId]);

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

  useLiveRefresh(ready && !commentSubmitting && !notFound, refreshThread);

  async function onDelete() {
    if (!post || !window.confirm(t("post.deleteConfirm"))) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deletePost(postId);
      const back = post.category === "news" ? "/" : "/forum";
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
    <article className="mx-auto mt-10 max-w-[42rem]">
      <FrontPageLink />
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
          <Kicker category={post.category} />
          <Headline className="mt-2 text-4xl sm:text-5xl">{post.title}</Headline>
          <div className="mt-3 flex items-center gap-3">
            {isForum ? <Avatar avatar={post.author?.avatar} size={48} /> : null}
            <p className="font-sans text-sm text-neutral-500">
              {post.author?.display_name}
              {post.created_at ? ` · ${formatDateline(post.created_at, lang)}` : ""}
            </p>
          </div>
          {post.images?.length ? (
              <div className="mt-6 grid gap-3">
                {post.images.map((src) => (
                  <img
                    key={src}
                    src={uploadSrc(src)}
                    alt=""
                    className="w-full border border-black object-contain"
                  />
                ))}
              </div>
            ) : null}
          {post.category === "news" && post.news_categories?.length ? (
            <p className="mt-4 font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">{post.news_categories.join(" · ")}</p>
          ) : null}
          {post.category === "news" && post.blocks?.length && !post.news_categories?.length ? (
            <div className="mt-8 space-y-8">
              {post.blocks.map((block) => (
                <section key={block.id}>
                  <h2 className="font-serif text-2xl">{block.heading}</h2>
                  <div className="mt-3 whitespace-pre-wrap font-sans text-[16px] leading-7 text-neutral-900">
                    {block.body}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className="mt-8 whitespace-pre-wrap font-sans text-[16px] leading-7 text-neutral-900">
              {post.body}
            </div>
          )}

          {isForum ? <ForumLike post={post} /> : null}

          {canDeletePosts(user) ? (
            <button
              type="button"
              onClick={onDelete}
              disabled={deleting}
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
                    </div>
                    <p className="mt-2 whitespace-pre-wrap font-sans text-sm leading-6">{item.body}</p>
                    {item.replies?.map((reply) => (
                      <div key={reply.id} className="mt-3 ml-6 flex gap-2 border-l border-black pl-4">
                        <Avatar avatar={reply.author?.avatar} size={22} />
                        <div>
                          <p className="font-sans text-[11px] text-neutral-500">{reply.author?.display_name}</p>
                          <p className="mt-1 whitespace-pre-wrap font-sans text-sm leading-6">{reply.body}</p>
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
                    className="mt-2 w-full border border-black p-3 font-sans text-sm outline-none"
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
