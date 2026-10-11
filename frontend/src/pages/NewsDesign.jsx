import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { ErrorBanner, FrontPageLink, SectionRule } from "../components/ui";
import { canEditNews, formatDateline } from "../format";
import { useI18n } from "../i18n";

function ArticlePreview({ item, body, label }) {
  const paragraphs = (body || "").split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
  return (
    <article className="max-h-[760px] overflow-y-auto border border-neutral-300 bg-white">
      {item.images[0] ? <img src={uploadSrc(item.images[0])} alt="" className="aspect-[16/9] w-full object-cover" /> : <div className="aspect-[16/9] bg-[#D6DEEE]" />}
      <div className="p-5 sm:p-7">
        <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">{item.topics.map((topic) => topic === "sport" ? "Sports" : topic).join(" · ")}</p>
        <h3 className="mt-2 font-serif text-2xl font-semibold leading-tight sm:text-3xl">{item.title}</h3>
        <p className="mt-3 border-b border-neutral-200 pb-4 font-sans text-xs text-neutral-500">{item.author.display_name} · {label}</p>
        {item.images.length > 1 ? <div className="mt-5 grid grid-cols-3 gap-2">{item.images.slice(1).map((image) => <img key={image} src={uploadSrc(image)} alt="" className="aspect-[4/3] w-full object-cover" />)}</div> : null}
        <div className="mt-5 space-y-4 font-serif text-base leading-7 text-neutral-900">
          {paragraphs.map((paragraph, index) => <p key={`${index}-${paragraph.slice(0, 16)}`}>{paragraph}</p>)}
        </div>
      </div>
    </article>
  );
}

export default function NewsDesign() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();
  const { lang } = useI18n();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [mode, setMode] = useState("original");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/news/design", { replace: true });
    else if (!canEditNews(user)) navigate("/", { replace: true });
  }, [ready, user, navigate]);

  async function refresh(keepId = null) {
    const { items: submissions } = await api.listNewsSubmissions();
    const drafts = submissions.filter((item) => item.status === "draft" && (user.role === "super_admin" || item.author.id === user.id));
    setItems(drafts);
    const next = drafts.find((item) => item.id === keepId) || drafts[0] || null;
    setSelected(next);
    return next;
  }

  useEffect(() => {
    if (!user || !canEditNews(user)) return undefined;
    let active = true;
    api.listNewsSubmissions().then(({ items: submissions }) => {
      if (!active) return;
      const drafts = submissions.filter((item) => item.status === "draft" && (user.role === "super_admin" || item.author.id === user.id));
      setItems(drafts);
      setSelected(drafts[0] || null);
    }).catch((err) => { if (active) setError(err); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user]);

  function choose(item) {
    setSelected(item);
    setMode("original");
    setError(null);
    setNotice("");
  }

  async function createDesign() {
    if (!selected) return;
    setActing("design");
    setError(null);
    setNotice("");
    try {
      const result = await api.formatNewsSubmission(selected.id);
      setSelected(result);
      setItems((current) => current.map((item) => item.id === result.id ? result : item));
      setMode("formatted");
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  async function sendForReview() {
    if (!selected || (mode === "formatted" && !selected.formatted_body)) return;
    setActing("submit");
    setError(null);
    try {
      await api.submitNewsSubmission(selected.id, mode);
      setItems((current) => current.filter((item) => item.id !== selected.id));
      setNotice("Sent for super admin review. It will appear in News after approval.");
      setSelected(null);
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  async function publish() {
    if (!selected || (mode === "formatted" && !selected.formatted_body)) return;
    setActing("publish");
    setError(null);
    setNotice("");
    try {
      await api.publishNewsSubmission(selected.id, mode);
      setItems((current) => current.filter((item) => item.id !== selected.id));
      setSelected(null);
      setNotice("Published to News.");
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  if (!ready || !user || !canEditNews(user)) return null;
  return (
    <main className="mt-8">
      <FrontPageLink />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionRule>Design · Editorial layout</SectionRule>
        {user.role === "super_admin" ? <Link to="/news/review" className="mb-3 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF]">Review queue</Link> : null}
      </div>
      <ErrorBanner error={error} />
      {notice ? <p role="status" className="mb-4 border-l-2 border-[#1A4FBF] pl-3 font-sans text-sm">{notice}</p> : null}
      <div className="mt-6 grid grid-cols-1 gap-10 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside>
          <h2 className="border-b border-black pb-2 font-sans text-[10px] font-semibold uppercase tracking-[0.15em]">Saved drafts</h2>
          {loading ? <p className="py-4 font-sans text-sm text-neutral-500">Loading…</p> : null}
          {!loading && !items.length ? <p className="py-4 font-sans text-sm text-neutral-500">No drafts to design.</p> : null}
          <ul className="divide-y divide-neutral-200">
            {items.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => choose(item)} className={`w-full py-3 text-left ${selected?.id === item.id ? "text-[#1A4FBF]" : "text-neutral-900"}`}>
                  <span className="block font-serif text-lg leading-snug">{item.title}</span>
                  <span className="mt-1 block font-sans text-[10px] uppercase tracking-[0.12em] text-neutral-500">{item.author.display_name} · {formatDateline(item.updated_at, lang)}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <section className="min-w-0 border-t border-black pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          {selected ? (
            <>
              <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">{selected.topics.map((topic) => topic === "sport" ? "Sports" : topic).join(" · ")}</p>
              <h1 className="mt-2 font-serif text-3xl font-semibold leading-tight">{selected.title}</h1>
              <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {selected.images.map((image) => <img key={image} src={uploadSrc(image)} alt="Story visual" className="aspect-[4/3] w-full border border-neutral-300 object-cover" />)}
              </div>
              <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="Design source">
                <button type="button" aria-pressed={mode === "original"} onClick={() => { setMode("original"); setNotice(""); }} className={`border px-3 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.12em] ${mode === "original" ? "border-black bg-black text-white" : "border-neutral-300"}`}>Original</button>
                <button type="button" aria-pressed={mode === "formatted"} onClick={() => { setMode("formatted"); setNotice(""); }} className={`border px-3 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.12em] ${mode === "formatted" ? "border-black bg-black text-white" : "border-neutral-300"}`}>API design</button>
              </div>
              <div className="mt-6">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-black pb-2">
                  <h2 className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em]">Article preview</h2>
                  {mode === "formatted" && selected.format_source === "local" ? <span className="font-sans text-xs text-neutral-500">Local preview · no API key configured</span> : null}
                </div>
                <div className="grid gap-5 xl:grid-cols-2">
                  <section>
                    <h3 className="mb-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-500">Original</h3>
                    <ArticlePreview item={selected} body={selected.body} label={formatDateline(selected.created_at, lang)} />
                  </section>
                  <section>
                    <h3 className="mb-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF]">{selected.formatted_body ? (selected.format_source === "openai" ? "API design" : "Local design") : "API design · not generated"}</h3>
                    {selected.formatted_body ? <ArticlePreview item={selected} body={selected.formatted_body} label={formatDateline(selected.created_at, lang)} /> : <div className="flex min-h-[260px] items-center justify-center border border-dashed border-neutral-300 px-6 text-center font-sans text-sm text-neutral-500">Generate the API design to preview this version.</div>}
                  </section>
                </div>
              </div>
              <div className="mt-6 flex flex-wrap gap-3 border-t border-black pt-5">
                {mode === "formatted" && !selected.formatted_body ? <button type="button" onClick={createDesign} disabled={Boolean(acting)} className="border border-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF] disabled:opacity-50">{acting === "design" ? "Designing…" : "Generate API design"}</button> : null}
                {user.role === "super_admin" ? (
                  <button type="button" onClick={publish} disabled={Boolean(acting) || (mode === "formatted" && !selected.formatted_body)} className="bg-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-white disabled:opacity-50">{acting === "publish" ? "Publishing…" : "Publish to News"}</button>
                ) : (
                  <button type="button" onClick={sendForReview} disabled={Boolean(acting) || (mode === "formatted" && !selected.formatted_body)} className="bg-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-white disabled:opacity-50">{acting === "submit" ? "Sending…" : "Send for review"}</button>
                )}
              </div>
            </>
          ) : <p className="py-8 font-sans text-sm text-neutral-500">Select a saved draft.</p>}
        </section>
      </div>
    </main>
  );
}
