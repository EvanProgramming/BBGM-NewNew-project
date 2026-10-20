import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, fieldMessage, safeNext } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FieldError, FrontPageLink, ManualPasswordInput, SectionRule } from "../components/ui";
import { useCodeCooldown } from "../emailCodeWait";
import { useI18n } from "../i18n";
import { TermsDialog } from "./Terms";

export default function Register() {
  const { signIn } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [termsError, setTermsError] = useState("");
  const [termsOpen, setTermsOpen] = useState(false);
  const { secondsLeft, begin: beginWait } = useCodeCooldown("register", email);
  const waiting = secondsLeft > 0;

  async function onSendCode() {
    if (waiting || sendingCode) return;
    setSendingCode(true);
    setError(null);
    try {
      await api.sendEmailCode({ email, purpose: "register" });
      beginWait();
      setCodeSent(true);
    } catch (err) {
      setCodeSent(false);
      setError(err);
    } finally {
      setSendingCode(false);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!acceptTerms) {
      setTermsError("accept");
      return;
    }
    setSubmitting(true);
    setError(null);
    setTermsError("");
    try {
      const profile = await api.register({
        email,
        password,
        display_name: displayName,
        code,
        accept_terms: true,
      });
      signIn(profile);
      navigate(safeNext(params.get("next")));
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const emailError =
    fieldMessage(error, "email") || (error?.code === "email_taken" ? error.message : "");
  const banner = error && error.code !== "email_taken" && !error.fields?.length ? error : null;
  const nextQuery = params.get("next") ? `?next=${encodeURIComponent(params.get("next"))}` : "";

  return (
    <div className="mx-auto mt-10 max-w-lg">
      <FrontPageLink />
      <SectionRule>{t("register.title")}</SectionRule>
      <ErrorBanner error={banner} />
      <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="display_name">
            {t("register.name")}
          </label>
          <input
            id="display_name"
            autoComplete="off"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            className="mt-2 w-full border-0 border-b border-black py-2 font-sans text-[15px] outline-none"
          />
          <FieldError message={fieldMessage(error, "display_name")} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="email">
            {t("register.email")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="off"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setCodeSent(false);
            }}
            className="mt-2 w-full border-0 border-b border-black py-2 font-sans text-[15px] outline-none"
          />
          <FieldError message={emailError} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="password">
            {t("register.password")}
          </label>
          <ManualPasswordInput id="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          <FieldError message={fieldMessage(error, "password")} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="code">
            {t("register.code")}
          </label>
          <div className="mt-2 flex items-end gap-3">
            <input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
              className="min-w-0 flex-1 border-0 border-b border-black py-2 font-sans text-[15px] outline-none"
            />
            <button
              type="button"
              disabled={sendingCode || waiting}
              onClick={onSendCode}
              className="inline-flex shrink-0 items-center gap-2 border border-black px-4 py-2.5 font-sans text-[13px] uppercase tracking-[0.16em] disabled:opacity-40"
            >
              {sendingCode ? <ButtonSpinner /> : null}
              {sendingCode ? t("register.sending") : waiting ? t("code.wait", { seconds: secondsLeft }) : t("register.send")}
            </button>
          </div>
          <FieldError message={fieldMessage(error, "code")} />
          <p className="mt-2 font-sans text-[15px] text-neutral-500">{t("code.hint")}</p>
          {(codeSent || waiting) && !fieldMessage(error, "code") && !emailError ? (
            <p className="mt-2 font-sans text-[15px] text-neutral-500">{t("register.sent")}</p>
          ) : null}
        </div>
        <div>
          <label className="flex items-start gap-3 font-sans text-[15px] leading-6" htmlFor="accept_terms">
            <input
              id="accept_terms"
              type="checkbox"
              checked={acceptTerms}
              onChange={(event) => {
                setAcceptTerms(event.target.checked);
                if (event.target.checked) setTermsError("");
              }}
              className="mt-1"
            />
            <span>
              {t("register.agree")}{" "}
              <button
                type="button"
                className="text-[#1A4FBF]"
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  setTermsOpen(true);
                }}
              >
                {t("register.agreement")}
              </button>
              .
            </span>
          </label>
          <FieldError message={(termsError === "accept" ? t("register.mustAccept") : termsError) || fieldMessage(error, "accept_terms")} />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="inline-flex items-center gap-2 rounded-[2px] bg-black px-6 py-2.5 font-sans text-[13px] uppercase tracking-[0.16em] text-white disabled:opacity-40"
        >
          {submitting ? <ButtonSpinner /> : null}
          {t("register.submit")}
        </button>
      </form>
      <p className="mt-6 font-sans text-[15px] text-neutral-500">
        {t("register.have")}{" "}
        <Link to={`/sign-in${nextQuery}`} className="text-[#1A4FBF]">
          {t("signIn.submit")}
        </Link>
      </p>
      {termsOpen ? (
        <TermsDialog
          onClose={() => setTermsOpen(false)}
          onAgree={() => {
            setAcceptTerms(true);
            setTermsError("");
            setTermsOpen(false);
          }}
        />
      ) : null}
    </div>
  );
}
