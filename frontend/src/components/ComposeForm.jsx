import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { forumListPath } from "../format";
import { useI18n } from "../i18n";
import { Avatar } from "./Avatar";
import { ErrorBanner, FieldError } from "./ui";

export default function ComposeForm({ category, onPublished, onCancel, onBusy }) {
  const { user, setUser } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const isForum = category === "forum";
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [images, setImages] = useState([]);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const imagesRef = useRef(images);
  imagesRef.current = images;

  useEffect(() => {
    return () => {
      imagesRef.current.forEach((item) => URL.revokeObjectURL(item.preview));
    };
  }, []);

  async function onPublish(event) {
    event.preventDefault();
    setSubmitting(true);
    onBusy?.(true);
    setError(null);
    const payload = { title, body, category };
    try {
      const created = await api.createPost(
        payload,
        isForum ? images.map((item) => item.file) : [],
      );
      if (isForum) {
        navigate(`/posts/${created.id}`, {
          state: { forumBack: forumListPath(location.pathname) || "/forum" },
        });
        return;
      }
      onPublished(created);
      setSubmitting(false);
      onBusy?.(false);
    } catch (err) {
      setSubmitting(false);
      onBusy?.(false);
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate(`/sign-in?next=${location.pathname}`);
        return;
      }
      setError(err);
    }
  }

  function onFiles(event) {
    const next = Array.from(event.target.files || []).slice(0, 4);
    setImages((current) => {
      current.forEach((item) => URL.revokeObjectURL(item.preview));
      return next.map((file) => ({ file, preview: URL.createObjectURL(file) }));
    });
    event.target.value = "";
  }

  function removeImage(index) {
    setImages((current) => {
      const copy = [...current];
      URL.revokeObjectURL(copy[index].preview);
      copy.splice(index, 1);
      return copy;
    });
  }

  const topMessage = error && (!error.fields || error.fields.length === 0) ? error : null;

  return (
    <form onSubmit={onPublish} className={`relative ${onCancel ? "mb-0" : "mb-8 border-b border-black pb-8"}`}>
      <fieldset disabled={submitting} className="min-w-0 border-0 p-0">
      <div className="mb-4 flex items-center gap-3">
        <Avatar avatar={user.avatar} size={40} />
        <div>
          <p className="font-sans text-sm">{user.display_name}</p>
          <p className="mt-1 font-sans text-xs text-neutral-500">
            <Link to="/me/avatar" className="text-[#1A4FBF]">
              {t("compose.changeAvatar")}
            </Link>
          </p>
        </div>
      </div>
      <ErrorBanner error={topMessage} />
      <label className="block font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="compose-title">
        {t("compose.title")}
      </label>
      <input
        id="compose-title"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        autoFocus={Boolean(onCancel)}
        className="mt-2 w-full border-0 border-b border-black bg-transparent py-2 font-serif text-3xl outline-none"
      />
      <FieldError message={fieldMessage(error, "title")} />

      <label className="mt-6 block font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="compose-body">
        {t("compose.body")}
      </label>
      <textarea
        id="compose-body"
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={10}
        className="mt-2 w-full resize-y overflow-x-hidden border border-black p-3 font-sans text-[15px] leading-7 outline-none [overflow-wrap:anywhere]"
      />
      <FieldError message={fieldMessage(error, "body")} />

      {isForum ? (
        <>
          <label className="mt-6 block font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="compose-images">
            {t("compose.photos")}
          </label>
          <input
            id="compose-images"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={onFiles}
            className="mt-2 block font-sans text-sm"
          />
          <p className="mt-1 font-sans text-xs text-neutral-500">{t("compose.photoHint")}</p>
          {images.length ? (
            <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {images.map((item, index) => (
                <li key={item.preview} className="relative">
                  <img src={item.preview} alt="" className="h-24 w-full border border-black object-cover" />
                  <button
                    type="button"
                    onClick={() => removeImage(index)}
                    className="mt-1 font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]"
                  >
                    {t("compose.remove")}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <FieldError message={fieldMessage(error, "images")} />
          <FieldError message={fieldMessage(error, "file")} />
        </>
      ) : null}

      <div className="mt-6 flex items-center gap-4">
        <button
          type="submit"
          disabled={submitting || user.muted}
          className="inline-flex items-center gap-2 rounded-[2px] bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.18em] text-white disabled:opacity-40"
        >
          {t("compose.publish")}
        </button>
        {user.muted ? (
          <p className="font-sans text-sm text-red-700">{t("compose.muted")}</p>
        ) : null}
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            className="font-sans text-[11px] uppercase tracking-[0.18em] text-neutral-500"
          >
            {t("compose.cancel")}
          </button>
        ) : null}
      </div>
      </fieldset>
      {submitting ? (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center bg-white/80" role="status">
          <div className="publish-spin" aria-hidden="true" />
          <p className="mt-3 font-sans text-sm text-[#1A4FBF]">{t("compose.publishing")}</p>
        </div>
      ) : null}
    </form>
  );
}
