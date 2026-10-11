import { Link } from "react-router-dom";
import { newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { uploadSrc } from "../avatar";
import { Dek, Headline, Kicker, SectionRule, StoryTile } from "./ui";

function slot(items, index) {
  return items[index] ?? null;
}

function filled(items, indexes, loading) {
  if (loading) return [];
  return indexes.map((index) => slot(items, index)).filter(Boolean);
}

function StoryImage({ post, className }) {
  return (
    <Link to={`/posts/${post.id}`} aria-label={`Read ${post.title}`} className={`block overflow-hidden bg-[#D6DEEE] ${className}`}>
      <img src={uploadSrc(post.images[0])} alt="" className="h-full w-full object-cover" />
    </Link>
  );
}

function SlotKicker({ post }) {
  if (post?.news_categories?.length) {
    return <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>;
  }
  if (post?.category) return <Kicker category={post.category} />;
  return null;
}

function Hero({ items, loading }) {
  const featured = loading ? null : slot(items, 0);
  const secondary = loading ? null : slot(items, 1);
  const third = loading ? null : slot(items, 2);
  const wide = loading ? null : slot(items, 3);
  if (!featured && !secondary && !third && !wide) return null;
  const sideBySide = Boolean(featured && (secondary || third || wide));

  return (
    <div className="grid grid-cols-1 gap-x-5 gap-y-5 pt-6 lg:grid-cols-12">
      {featured ? (
        <div className={sideBySide ? "lg:col-span-7" : "lg:col-span-12"}>
          {featured.images?.[0] ? <StoryImage post={featured} className="h-full min-h-[320px] w-full" /> : null}
          <div className={featured.images?.[0] ? "mt-4" : ""}>
            <SlotKicker post={featured} />
            <Headline to={`/posts/${featured.id}`} className="mt-1 text-[40px] font-bold sm:text-[44px]">
              {featured.title}
            </Headline>
            {featured.excerpt ? <Dek>{featured.excerpt}</Dek> : null}
          </div>
        </div>
      ) : null}

      {secondary || third || wide ? (
        <div className={`flex flex-col gap-5 ${featured ? "lg:col-span-5" : "lg:col-span-12"}`}>
          {secondary || third ? (
            <div className={`grid gap-x-4 gap-y-3 ${[secondary, third].filter(Boolean).length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
              {[secondary, third].filter(Boolean).map((post) => (
                <article key={post.id}>
                  {post.images?.[0] ? <StoryImage post={post} className="aspect-square w-full" /> : null}
                  <div className={`${post.images?.[0] ? "mt-3" : ""} border-b border-neutral-200 pb-4`}>
                    <SlotKicker post={post} />
                    <Headline to={`/posts/${post.id}`} className="mt-1 text-[21px] font-semibold">
                      {post.title}
                    </Headline>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
          {wide ? (
            <article className={wide.images?.[0] ? "grid grid-cols-[minmax(120px,0.85fr)_1.15fr] gap-4" : ""}>
              {wide.images?.[0] ? <StoryImage post={wide} className="h-[110px] w-full" /> : null}
              <div>
                <SlotKicker post={wide} />
                <Headline to={`/posts/${wide.id}`} className="mt-1 text-[22px] font-semibold">
                  {wide.title}
                </Headline>
                {wide.excerpt ? (
                  <p className="mt-2 font-sans text-[13px] font-normal leading-relaxed text-neutral-600">{wide.excerpt}</p>
                ) : null}
              </div>
            </article>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function StoryBand({ title, posts, wellClassName, showDate = false }) {
  if (!posts.length) return null;
  return (
    <>
      <SectionRule>{title}</SectionRule>
      <div className={`grid gap-8 ${posts.length > 1 ? "md:grid-cols-2" : ""}`}>
        {posts.map((post) => (
          <StoryTile key={post.id} post={post} wellClassName={wellClassName} showDate={showDate} />
        ))}
      </div>
    </>
  );
}

export default function HomeGrid({ items, loading }) {
  const { t } = useI18n();
  const latest = filled(items, [4, 5, 6, 7], loading);
  const features = filled(items, [8, 9, 10, 11], loading);
  const more = filled(items, [12, 13, 14], loading);
  const special = filled(items, [15], loading);

  return (
    <div>
      <Hero items={items} loading={loading} />
      <div className="mt-10">
        <StoryBand title={t("home.latest")} posts={latest} wellClassName="h-56" />
        <StoryBand title={t("home.features")} posts={features} wellClassName="h-56" showDate />
        <StoryBand title={t("home.more")} posts={more} wellClassName="h-36" showDate />
        <StoryBand title={t("home.special")} posts={special} wellClassName="h-64" showDate />
      </div>
    </div>
  );
}
