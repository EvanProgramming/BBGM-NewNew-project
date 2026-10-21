import { Link } from "react-router-dom";
import { newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { uploadSrc } from "../avatar";
import { Byline, CompactStoryRow, Dek, Headline, ImageWell, Kicker, SafeImage, SectionRule, StoryTile } from "./ui";

function slot(items, index) {
  return items[index] ?? null;
}

function StoryImage({ post, className }) {
  const image = post?.images?.[0] ? uploadSrc(post.images[0]) : undefined;
  return post ? (
    <Link to={`/posts/${post.id}`} aria-label={`Read ${post.title}`} className={`zoom-frame block bg-[#D6DEEE] ${className}`}>
      <SafeImage src={image} />
    </Link>
  ) : <ImageWell className={className} />;
}

function SlotKicker({ post, fallback }) {
  const { t } = useI18n();
  const label = post?.pinned ? (
    <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">{t("post.pinned")}</p>
  ) : null;
  let topic = null;
  if (post?.news_categories?.length) {
    topic = <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>;
  } else if (post?.category) {
    topic = <Kicker category={post.category} />;
  } else {
    topic = (
      <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">
        {fallback}
      </p>
    );
  }
  return (
    <>
      {label}
      {topic}
    </>
  );
}

function SlotTitle({ post, fallback, className }) {
  if (post) {
    return (
      <Headline to={`/posts/${post.id}`} className={className}>
        {post.title}
      </Headline>
    );
  }
  return <h2 className={`font-serif font-extrabold leading-[1.12] tracking-[-0.02em] text-[#111111] ${className}`}>{fallback}</h2>;
}

function Hero({ items, loading }) {
  const { t } = useI18n();
  const featured = loading ? null : slot(items, 0);
  const secondary = loading ? null : slot(items, 1);
  const third = loading ? null : slot(items, 2);
  const sports = loading ? null : slot(items, 3);

  return (
    <div className="grid grid-cols-1 gap-8 border-b border-neutral-300 pb-12 pt-8 lg:grid-cols-12">
      <div className="flex flex-col lg:col-span-7">
        <StoryImage post={featured} className="aspect-[3/2] w-full" />
        <div className="mt-6 border-t border-neutral-300 pt-7 lg:pr-8">
          <p className="font-sans text-[13px] font-bold uppercase tracking-[0.14em] text-[#1A4FBF]">
            {t("home.featured")}
          </p>
          <SlotTitle
            post={featured}
            fallback={t("home.featuredTitle")}
            className="mt-2 text-[38px] font-bold leading-[1.04] sm:text-[46px]"
          />
          {featured?.excerpt ? <Dek>{featured.excerpt}</Dek> : null}
          <Byline post={featured} className="mt-3" />
        </div>
      </div>

      <div className="flex flex-col gap-8 lg:col-span-5">
        <div className="grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2">
          <article>
            <StoryImage post={secondary} className="aspect-[4/3] w-full" />
            <div className="mt-3 border-b border-neutral-300 pb-5">
              <SlotKicker post={secondary} fallback={t("home.news")} />
              <SlotTitle
                post={secondary}
                fallback={t("home.secondaryTitle")}
                className="mt-1 text-[22px] font-bold"
              />
              <Byline post={secondary} />
            </div>
          </article>
          <article>
            <StoryImage post={third} className="aspect-[4/3] w-full" />
            <div className="mt-3 border-b border-neutral-300 pb-5">
              <SlotKicker post={third} fallback={t("home.news")} />
              <SlotTitle post={third} fallback={t("home.thirdTitle")} className="mt-1 text-[22px] font-bold" />
              <Byline post={third} />
            </div>
          </article>
        </div>

        <div className="grid grid-cols-1 gap-5 border-t border-neutral-300 pt-7 sm:grid-cols-2">
          <StoryImage post={sports} className="aspect-[3/2] w-full" />
          <article>
            <SlotKicker post={sports} fallback={t("home.news")} />
            <SlotTitle post={sports} fallback={t("home.wideTitle")} className="mt-1 text-[24px] font-bold" />
            {sports?.excerpt ? (
              <p className="mt-2 font-sans text-[15px] font-medium leading-relaxed text-neutral-700">{sports.excerpt}</p>
            ) : (
              <p className="mt-2 font-sans text-[15px] font-medium leading-relaxed text-neutral-700">
                {t("home.wideDek")}
              </p>
            )}
            <Byline post={sports} />
          </article>
        </div>
      </div>
    </div>
  );
}

function StaticRail({ kicker, title, note, wellClassName = "h-28" }) {
  return (
    <section className="border-b border-neutral-300 pb-6">
      <h2 className="font-sans text-[13px] font-bold uppercase tracking-[0.16em] text-[#1A4FBF]">{kicker}</h2>
      <ImageWell className={`mt-3 ${wellClassName}`} />
      <p className="mt-3 font-serif text-[24px] font-bold leading-snug">{title}</p>
      <p className="mt-2 font-sans text-[15px] font-medium leading-relaxed text-neutral-600">{note}</p>
    </section>
  );
}

function SpecialFeature({ post }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-8 md:grid-cols-2 md:items-center">
      <StoryImage post={post} className="aspect-[4/3] w-full" />
      <article>
        <SlotKicker post={post} fallback={t("home.special")} />
        <SlotTitle
          post={post}
          fallback={t("home.specialTitle")}
          className="mt-2 text-[38px] font-bold leading-[1.05] sm:text-[44px]"
        />
        {post?.excerpt ? <Dek>{post.excerpt}</Dek> : (
          <p className="mt-3 font-sans text-[16px] font-medium leading-relaxed text-neutral-700">
            {t("home.specialDek")}
          </p>
        )}
        <Byline post={post} className="mt-3" />
      </article>
    </div>
  );
}

export default function HomeGrid({ items, loading }) {
  const { t } = useI18n();

  return (
    <div>
      <Hero items={items} loading={loading} />

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <SectionRule first>{t("home.latest")}</SectionRule>
          <div className="grid gap-8 md:grid-cols-12">
            <div className="md:col-span-7">
              <StoryTile post={loading ? null : slot(items, 4)} wellClassName="aspect-[4/3] w-full" />
            </div>
            <div className="flex flex-col gap-5 md:col-span-5">
              {[5, 6, 7].map((index) => (
                <CompactStoryRow key={index} post={loading ? null : slot(items, index)} />
              ))}
            </div>
          </div>

          <SectionRule>{t("home.features")}</SectionRule>
          <div className="grid gap-8 md:grid-cols-12">
            <div className="flex flex-col gap-5 md:col-span-5">
              {[8, 9, 10].map((index) => (
                <CompactStoryRow key={index} post={loading ? null : slot(items, index)} />
              ))}
            </div>
            <div className="md:col-span-7">
              <StoryTile post={loading ? null : slot(items, 11)} wellClassName="aspect-[4/3] w-full" />
            </div>
          </div>

          <SectionRule>{t("home.more")}</SectionRule>
          <div className="grid gap-6 md:grid-cols-3">
            {[12, 13, 14].map((index) => (
              <StoryTile
                key={index}
                post={loading ? null : slot(items, index)}
                wellClassName="aspect-[4/3] w-full"
              />
            ))}
          </div>

          <SectionRule>{t("home.special")}</SectionRule>
          <SpecialFeature post={loading ? null : slot(items, 15)} />
        </div>

        <aside className="flex flex-col gap-10 border-t border-neutral-200 pt-8 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <StaticRail
            kicker={t("home.photoKicker")}
            title={t("home.photoTitle")}
            note={t("home.photoNote")}
            wellClassName="aspect-[4/5] w-full"
          />
          <StaticRail
            kicker={t("home.trackKicker")}
            title={t("home.trackTitle")}
            note={t("home.trackNote")}
            wellClassName="aspect-[16/9] w-full"
          />
          <StaticRail
            kicker={t("home.artKicker")}
            title={t("home.artTitle")}
            note={t("home.artNote")}
            wellClassName="aspect-square w-full"
          />
        </aside>
      </div>
    </div>
  );
}
