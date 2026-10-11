import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { formatRelative } from "../format";
import { useI18n } from "../i18n";
import { TitleLine } from "./ui";
import { Avatar } from "./Avatar";

function CommentIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 8.25h9m-9 3.75h5.25M21 12a8.96 8.96 0 0 1-1.5 4.95l.75 3.3-3.45-.75A9 9 0 1 1 21 12Z"
      />
    </svg>
  );
}

export function LikeIcon({ filled }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.8"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 21V10.5H4.5v10.5h3Zm12.75-9.75c0-.83-.67-1.5-1.5-1.5h-4.19l.63-3.03a1.5 1.5 0 0 0-1.47-1.82h-.22L9 9.75V21h9.38c.71 0 1.32-.5 1.46-1.19l1.16-6.19c.08-.42-.02-.85-.25-1.2-.23-.34-.58-.57-.99-.57h-.01Z"
      />
    </svg>
  );
}

export function ForumLikeButton({ post, signInNext, className = "" }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [likeCount, setLikeCount] = useState(post.like_count ?? 0);
  const [liked, setLiked] = useState(Boolean(post.liked));
  const [pop, setPop] = useState(0);
  const savingRef = useRef(false);

  useEffect(() => {
    if (savingRef.current) return;
    setLikeCount(post.like_count ?? 0);
    setLiked(Boolean(post.liked));
  }, [post.id, post.like_count, post.liked]);

  async function onLike() {
    if (!user) {
      navigate(signInNext);
      return;
    }
    if (savingRef.current) return;
    const previousLiked = liked;
    const previousCount = likeCount;
    const nextLiked = !liked;
    setLiked(nextLiked);
    setLikeCount(Math.max(0, likeCount + (nextLiked ? 1 : -1)));
    setPop((current) => current + 1);
    savingRef.current = true;
    try {
      const result = nextLiked ? await api.likePost(post.id) : await api.unlikePost(post.id);
      setLikeCount(result.like_count);
      setLiked(result.liked);
    } catch (err) {
      setLiked(previousLiked);
      setLikeCount(previousCount);
      if (err instanceof ApiError && err.status === 401) {
        navigate(signInNext);
      }
    } finally {
      savingRef.current = false;
    }
  }

  return (
    <button
      type="button"
      onClick={onLike}
      className={`flex items-center gap-1.5 font-sans text-sm ${liked ? "text-[#1A4FBF]" : "text-neutral-500"} ${className}`}
      aria-label={liked ? t("forum.unlike") : t("forum.like")}
      aria-pressed={liked}
    >
      <span key={pop} className={pop ? "like-pop" : "inline-flex"}>
        <LikeIcon filled={liked} />
      </span>
      <span>{likeCount}</span>
    </button>
  );
}

export function CommunityCard({ post, onDelete = null }) {
  const { lang, t } = useI18n();
  const replies = post.reply_count ?? 0;

  return (
    <article className="mb-3 rounded-2xl bg-[#F4F5F7] p-4">
      <div className="flex gap-3">
        <Avatar avatar={post.author?.avatar} size={44} className="rounded-full" />
        <div className="min-w-0 flex-1">
          <p className="font-sans text-sm font-medium text-[#111111]">{post.author?.display_name}</p>
          <p className="mt-0.5 font-sans text-xs text-neutral-500">{formatRelative(post.created_at, lang)}</p>
          <Link to={`/posts/${post.id}`} className="mt-3 block font-sans text-[15px] font-medium leading-6 text-[#111111]">
            {post.title}
          </Link>
          {post.excerpt ? (
            <p className="mt-1 whitespace-pre-wrap font-sans text-sm leading-6 text-neutral-700">{post.excerpt}</p>
          ) : null}
          {post.images?.[0] ? (
            <img
              src={uploadSrc(post.images[0])}
              alt=""
              className="mt-3 max-h-64 w-full rounded-xl object-cover"
            />
          ) : null}
          <div className="mt-4 flex items-center gap-10 text-neutral-500">
            <Link
              to={`/posts/${post.id}`}
              className="flex items-center gap-1.5 font-sans text-sm"
              aria-label={t("forum.comments", { count: replies })}
            >
              <CommentIcon />
              <span>{replies}</span>
            </Link>
            <ForumLikeButton post={post} signInNext="/sign-in?next=/forum" />
            {onDelete ? (
              <button
                type="button"
                onClick={onDelete}
                className="ml-auto font-sans text-[11px] uppercase tracking-[0.14em] text-red-700"
              >
                {t("post.delete")}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </article>
  );
}

export function CommunityCardSkeleton() {
  return (
    <div className="mb-3 flex gap-3 rounded-2xl bg-[#F4F5F7] p-4">
      <div className="h-11 w-11 rounded-full bg-[#D6DEEE]" />
      <div className="flex flex-1 flex-col justify-center gap-3">
        <TitleLine />
        <TitleLine className="w-1/3" />
      </div>
    </div>
  );
}
