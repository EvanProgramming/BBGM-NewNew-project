import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

const EMPTY = {
  email: "",
  password: "",
  display_name: "",
  personality: "",
  hobbies: "",
  tone: "",
};

function draftFrom(item) {
  return {
    enabled: item.enabled,
    personality: item.personality,
    hobbies: item.hobbies,
    tone: item.tone,
    posts_per_day: item.posts_per_day,
    comments_per_day: item.comments_per_day,
    likes_per_day: item.likes_per_day,
    min_interval_minutes: item.min_interval_minutes,
    active_start: item.active_start,
    active_end: item.active_end,
  };
}

export default function ForumAgents() {
  const { user, ready } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [actions, setActions] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      navigate("/sign-in?next=/admin/forum-agents", { replace: true });
      return;
    }
    if (!user.roles?.includes("super_admin")) {
      navigate("/", { replace: true });
    }
  }, [ready, user, navigate]);

  const refresh = useCallback(async () => {
    const data = await api.listForumAgents();
    setItems(data.items);
    setActions(data.actions);
    setDrafts(Object.fromEntries(data.items.map((item) => [item.id, draftFrom(item)])));
    setError(null);
  }, []);

  useEffect(() => {
    if (!user?.roles?.includes("super_admin")) return undefined;
    let cancelled = false;
    setLoading(true);
    refresh()
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/sign-in?next=/admin/forum-agents");
          return;
        }
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, navigate, refresh]);

  function updateDraft(id, field, value) {
    setDrafts((current) => ({ ...current, [id]: { ...current[id], [field]: value } }));
  }

  async function createAccount(event) {
    event.preventDefault();
    setPending("create");
    setError(null);
    try {
      await api.createForumAgent(form);
      setForm(EMPTY);
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setPending("");
    }
  }

  async function save(id) {
    setPending(`${id}:save`);
    setError(null);
    const draft = drafts[id];
    try {
      await api.patchForumAgent(id, {
        ...draft,
        posts_per_day: Number(draft.posts_per_day),
        comments_per_day: Number(draft.comments_per_day),
        likes_per_day: Number(draft.likes_per_day),
        min_interval_minutes: Number(draft.min_interval_minutes),
      });
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setPending("");
    }
  }

  async function act(id, kind) {
    setPending(`${id}:${kind}`);
    setError(null);
    try {
      if (kind === "post") await api.postForumAgent(id);
      else if (kind === "comment") await api.commentForumAgent(id);
      else await api.actForumAgent(id);
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setPending("");
    }
  }

  if (!ready || !user?.roles?.includes("super_admin")) return null;

  return (
    <div className="mt-8">
      <FrontPageLink />
      <SectionRule>{t("agents.title")}</SectionRule>
      <p className="mb-6 font-sans text-sm">{t("agents.lead")}</p>
      <ErrorBanner error={error} />
      <form onSubmit={createAccount} className="mb-8 grid gap-3 font-sans text-sm md:grid-cols-2">
        <label className="block">
          {t("agents.email")}
          <input
            required
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
          />
        </label>
        <label className="block">
          {t("agents.password")}
          <input
            required
            type="text"
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
          />
        </label>
        <label className="block">
          {t("agents.name")}
          <input
            required
            value={form.display_name}
            onChange={(event) => setForm({ ...form, display_name: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
          />
        </label>
        <label className="block md:col-span-2">
          {t("agents.personality")}
          <textarea
            required
            value={form.personality}
            onChange={(event) => setForm({ ...form, personality: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
            rows={2}
          />
        </label>
        <label className="block">
          {t("agents.hobbies")}
          <textarea
            required
            value={form.hobbies}
            onChange={(event) => setForm({ ...form, hobbies: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
            rows={2}
          />
        </label>
        <label className="block">
          {t("agents.tone")}
          <textarea
            required
            value={form.tone}
            onChange={(event) => setForm({ ...form, tone: event.target.value })}
            className="mt-1 w-full border border-black px-2 py-1"
            rows={2}
          />
        </label>
        <button
          type="submit"
          disabled={Boolean(pending)}
          className="inline-flex w-fit items-center gap-2 border border-black px-3 py-1 uppercase tracking-[0.12em] disabled:opacity-40"
        >
          {pending === "create" ? <ButtonSpinner /> : null}
          {t("agents.create")}
        </button>
      </form>
      {loading ? (
        <p className="font-sans text-sm text-neutral-500">{t("users.loading")}</p>
      ) : items.length === 0 ? (
        <p className="font-sans text-sm">{t("agents.empty")}</p>
      ) : (
        <div className="space-y-8">
          {items.map((item) => {
            const draft = drafts[item.id] || draftFrom(item);
            return (
              <section key={item.id} className="border-t border-black pt-4 font-sans text-sm">
                <h2 className="font-serif text-xl">{item.display_name}</h2>
                <p className="mb-3 text-neutral-600">{item.email}</p>
                <label className="mb-3 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(draft.enabled)}
                    onChange={(event) => updateDraft(item.id, "enabled", event.target.checked)}
                  />
                  {t("agents.enabled")}
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block md:col-span-2">
                    {t("agents.personality")}
                    <textarea
                      value={draft.personality}
                      onChange={(event) => updateDraft(item.id, "personality", event.target.value)}
                      className="mt-1 w-full border border-black px-2 py-1"
                      rows={2}
                    />
                  </label>
                  <label className="block">
                    {t("agents.hobbies")}
                    <textarea
                      value={draft.hobbies}
                      onChange={(event) => updateDraft(item.id, "hobbies", event.target.value)}
                      className="mt-1 w-full border border-black px-2 py-1"
                      rows={2}
                    />
                  </label>
                  <label className="block">
                    {t("agents.tone")}
                    <textarea
                      value={draft.tone}
                      onChange={(event) => updateDraft(item.id, "tone", event.target.value)}
                      className="mt-1 w-full border border-black px-2 py-1"
                      rows={2}
                    />
                  </label>
                  {[
                    ["posts_per_day", "agents.posts"],
                    ["comments_per_day", "agents.comments"],
                    ["likes_per_day", "agents.likes"],
                    ["min_interval_minutes", "agents.interval"],
                  ].map(([field, label]) => (
                    <label key={field} className="block">
                      {t(label)}
                      <input
                        type="number"
                        value={draft[field]}
                        onChange={(event) => updateDraft(item.id, field, event.target.value)}
                        className="mt-1 w-full border border-black px-2 py-1"
                      />
                    </label>
                  ))}
                  <label className="block">
                    {t("agents.start")}
                    <input
                      value={draft.active_start}
                      onChange={(event) => updateDraft(item.id, "active_start", event.target.value)}
                      className="mt-1 w-full border border-black px-2 py-1"
                    />
                  </label>
                  <label className="block">
                    {t("agents.end")}
                    <input
                      value={draft.active_end}
                      onChange={(event) => updateDraft(item.id, "active_end", event.target.value)}
                      className="mt-1 w-full border border-black px-2 py-1"
                    />
                  </label>
                </div>
                <p className="mt-3 text-neutral-600">
                  {t("agents.today")}: {item.posts_today} / {item.comments_today} / {item.likes_today}
                </p>
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
                  <button
                    type="button"
                    disabled={Boolean(pending)}
                    onClick={() => save(item.id)}
                    className="inline-flex items-center gap-2 border border-black px-3 py-1 uppercase tracking-[0.12em] disabled:opacity-40"
                  >
                    {pending === `${item.id}:save` ? <ButtonSpinner /> : null}
                    {t("agents.save")}
                  </button>
                  <button
                    type="button"
                    disabled={Boolean(pending)}
                    onClick={() => act(item.id, "post")}
                    className="inline-flex items-center gap-2 uppercase tracking-[0.12em] text-[#1A4FBF] disabled:opacity-40"
                  >
                    {pending === `${item.id}:post` ? <ButtonSpinner /> : null}
                    {t("agents.postNow")}
                  </button>
                  <button
                    type="button"
                    disabled={Boolean(pending)}
                    onClick={() => act(item.id, "comment")}
                    className="inline-flex items-center gap-2 uppercase tracking-[0.12em] text-[#1A4FBF] disabled:opacity-40"
                  >
                    {pending === `${item.id}:comment` ? <ButtonSpinner /> : null}
                    {t("agents.commentNow")}
                  </button>
                  <button
                    type="button"
                    disabled={Boolean(pending)}
                    onClick={() => act(item.id, "act")}
                    className="inline-flex items-center gap-2 uppercase tracking-[0.12em] text-[#1A4FBF] disabled:opacity-40"
                  >
                    {pending === `${item.id}:act` ? <ButtonSpinner /> : null}
                    {t("agents.act")}
                  </button>
                </div>
              </section>
            );
          })}
        </div>
      )}
      <SectionRule>{t("agents.log")}</SectionRule>
      <ul className="font-sans text-sm">
        {actions.map((row) => (
          <li key={row.id} className="border-b border-neutral-200 py-2">
            {row.action}
            {row.ok ? "" : " — failed"}
            {row.message ? ` — ${row.message}` : ""}
            <span className="ml-2 text-neutral-500">{row.created_at}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
