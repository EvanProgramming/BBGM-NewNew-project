import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, fieldMessage, safeNext } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError, FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

export default function SignIn() {
  const { signIn } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const profile = await api.login({ email, password });
      signIn(profile);
      navigate(safeNext(params.get("next")));
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const banner =
    error && (error.code === "invalid_credentials" || !error.fields?.length) ? error : null;

  return (
    <div className="mx-auto mt-10 max-w-lg">
      <FrontPageLink />
      <SectionRule>{t("signIn.title")}</SectionRule>
      <ErrorBanner error={banner} />
      <form onSubmit={onSubmit} className="space-y-5">
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="email">
            {t("signIn.email")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-2 w-full border-0 border-b border-black py-2 font-sans text-[15px] outline-none"
          />
          <FieldError message={fieldMessage(error, "email")} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="password">
            {t("signIn.password")}
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 w-full border-0 border-b border-black py-2 font-sans text-[15px] outline-none"
          />
          <FieldError message={fieldMessage(error, "password")} />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 rounded-[2px] bg-black px-6 py-2.5 font-sans text-[13px] uppercase tracking-[0.16em] text-white disabled:opacity-40"
        >
          {submitting ? <ButtonSpinner /> : null}
          {t("signIn.submit")}
        </button>
      </form>
      <p className="mt-6 font-sans text-[15px] text-neutral-500">
        {t("signIn.new")}{" "}
        <Link to={`/register${params.get("next") ? `?next=${encodeURIComponent(params.get("next"))}` : ""}`} className="text-[#1A4FBF]">
          {t("signIn.create")}
        </Link>
        {" · "}
        <Link to="/reset-password" className="text-[#1A4FBF]">
          {t("signIn.forgot")}
        </Link>
        {" · "}
        <Link to="/" className="text-[#1A4FBF]">
          {t("link.frontPage")}
        </Link>
      </p>
    </div>
  );
}
