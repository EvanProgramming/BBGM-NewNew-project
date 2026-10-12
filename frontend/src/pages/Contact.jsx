import { FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";

export default function Contact() {
  const { t } = useI18n();
  return (
    <div className="mx-auto mt-8 max-w-2xl">
      <FrontPageLink />
      <SectionRule>{t("contact.kicker")}</SectionRule>
      <p className="font-serif text-3xl leading-snug">{t("contact.lead")}</p>
    </div>
  );
}
