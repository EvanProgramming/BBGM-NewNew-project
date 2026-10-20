import { Link } from "react-router-dom";
import { uploadSrc } from "../avatar";
import { newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { Byline, Dek, Headline, ImageWell, Kicker, TitleLine } from "./ui";

export function StoryRow({ post }) {
  const image = post.images?.[0] ? uploadSrc(post.images[0]) : undefined;
  return (
    <article className="grid grid-cols-[8rem_1fr] gap-5 border-b border-neutral-300 py-6 md:grid-cols-[11rem_1fr]">
      <ImageWell className="h-28 md:h-32" src={image} alt="" />
      <div>
        {post.news_categories?.length ? (
          <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">
            {newsTopicsLabel(post.news_categories)}
          </p>
        ) : (
          <Kicker category={post.category} />
        )}
        <Headline to={`/posts/${post.id}`} className="mt-1 text-[1.75rem]">
          {post.title}
        </Headline>
        <Dek>{post.excerpt}</Dek>
        <Byline post={post} className="mt-3" />
      </div>
    </article>
  );
}

export function StoryRowSkeleton() {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-5 border-b border-neutral-300 py-6 md:grid-cols-[11rem_1fr]">
      <ImageWell className="h-28 md:h-32" />
      <div className="flex flex-col justify-center gap-3">
        <TitleLine />
        <TitleLine className="w-1/2" />
      </div>
    </div>
  );
}

export function EmptyCategory({ name }) {
  const { t } = useI18n();
  return (
    <div className="mt-6">
      <ImageWell className="h-44 max-w-lg" />
      <p className="mt-4 font-serif text-3xl font-bold">{t("empty.category", { name })}</p>
      <p className="mt-2 font-sans text-[16px] font-semibold">
        <Link to="/" className="text-link text-[#1A4FBF]">
          {t("empty.back")}
        </Link>
      </p>
    </div>
  );
}
