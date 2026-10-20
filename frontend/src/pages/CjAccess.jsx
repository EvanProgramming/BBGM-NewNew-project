import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { hasRole } from "../format";
import { hasSeenCjHello, markCjHelloSeen } from "../cjHello";
import { useI18n } from "../i18n";
import { SectionRule } from "../components/ui";

export const CJ_PAUSED = false;

export function CjPaused() {
  const { t } = useI18n();
  return (
    <div className="mt-8">
      <SectionRule>{t("nav.cj")}</SectionRule>
      <p className="font-serif text-3xl leading-snug">{t("cj.paused")}</p>
    </div>
  );
}

const CJ_HOME = [
  ["super_admin", "/cj/admin"],
  ["student", "/cj/student"],
  ["teacher", "/cj/student"],
];

function cjHome(user) {
  const match = CJ_HOME.find(([role]) => hasRole(user, role));
  return match ? match[1] : "/";
}

function LoadingAccess() {
  const { t } = useI18n();
  return <p className="mt-8 font-sans text-sm text-neutral-500">{t("cj.checkingAccess")}</p>;
}

export default function CjPortal() {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <LoadingAccess />;
  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/sign-in?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Navigate to={cjHome(user)} replace />;
}

function CjHello({ name }) {
  const { t } = useI18n();
  return (
    <div className="min-h-[70vh] px-2 pt-16 sm:px-6 sm:pt-20">
      <h1 className="cj-welcome-in text-left font-serif text-5xl leading-tight sm:text-7xl">{t("cj.hello", { name })}</h1>
    </div>
  );
}

export function RequireCjRole({ roles, children }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  const userId = user?.id;
  const seen = Boolean(userId && hasSeenCjHello(userId));
  const [released, setReleased] = useState(false);
  const entered = seen || released;

  useEffect(() => {
    if (!userId || hasSeenCjHello(userId)) return undefined;
    setReleased(false);
    const timer = window.setTimeout(() => {
      markCjHelloSeen(userId);
      setReleased(true);
    }, 3200);
    return () => window.clearTimeout(timer);
  }, [userId]);

  if (!ready) return <LoadingAccess />;
  if (!user) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/sign-in?next=${encodeURIComponent(next)}`} replace />;
  }
  if (!roles.some((role) => hasRole(user, role))) {
    return <Navigate to={cjHome(user)} replace />;
  }
  if (!entered) return <CjHello name={user.display_name} />;
  return children;
}
