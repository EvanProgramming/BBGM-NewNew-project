import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { ErrorBanner, FrontPageLink, SectionRule } from "../components/ui";
import { formatDateline, hasRole, newsTopicsLabel } from "../format";
import { useI18n } from "../i18n";

export default function NewsReview() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();
  const { submissionId } = useParams();
  const { lang } = useI18n();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [version, setVersion] = useState("formatted");
  const [error, setError] = useState(null);
  const [acting, setActing] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/news/review", { replace: true });
    else if (!hasRole(user, "super_admin")) navigate("/", { replace: true });
  }, [ready, user, navigate]);

  useEffect(() => {
    if (!user || !hasRole(user, "super_admin")) return undefined;
    let active = true;
    const request = submissionId ? api.getNewsReview(submissionId) : api.listNewsReview();
    request.then((result) => {
      if (!active) return;
      if (submissionId) setSelected(result);
      else setItems(result.items);
      setError(null);
    }).catch((err) => { if (active) setError(err); });
    return () => { active = false; };
  }, [user, submissionId]);

  async function decide(action) {
    if (!selected) return;
    setActing(action);
    setError(null);
    try {
      if (action === "approve") await api.approveNewsSubmission(selected.id);
      else await api.rejectNewsSubmission(selected.id);
      if (action === "approve") {
        const topic = selected.topics?.[0];
        navigate(topic ? `/?topic=${encodeURIComponent(topic)}` : "/", { replace: true });
      } else {
        navigate("/news/review", { replace: true });
      }
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  function openPreview(id) {
    window.open(`/news/review/${id}`, "_blank", "noopener,noreferrer");
  }

  if (!ready || !user || !hasRole(user, "super_admin")) return null;

  return (
    <main className="mt-8">
      <FrontPageLink />
      <SectionRule>News · Review desk</SectionRule>
      <ErrorBanner error={error} />
      {!submissionId ? (
        <div className="mt-6 divide-y divide-neutral-300 border-y border-black">
          {items.length ? items.map((item) => (
            <article key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4">
              <div>
                <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF]">{newsTopicsLabel(item.topics)}</p>
                <h2 className="mt-1 font-serif text-2xl">{item.title}</h2>
                <p className="mt-1 font-sans text-xs text-neutral-500">{item.author.display_name} · Submitted {formatDateline(item.updated_at, lang)}</p>
              </div>
              <button type="button" onClick={() => openPreview(item.id)} className="border border-black px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em]">Open review preview</button>
            </article>
          )) : <p className="py-10 font-serif text-2xl">No stories are waiting for review.</p>}
        </div>
      ) : selected ? (
        <article className="mx-auto mt-6 max-w-[52rem]">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-black pb-4">
            <div>
              <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF]">{newsTopicsLabel(selected.topics)}</p>
              <h1 className="mt-2 font-serif text-4xl font-semibold">{selected.title}</h1>
              <p className="mt-2 font-sans text-xs text-neutral-500">{selected.author.display_name} · {formatDateline(selected.created_at, lang)}</p>
            </div>
            <Link to="/news/review" className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-[#1A4FBF]">Back to queue</Link>
          </div>
          <div className="mt-5 flex gap-2">
            <button type="button" onClick={() => setVersion("formatted")} aria-pressed={version === "formatted"} className={`border px-3 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.12em] ${version === "formatted" ? "border-black bg-[#1A4FBF] text-white" : "border-neutral-300"}`}>Formatted</button>
            <button type="button" onClick={() => setVersion("original")} aria-pressed={version === "original"} className={`border px-3 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.12em] ${version === "original" ? "border-black bg-[#1A4FBF] text-white" : "border-neutral-300"}`}>Original</button>
            {selected.format_source === "local" ? <span className="self-center font-sans text-xs text-neutral-500">Local layout preview</span> : null}
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {selected.images.map((src) => <img key={src} src={uploadSrc(src)} alt="Submitted news visual" className="max-h-[320px] w-full border border-neutral-300 object-contain" />)}
          </div>
          <div className="mt-6 whitespace-pre-wrap font-serif text-lg leading-8">{version === "original" ? selected.body : selected.formatted_body || selected.body}</div>
          <div className="mt-8 flex flex-wrap gap-3 border-t border-black pt-5">
            <button type="button" onClick={() => decide("approve")} disabled={Boolean(acting)} className="bg-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-white disabled:opacity-50">{acting === "approve" ? "Publishing…" : "Approve & publish"}</button>
            <button type="button" onClick={() => decide("reject")} disabled={Boolean(acting)} className="border border-black px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] disabled:opacity-50">{acting === "reject" ? "Returning…" : "Return to editor"}</button>
          </div>
        </article>
      ) : <p className="mt-6 font-sans text-sm text-neutral-500">Loading review preview…</p>}
    </main>
  );
}
