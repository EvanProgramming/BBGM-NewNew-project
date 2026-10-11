import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { uploadSrc } from "../avatar";
import { ErrorBanner, FieldError, FrontPageLink, SectionRule } from "../components/ui";
import { canEditNews, formatDateline, hasRole } from "../format";
import { useI18n } from "../i18n";

const TOPICS = ["sport", "dorm", "scoop"];

function PendingImage({ file, onRemove }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  return (
    <div className="relative">
      {src ? <img src={src} alt={file.name} className="aspect-square w-full border border-neutral-300 object-cover" /> : null}
      <button type="button" onClick={onRemove} className="mt-1 font-sans text-[10px] font-semibold uppercase text-[#1A4FBF]">Remove</button>
    </div>
  );
}

export default function NewsSubmit() {
  const { user, ready, setUser } = useAuth();
  const { lang } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [topics, setTopics] = useState([]);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) navigate("/sign-in?next=/news/submit", { replace: true });
    else if (!canEditNews(user)) navigate("/", { replace: true });
  }, [ready, user, navigate]);

  async function refresh() {
    const result = await api.listNewsSubmissions();
    setItems(result.items);
  }

  useEffect(() => {
    if (!user || !canEditNews(user)) return undefined;
    let active = true;
    api.listNewsSubmissions().then((result) => {
      if (active) setItems(result.items);
    }).catch((err) => {
      if (active && err instanceof ApiError && err.status === 401) setUser(null);
      else if (active) setError(err);
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [user, setUser]);

  function load(item) {
    setSelected(item);
    setTitle(item.title);
    setBody(item.body);
    setTopics(item.topics);
    setFiles([]);
    setError(null);
    setNotice("");
  }

  function toggleTopic(topic) {
    setTopics((current) => current.includes(topic) ? current.filter((item) => item !== topic) : [...current, topic]);
  }

  function selectImages(event) {
    const chosen = Array.from(event.target.files || []);
    setError(null);
    setFiles((current) => [...current, ...chosen]);
    event.target.value = "";
  }

  async function removeImage(image) {
    if (!selected) return;
    setActing(`remove:${image}`);
    setError(null);
    try {
      const item = await api.removeNewsSubmissionImage(selected.id, image);
      setSelected(item);
      setItems((current) => current.map((entry) => entry.id === item.id ? item : entry));
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  async function create(event) {
    event.preventDefault();
    setActing("save");
    setError(null);
    const form = new FormData();
    form.set("title", title);
    form.set("body", body);
    form.set("topics", JSON.stringify(topics));
    files.forEach((file) => form.append("images", file));
    try {
      const item = await api.createNewsSubmission(form);
      await refresh();
      load(item);
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  async function save() {
    if (!selected) return null;
    setActing("save");
    setError(null);
    try {
      let item = await api.patchNewsSubmission(selected.id, { title, body, topics });
      if (files.length) {
        const form = new FormData();
        files.forEach((file) => form.append("images", file));
        item = await api.addNewsSubmissionImages(item.id, form);
      }
      setSelected(item);
      setTitle(item.title);
      setBody(item.body);
      setTopics(item.topics);
      setFiles([]);
      setItems((current) => current.map((entry) => entry.id === item.id ? item : entry));
      return item;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      setActing("");
    }
  }

  async function sendForReview() {
    const item = await save();
    if (!item) return;
    setActing("submit");
    setError(null);
    setNotice("");
    try {
      const pending = await api.submitNewsSubmission(item.id, "original");
      setSelected(pending);
      setItems((current) => current.map((entry) => entry.id === pending.id ? pending : entry));
      setNotice("Sent for super admin review. It will appear in News after approval.");
    } catch (err) {
      setError(err);
    } finally {
      setActing("");
    }
  }

  if (!ready || !user || !canEditNews(user)) return null;
  const isNew = !selected;
  const editable = isNew || selected.status === "draft";

  return (
    <main className="mt-8">
      <FrontPageLink />
      <SectionRule>Draft · Story editor</SectionRule>
      <ErrorBanner error={error && !error.fields?.length ? error : null} />
      {notice ? <p role="status" className="mb-4 border-l-2 border-[#1A4FBF] pl-3 font-sans text-sm">{notice}</p> : null}
      <div className="mt-6 grid grid-cols-1 gap-10 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside>
          <div className="flex items-center justify-between border-b border-black pb-2">
            <h2 className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]">Your submissions</h2>
            <button type="button" onClick={() => { setSelected(null); setTitle(""); setBody(""); setTopics([]); setFiles([]); setError(null); setNotice(""); }} className="font-sans text-[11px] font-semibold uppercase text-[#1A4FBF]">New</button>
          </div>
          {loading ? <p className="py-4 font-sans text-sm text-neutral-500">Loading…</p> : null}
          <ul className="divide-y divide-neutral-200">
            {items.map((item) => (
              <li key={item.id}>
                <button type="button" onClick={() => load(item)} className={`w-full py-3 text-left ${selected?.id === item.id ? "text-[#1A4FBF]" : "text-neutral-900"}`}>
                  <span className="block font-serif text-lg leading-snug">{item.title}</span>
                  <span className="mt-1 block font-sans text-[10px] uppercase tracking-[0.12em] text-neutral-500">{item.status} · {formatDateline(item.updated_at, lang)}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="min-w-0 border-t border-black pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <form onSubmit={isNew ? create : (event) => { event.preventDefault(); save(); }}>
            <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_250px]">
              <div>
                <label htmlFor="news-title" className="font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">Headline</label>
                <input id="news-title" value={title} disabled={!editable} onChange={(event) => setTitle(event.target.value)} className="mt-2 w-full border-0 border-b border-black bg-transparent py-2 font-serif text-3xl outline-none disabled:text-neutral-500" />
                <FieldError message={fieldMessage(error, "title")} />
                <label htmlFor="news-body" className="mt-6 block font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">Story</label>
                <textarea id="news-body" value={body} disabled={!editable} onChange={(event) => setBody(event.target.value)} rows={17} className="mt-2 w-full resize-y border border-neutral-400 bg-white p-4 font-sans text-[15px] leading-7 outline-none focus:border-black disabled:bg-neutral-50" placeholder="Write the story here…" />
                <FieldError message={fieldMessage(error, "body")} />
              </div>
              <div>
                <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">Sections</p>
                <div className="mt-3 flex flex-col gap-2">
                  {TOPICS.map((topic) => (
                    <label key={topic} className="flex items-center gap-2 font-sans text-sm capitalize">
                      <input type="checkbox" checked={topics.includes(topic)} disabled={!editable} onChange={() => toggleTopic(topic)} className="h-4 w-4 accent-[#1A4FBF]" />
                      {topic === "sport" ? "Sports" : topic === "scoop" ? "Scoop" : "Dorm"}
                    </label>
                  ))}
                </div>
                <FieldError message={fieldMessage(error, "topics")} />
                <label htmlFor="news-images" className="mt-7 block font-sans text-[10px] font-semibold uppercase tracking-[0.15em] text-[#1A4FBF]">Photos</label>
                {selected?.images?.length ? (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {selected.images.map((src, index) => (
                      <div key={src}>
                        <img src={uploadSrc(src)} alt={`Story photo ${index + 1}`} className="aspect-square w-full border border-neutral-300 object-cover" />
                        {editable ? <button type="button" onClick={() => removeImage(src)} disabled={Boolean(acting)} className="mt-1 font-sans text-[10px] font-semibold uppercase text-[#1A4FBF] disabled:opacity-50">{acting === `remove:${src}` ? "Removing…" : "Remove"}</button> : null}
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-2 font-sans text-xs text-neutral-500">No images attached.</p>}
                {editable ? (
                  <input id="news-images" type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={selectImages} className="mt-3 block w-full font-sans text-xs" />
                ) : null}
                {files.length ? <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">{files.map((file, index) => <PendingImage key={`${file.name}-${file.lastModified}-${index}`} file={file} onRemove={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} />)}</div> : null}
                <p className="mt-1 font-sans text-[11px] text-neutral-500">{(selected?.images?.length || 0) + files.length} selected</p>
                <FieldError message={fieldMessage(error, "images")} />
              </div>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              {isNew ? (
                <button type="submit" disabled={Boolean(acting)} className="bg-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-white disabled:opacity-50">{acting === "save" ? "Saving…" : "Save draft"}</button>
              ) : editable ? (
                <>
                  <button type="submit" disabled={Boolean(acting)} className="border border-black px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] disabled:opacity-50">{acting === "save" ? "Saving…" : "Save changes"}</button>
                  {!hasRole(user, "super_admin") ? (
                    <button type="button" onClick={sendForReview} disabled={Boolean(acting)} className="bg-[#1A4FBF] px-4 py-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em] text-white disabled:opacity-50">{acting === "submit" ? "Sending…" : "Send for review"}</button>
                  ) : null}
                </>
              ) : <p className="font-sans text-sm text-neutral-500">This article is awaiting super admin review.</p>}
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
