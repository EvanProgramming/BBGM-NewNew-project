import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { canEditNews, newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";
import { uploadSrc } from "../avatar";
import { Dek, Headline, ImageWell, Kicker, SectionRule, StoryTile, TitleLine } from "./ui";

function slot(items, index) {
  return items[index] ?? null;
}

function StoryImage({ post, className }) {
  const image = post?.images?.[0];
  const content = image ? <img src={uploadSrc(image)} alt="" className="h-full w-full object-cover" /> : <ImageWell className="h-full w-full" />;
  return post ? (
    <Link to={`/posts/${post.id}`} aria-label={`Read ${post.title}`} className={`block overflow-hidden bg-[#D6DEEE] ${className}`}>
      {content}
    </Link>
  ) : <ImageWell className={className} />;
}

function SlotKicker({ post, fallback }) {
  const { t } = useI18n();
  const label = post?.pinned ? (
    <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">{t("post.pinned")}</p>
  ) : null;
  let topic = null;
  if (post?.news_categories?.length) {
    topic = <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">{newsTopicsLabel(post.news_categories)}</p>;
  } else if (post?.category) {
    topic = <Kicker category={post.category} />;
  } else {
    topic = (
      <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">
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
  return <h2 className={`font-serif font-bold leading-[1.12] tracking-[-0.02em] text-[#111111] ${className}`}>{fallback}</h2>;
}

function Hero({ items, loading }) {
  const { t } = useI18n();
  const featured = loading ? null : slot(items, 0);
  const secondary = loading ? null : slot(items, 1);
  const third = loading ? null : slot(items, 2);
  const sports = loading ? null : slot(items, 3);

  return (
    <div className="grid grid-cols-1 gap-x-5 gap-y-5 pt-6 lg:grid-cols-12">
      <div className="lg:col-span-7">
        <StoryImage post={featured} className="h-full min-h-[320px] w-full" />
      </div>

      <div className="lg:col-span-5">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <article>
            <StoryImage post={secondary} className="aspect-square w-full" />
            <div className="mt-3 border-b border-neutral-200 pb-4">
              <SlotKicker post={secondary} fallback={t("home.news")} />
              <SlotTitle
                post={secondary}
                fallback={t("home.secondaryTitle")}
                className="mt-1 text-[21px] font-semibold"
              />
            </div>
          </article>
          <article>
            <StoryImage post={third} className="aspect-square w-full" />
            <div className="mt-3 border-b border-neutral-200 pb-4">
              <SlotKicker post={third} fallback={t("home.news")} />
              <SlotTitle post={third} fallback={t("home.thirdTitle")} className="mt-1 text-[21px] font-semibold" />
            </div>
          </article>
        </div>
      </div>

      <div className="lg:col-span-7 lg:pr-6">
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em] text-[#1A4FBF]">
          {t("home.featured")}
        </p>
        <SlotTitle
          post={featured}
          fallback={t("home.featuredTitle")}
          className="mt-1 text-[40px] font-bold sm:text-[44px]"
        />
        {featured?.excerpt ? <Dek>{featured.excerpt}</Dek> : null}
      </div>

      <div className="grid grid-cols-[minmax(120px,0.85fr)_1.15fr] gap-4 lg:col-span-5">
        <StoryImage post={sports} className="h-[110px] w-full" />
        <article>
          <SlotKicker post={sports} fallback={t("home.news")} />
          <SlotTitle post={sports} fallback={t("home.wideTitle")} className="mt-1 text-[22px] font-semibold" />
          {sports?.excerpt ? (
            <p className="mt-2 font-sans text-[13px] font-normal leading-relaxed text-neutral-600">{sports.excerpt}</p>
          ) : (
            <p className="mt-2 font-sans text-[13px] font-normal leading-relaxed text-neutral-600">
              {t("home.wideDek")}
            </p>
          )}
        </article>
      </div>
    </div>
  );
}

function EmptyFeatured({ user }) {
  const { t } = useI18n();
  if (!user) return null;
  return (
    <div className="mt-6">
      {canEditNews(user) ? (
        <p className="font-sans text-sm">
          <Link to="/news/drafts" className="text-[#1A4FBF]">
            {t("home.editDrafts")}
          </Link>
        </p>
      ) : (
        <p className="font-sans text-sm">
          <Link to="/forum" className="text-[#1A4FBF]">
            {t("home.writeForum")}
          </Link>
        </p>
      )}
    </div>
  );
}

function StaticRail({ kicker, title, note, wellClassName = "h-28" }) {
  return (
    <section>
      <h2 className="font-sans text-[11px] font-semibold uppercase tracking-[0.18em] text-[#1A4FBF]">{kicker}</h2>
      <ImageWell className={`mt-2 ${wellClassName}`} />
      <p className="mt-2 font-serif text-lg font-semibold leading-snug">{title}</p>
      <p className="mt-1 font-sans text-sm font-normal text-neutral-500">{note}</p>
    </section>
  );
}

export default function HomeGrid({ items, total, loading }) {
  const { user } = useAuth();
  const { t } = useI18n();
  const emptyCampus = !loading && total === 0;

  return (
    <div>
      <Hero items={items} loading={loading} />
      {emptyCampus ? <EmptyFeatured user={user} /> : null}

      <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <SectionRule>{t("home.latest")}</SectionRule>
          <div className="grid gap-8 md:grid-cols-12">
            <div className="md:col-span-7">
              <StoryTile post={loading ? null : slot(items, 4)} wellClassName="h-56" />
            </div>
            <div className="flex flex-col gap-5 md:col-span-5">
              {[5, 6, 7].map((index) => (
                <StoryTile key={index} post={loading ? null : slot(items, index)} wellClassName="h-24" />
              ))}
            </div>
          </div>

          <SectionRule>{t("home.features")}</SectionRule>
          <div className="grid gap-8 md:grid-cols-12">
            <div className="flex flex-col gap-5 md:col-span-5">
              {[8, 9, 10].map((index) => {
                const post = loading ? null : slot(items, index);
                return post ? (
                  <article key={post.id} className="border-b border-neutral-200 pb-4">
                    <SlotKicker post={post} fallback="" />
                    <Headline to={`/posts/${post.id}`} className="mt-1 text-xl font-semibold">
                      {post.title}
                    </Headline>
                    <Dek>{post.excerpt}</Dek>
                  </article>
                ) : (
                  <div key={index}>
                    <TitleLine />
                    <TitleLine className="mt-2 w-1/2" />
                  </div>
                );
              })}
            </div>
            <div className="md:col-span-7">
              <StoryTile post={loading ? null : slot(items, 11)} wellClassName="h-56" showDate />
            </div>
          </div>

          <SectionRule>{t("home.more")}</SectionRule>
          <div className="grid gap-6 md:grid-cols-3">
            {[12, 13, 14].map((index) => (
              <StoryTile
                key={index}
                post={loading ? null : slot(items, index)}
                wellClassName="h-36"
                showDate
              />
            ))}
          </div>

          <SectionRule>{t("home.special")}</SectionRule>
          <StoryTile post={loading ? null : slot(items, 15)} wellClassName="h-64" showDate />
        </div>

        <aside className="flex flex-col gap-8 lg:col-span-4">
          <StaticRail kicker={t("home.photoKicker")} title={t("home.photoTitle")} note={t("home.photoNote")} />
          <StaticRail
            kicker={t("home.trackKicker")}
            title={t("home.trackTitle")}
            note={t("home.trackNote")}
            wellClassName="h-16"
          />
          <StaticRail kicker={t("home.artKicker")} title={t("home.artTitle")} note={t("home.artNote")} />
        </aside>
      </div>
    </div>
  );
}
