import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { formatDateline, newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { uploadSrc } from "../avatar";

export function ButtonSpinner() {
  return (
    <span
      className="inline-block h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
      aria-hidden="true"
    />
  );
}

export function SafeImage({ src, alt = "", className = "h-full w-full object-cover" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [src]);
  if (!src || failed) {
    return <div className="zoom-target image-well-fill h-full w-full" />;
  }
  return <img src={src} alt={alt} onError={() => setFailed(true)} className={className} />;
}

export function ImageWell({ className = "h-40", src, alt = "" }) {
  return (
    <div className={`zoom-frame bg-[#D6DEEE] ${className}`} aria-hidden={src ? undefined : "true"}>
      <SafeImage src={src} alt={alt} />
    </div>
  );
}

export function TitleLine({ className = "h-0.5 w-3/4 bg-neutral-200" }) {
  return <div className={className} />;
}

export function ErrorBanner({ error }) {
  if (!error?.message) return null;
  return <p className="mb-4 text-sm text-red-700">{error.message}</p>;
}

export function FieldError({ message }) {
  if (!message) return null;
  return <p className="mt-1 text-xs text-red-700">{message}</p>;
}

export function ManualPasswordInput({ id, value, onChange }) {
  return (
    <input
      id={id}
      type="text"
      name={`${id}-manual`}
      autoComplete="off"
      autoCorrect="off"
      autoCapitalize="none"
      spellCheck={false}
      data-1p-ignore="true"
      data-lpignore="true"
      data-form-type="other"
      value={value}
      onChange={onChange}
      className="mt-2 w-full border-0 border-b border-black py-2 font-sans text-sm outline-none [-webkit-text-security:disc]"
    />
  );
}

export function FrontPageLink({ to = "/", labelKey = "link.front" }) {
  const { t } = useI18n();
  return (
    <p className="mb-6 font-sans text-[13px] font-bold uppercase tracking-[0.14em]">
      <Link to={to} className="text-link text-[#1A4FBF]">
        {t(labelKey)}
      </Link>
    </p>
  );
}

export function Kicker({ category }) {
  const { t } = useI18n();
  if (!category) return null;
  const key = category === "forum" ? "category.forum" : "category.news";
  return (
    <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">
      {t(key)}
    </p>
  );
}

export function Headline({ to, children, className = "text-[1.35rem] font-bold" }) {
  const classes = `font-serif leading-[1.12] tracking-[-0.02em] text-[#111111] ${className}`;
  if (to) {
    return (
      <h3 className={classes}>
        <Link to={to} className="text-link">
          {children}
        </Link>
      </h3>
    );
  }
  return <h1 className={classes}>{children}</h1>;
}

export function Dek({ children }) {
  if (!children) return null;
  return <p className="mt-2 font-sans text-[16px] font-medium leading-relaxed text-neutral-800">{children}</p>;
}

export function Dateline({ iso }) {
  const { lang } = useI18n();
  if (!iso) return null;
  return <p className="mt-1 font-sans text-[13px] font-medium text-neutral-500">{formatDateline(iso, lang)}</p>;
}

export function Byline({ post, className = "" }) {
  const { lang, t } = useI18n();
  if (!post) return null;
  const author = post.author?.display_name;
  return (
    <p
      className={`mt-2 flex flex-wrap items-center gap-x-1.5 font-sans text-[12px] font-semibold uppercase tracking-[0.05em] text-neutral-600 ${className}`}
    >
      {author ? <span>{t("meta.by", { name: author })}</span> : null}
      {author && post.created_at ? <span aria-hidden="true">·</span> : null}
      {post.created_at ? (
        <time dateTime={post.created_at}>{formatDateline(post.created_at, lang)}</time>
      ) : null}
    </p>
  );
}

export function SectionRule({ children, first = false }) {
  return (
    <div className={`mb-7 flex items-center gap-5 border-t border-neutral-200 ${first ? "mt-0 pt-0" : "mt-14 pt-8"}`}>
      <h2 className="font-serif text-[40px] font-extrabold leading-none tracking-[-0.02em] sm:text-[44px]">{children}</h2>
      <div className="h-[4px] flex-1 bg-black" />
    </div>
  );
}

export function CompactStoryRow({ post, className = "" }) {
  if (!post) {
    return (
      <article className={`grid grid-cols-[6.5rem_1fr] gap-4 border-b border-neutral-300 pb-5 sm:grid-cols-[9rem_1fr] ${className}`}>
        <ImageWell className="h-24 sm:h-28" />
        <div className="flex flex-col justify-center gap-3">
          <TitleLine />
          <TitleLine className="w-1/2" />
        </div>
      </article>
    );
  }
  const image = post.images?.[0] ? uploadSrc(post.images[0]) : undefined;
  return (
    <article className={`grid grid-cols-[6.5rem_1fr] gap-4 border-b border-neutral-300 pb-5 sm:grid-cols-[9rem_1fr] ${className}`}>
      {image ? (
        <Link to={`/posts/${post.id}`} aria-label={`Read ${post.title}`} className="zoom-frame block h-24 bg-[#D6DEEE] sm:h-28">
          <SafeImage src={image} />
        </Link>
      ) : <ImageWell className="h-24 sm:h-28" />}
      <div className="min-w-0">
        {post.news_categories?.length ? (
          <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>
        ) : (
          <Kicker category={post.category} />
        )}
        <Headline to={`/posts/${post.id}`} className="mt-1 text-[1.35rem]">
          {post.title}
        </Headline>
        <Dek>{post.excerpt}</Dek>
        <Byline post={post} />
      </div>
    </article>
  );
}

export function StoryTile({ post, wellClassName = "h-36", showExcerpt = true }) {
  if (!post) {
    return (
      <div className="border-b border-neutral-300 pb-5">
        <ImageWell className={wellClassName} />
        <TitleLine className="mt-3" />
      </div>
    );
  }
  return (
    <article className="border-b border-neutral-300 pb-5">
      {post.images?.[0] ? (
        <Link to={`/posts/${post.id}`} aria-label={`Read ${post.title}`} className={`zoom-frame block bg-[#D6DEEE] ${wellClassName}`}>
          <SafeImage src={uploadSrc(post.images[0])} />
        </Link>
      ) : <ImageWell className={wellClassName} />}
      <div className="mt-3">
        {post.news_categories?.length ? (
          <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>
        ) : (
          <Kicker category={post.category} />
        )}
        <Headline to={`/posts/${post.id}`} className="mt-1 text-[1.45rem]">
          {post.title}
        </Headline>
        {showExcerpt ? <Dek>{post.excerpt}</Dek> : null}
        <Byline post={post} />
      </div>
    </article>
  );
}
