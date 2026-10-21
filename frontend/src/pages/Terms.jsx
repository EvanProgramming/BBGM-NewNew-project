import { useEffect } from "react";
import { FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

function Paragraph({ part }) {
  return (
    <p className={`mt-3 font-sans text-[15px] leading-7 ${part.bold ? "font-semibold text-[#111111]" : ""}`}>
      {part.text}
    </p>
  );
}

function TermsBody() {
  const { terms } = useI18n();

  return (
    <>
      <SectionRule>{terms.title}</SectionRule>
      <p className="font-sans text-[15px] leading-7">{terms.makers}</p>
      <p className="mt-4 font-sans text-[15px] leading-7">{terms.covers}</p>
      <p className="mt-2 font-sans text-[13px] text-neutral-500">{terms.version}</p>
      <p className="mt-6 font-sans text-[15px] leading-7">
        {terms.lead.map((part) => (
          <span key={part.text} className={part.bold ? "font-semibold" : ""}>
            {part.text}
          </span>
        ))}
      </p>
      {terms.sections.map((section) => (
        <section key={section.heading} className="mt-8">
          <h3 className="font-serif text-xl">{section.heading}</h3>
          {section.paragraphs.map((part) => (
            <Paragraph key={part.text} part={part} />
          ))}
        </section>
      ))}
    </>
  );
}

export function TermsDialog({ onClose, onAgree }) {
  const { t } = useI18n();

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-10">
      <button type="button" className="absolute inset-0 cursor-default" aria-label={t("terms.close")} onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-dialog-title"
        className="relative z-10 w-full max-w-2xl bg-white p-8"
      >
        <h2 id="terms-dialog-title" className="sr-only">
          {t("terms.dialog")}
        </h2>
        <TermsBody />
        <div className="mt-8 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="border border-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.18em]"
          >
            {t("terms.close")}
          </button>
          {onAgree ? (
            <button
              type="button"
              onClick={onAgree}
              className="rounded-[2px] bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.18em] text-white"
            >
              {t("terms.agree")}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function Terms() {
  return (
    <div className="mx-auto mt-8 max-w-2xl">
      <FrontPageLink />
      <TermsBody />
    </div>
  );
}
