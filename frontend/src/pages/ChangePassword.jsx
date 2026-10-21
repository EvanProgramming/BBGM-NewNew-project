import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, api, fieldMessage } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError, FrontPageLink, ManualPasswordInput, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

export default function ChangePassword() {
  const { user, ready, setUser } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (ready && !user) {
      navigate("/sign-in?next=/me/password", { replace: true });
    }
  }, [ready, user, navigate]);

  async function onSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.changePassword({ current_password: currentPassword, password });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
        navigate("/sign-in?next=/me/password");
        return;
      }
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready || !user) return null;

  if (done) {
    return (
      <div className="mx-auto mt-10 max-w-lg">
        <FrontPageLink />
        <SectionRule>{t("password.title")}</SectionRule>
        <p className="font-sans text-[15px] text-neutral-700">{t("reset.updated")}</p>
        <p className="mt-4 font-sans text-[15px]">
          <Link to="/" className="text-[#1A4FBF]">
            {t("link.frontPage")}
          </Link>
        </p>
      </div>
    );
  }

  const banner = error && !error.fields?.length ? error : null;

  return (
    <div className="mx-auto mt-10 max-w-lg">
      <FrontPageLink />
      <SectionRule>{t("password.title")}</SectionRule>
      <ErrorBanner error={banner} />
      <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="current_password">
            {t("password.current")}
          </label>
          <ManualPasswordInput
            id="current_password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
          />
          <FieldError message={fieldMessage(error, "current_password")} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="password">
            {t("password.new")}
          </label>
          <ManualPasswordInput id="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          <FieldError message={fieldMessage(error, "password")} />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 rounded-[2px] bg-black px-6 py-2.5 font-sans text-[13px] uppercase tracking-[0.16em] text-white disabled:opacity-40"
        >
          {submitting ? <ButtonSpinner /> : null}
          {t("password.submit")}
        </button>
      </form>
    </div>
  );
}
