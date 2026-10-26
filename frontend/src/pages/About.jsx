import { FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

export default function About() {
  const { t } = useI18n();
  return (
    <div className="mx-auto mt-8 max-w-2xl">
      <FrontPageLink />
      <SectionRule>{t("about.kicker")}</SectionRule>
      <p className="font-serif text-3xl leading-snug">{t("about.lead")}</p>
      <p className="mt-4 font-sans text-[15px] leading-7">{t("about.body")}</p>
      <p className="mt-4 font-sans text-[15px] leading-7">{t("about.newsletter")}</p>
      <p className="mt-4 font-sans text-[15px] leading-7">{t("about.adviser")}</p>
      <p className="mt-4 font-sans text-[15px] leading-7 text-neutral-500">{t("about.not")}</p>
    </div>
  );
}
