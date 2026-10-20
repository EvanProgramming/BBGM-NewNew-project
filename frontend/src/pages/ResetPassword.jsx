import { useState } from "react";
import { Link } from "react-router-dom";
import { api, fieldMessage } from "../api";
import { ButtonSpinner, ErrorBanner, FieldError, FrontPageLink, ManualPasswordInput, SectionRule } from "../components/ui";
import { useCodeCooldown } from "../emailCodeWait";
import { useI18n } from "../i18n";

export default function ResetPassword() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [done, setDone] = useState(false);
  const { secondsLeft, begin: beginWait } = useCodeCooldown("reset", email);
  const waiting = secondsLeft > 0;

  async function onSendCode() {
    if (waiting || sendingCode) return;
    setSendingCode(true);
    setError(null);
    try {
      await api.sendEmailCode({ email, purpose: "reset" });
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
    setSubmitting(true);
    setError(null);
    try {
      await api.resetPassword({ email, code, password });
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  const banner = error && !error.fields?.length ? error : null;

  if (done) {
    return (
      <div className="mx-auto mt-10 max-w-lg">
        <FrontPageLink />
        <SectionRule>{t("reset.title")}</SectionRule>
        <p className="font-sans text-[15px] text-neutral-700">{t("reset.updated")}</p>
        <p className="mt-4 font-sans text-[15px]">
          <Link to="/sign-in" className="text-[#1A4FBF]">
            {t("signIn.submit")}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-10 max-w-lg">
      <FrontPageLink />
      <SectionRule>{t("reset.title")}</SectionRule>
      <ErrorBanner error={banner} />
      <form onSubmit={onSubmit} autoComplete="off" className="space-y-5">
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="email">
            {t("reset.email")}
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
          <FieldError message={fieldMessage(error, "email")} />
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="code">
            {t("reset.code")}
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
          {(codeSent || waiting) && !fieldMessage(error, "code") && !fieldMessage(error, "email") ? (
            <p className="mt-2 font-sans text-[15px] text-neutral-500">{t("reset.sent")}</p>
          ) : null}
        </div>
        <div>
          <label className="block font-sans text-[13px] uppercase tracking-[0.16em] text-[#1A4FBF]" htmlFor="password">
            {t("reset.new")}
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
          {t("reset.submit")}
        </button>
      </form>
      <p className="mt-6 font-sans text-[15px] text-neutral-500">
        <Link to="/sign-in" className="text-[#1A4FBF]">
          {t("reset.back")}
        </Link>
      </p>
    </div>
  );
}
