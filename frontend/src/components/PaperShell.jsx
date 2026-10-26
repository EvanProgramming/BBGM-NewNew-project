import { useCallback, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useLiveRefresh } from "../live";
import { Avatar } from "./Avatar";
import { ButtonSpinner } from "./ui";
import { canEditNews, CATEGORY_ROUTES, formatToday, hasRole } from "../format";
import { useI18n } from "../i18n";
import { TermsDialog } from "../pages/Terms";

function navClass() {
  return "nav-pill font-serif text-[17px] font-semibold uppercase tracking-[0.03em] sm:text-[19px]";
}

const menuItemClass =
  "block w-full px-4 py-2.5 text-left text-[13px] font-semibold uppercase tracking-[0.14em] transition-colors hover:bg-[#1A4FBF] hover:text-white";

function BarMenu({ label, open, onToggle, children }) {
  return (
    <div className="relative">
      <button
        type="button"
        className="nav-pill uppercase"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={onToggle}
      >
        {label}
      </button>
      {open ? (
        <div role="menu" className="absolute left-0 top-full z-20 mt-2 min-w-[9.5rem] border border-black bg-white py-1">
          {children}
        </div>
      ) : null}
    </div>
  );
}

const NAV_KEYS = {
  "/forum": "nav.forum",
  "/bell": "nav.bell",
  "/bottles": "nav.bottles",
  "/cj": "nav.cj",
  "/opinion": "nav.opinion",
};

function ActivityBadge({ label }) {
  return (
    <span
      title={label}
      className="ml-1 inline-flex h-[16px] min-w-[16px] items-center justify-center rounded-full bg-[#E10600] px-[4px] font-sans text-[10px] font-bold leading-none tracking-normal text-white normal-case"
    >
      1
    </span>
  );
}

export default function PaperShell() {
  const { user, signOut } = useAuth();
  const { lang, t } = useI18n();
  const location = useLocation();
  const barRef = useRef(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [openMenu, setOpenMenu] = useState(null);
  const [forumUnread, setForumUnread] = useState(false);
  const [bottleUnread, setBottleUnread] = useState(false);
  const activitySeq = useRef(0);
  const bottleSeq = useRef(0);
  const onMine = location.pathname === "/forum/mine";

  const syncForumActivity = useCallback(async () => {
    const seq = activitySeq.current + 1;
    activitySeq.current = seq;
    const data = await api.forumActivity();
    if (seq !== activitySeq.current) return;
    const unread = data?.unread === 1;
    if (onMine) {
      if (unread) await api.readForumActivity();
      if (seq !== activitySeq.current) return;
      setForumUnread(false);
      return;
    }
    setForumUnread(unread);
  }, [onMine]);

  useEffect(() => {
    if (onMine) setForumUnread(false);
  }, [onMine]);

  useEffect(() => {
    if (!user) {
      setForumUnread(false);
      return undefined;
    }
    syncForumActivity().catch(() => {
      /* keep the last badge */
    });
    return undefined;
  }, [user, syncForumActivity]);

  const syncBottleActivity = useCallback(async () => {
    const seq = bottleSeq.current + 1;
    bottleSeq.current = seq;
    const data = await api.bottleActivity();
    if (seq !== bottleSeq.current) return;
    setBottleUnread(data?.unread === 1);
  }, []);

  useEffect(() => {
    if (!user) {
      setBottleUnread(false);
      return undefined;
    }
    syncBottleActivity().catch(() => {
      /* keep the last badge */
    });
    return undefined;
  }, [user, syncBottleActivity]);

  useLiveRefresh(Boolean(user), syncForumActivity);
  useLiveRefresh(Boolean(user), syncBottleActivity);

  useEffect(() => {
    setOpenMenu(null);
  }, [location.pathname]);

  useEffect(() => {
    function onPointerDown(event) {
      if (!barRef.current?.contains(event.target)) setOpenMenu(null);
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setOpenMenu(null);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  function toggleMenu(name) {
    setOpenMenu((current) => (current === name ? null : name));
  }

  async function onSignOut() {
    setSigningOut(true);
    try {
      await signOut();
    } catch {
      /* 401 still signs out in auth */
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="min-h-screen bg-white text-[#111111]">
      <div className="mx-auto max-w-[1920px] px-4 pb-20 sm:px-8 lg:px-20 xl:px-[210px]">
        <div
          ref={barRef}
          className="full-bleed-rule-thin py-2.5 font-sans text-[13px] font-semibold tracking-[0.14em] text-[#111111] sm:text-[14px]"
        >
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <nav className="flex flex-wrap items-center gap-x-2 gap-y-1 uppercase" aria-label="Site">
              <BarMenu label={t("shell.system")} open={openMenu === "system"} onToggle={() => toggleMenu("system")}>
                <Link role="menuitem" to="/about" className={menuItemClass}>
                  {t("shell.about")}
                </Link>
                <button
                  type="button"
                  role="menuitem"
                  className={menuItemClass}
                  onClick={() => {
                    setOpenMenu(null);
                    setTermsOpen(true);
                  }}
                >
                  {t("shell.terms")}
                </button>
                <Link role="menuitem" to="/contact" className={menuItemClass}>
                  {t("shell.contact")}
                </Link>
              </BarMenu>
              {user ? (
                <BarMenu
                  label={t("shell.settings")}
                  open={openMenu === "settings"}
                  onToggle={() => toggleMenu("settings")}
                >
                  <Link role="menuitem" to="/me/avatar" className={menuItemClass}>
                    {t("shell.avatar")}
                  </Link>
                  <Link role="menuitem" to="/me/password" className={menuItemClass}>
                    {t("shell.password")}
                  </Link>
                  {hasRole(user, "super_admin") ? (
                    <Link role="menuitem" to="/admin/users" className={menuItemClass}>
                      {t("shell.users")}
                    </Link>
                  ) : null}
                </BarMenu>
              ) : null}
              {user ? (
                <Link to="/me/posts" className="nav-pill uppercase">
                  {t("shell.myPosts")}
                </Link>
              ) : null}
              <Link to="/system" className="nav-pill uppercase">
                {t("shell.notices")}
              </Link>
            </nav>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              {user ? (
                <>
                  <Link
                    to="/me/avatar"
                    className="flex items-center gap-2.5 normal-case tracking-normal text-[#111111]"
                  >
                    <Avatar avatar={user.avatar} size={28} />
                    {user.display_name}
                  </Link>
                  <button type="button" onClick={onSignOut} disabled={signingOut} className="nav-pill inline-flex items-center gap-2 uppercase disabled:opacity-40">
                    {signingOut ? <ButtonSpinner /> : null}
                    {t("shell.signOut")}
                  </button>
                </>
              ) : (
                <Link to="/sign-in" className="nav-pill uppercase">
                  {t("shell.signIn")}
                </Link>
              )}
              <p className="font-medium tracking-[0.06em] text-[#111111] sm:ml-1 sm:border-l sm:border-black sm:pl-5">
                {t("shell.today", { date: formatToday(lang) })}
              </p>
            </div>
          </div>
        </div>

        <header className="flex items-center justify-center pb-1 pt-7 sm:pt-9">
          <Link
            to="/"
            aria-label="Elegram"
            className="relative z-10 flex cursor-pointer items-center justify-center whitespace-nowrap no-underline"
          >
            <span className="font-wordmark-elegram text-[58px] sm:text-[86px]">Elegram</span>
          </Link>
        </header>

        <p className="pb-7 pt-5 text-center font-serif text-[14px] font-bold uppercase tracking-[0.08em] text-[#111111] sm:text-[18px]">
          <Link to="/" className="text-inherit no-underline">
            {t("shell.tagline")}
          </Link>
        </p>

        <nav className="full-bleed-rule flex flex-wrap items-center justify-center gap-x-1 gap-y-1 pb-3 sm:gap-x-3">
          <NavLink to="/" end className={navClass}>
            {t("nav.news")}
          </NavLink>
          {canEditNews(user) ? (
            <NavLink to="/news/submit" className={navClass}>DRAFT</NavLink>
          ) : null}
          {hasRole(user, "super_admin") ? (
            <NavLink to="/news/design" className={navClass}>DESIGN</NavLink>
          ) : null}
          {CATEGORY_ROUTES.map((item) => (
            <NavLink key={item.to} to={item.to} className={navClass}>
              <span className="inline-flex items-center">
                {t(NAV_KEYS[item.to] || item.label)}
                {item.to === "/forum" && forumUnread ? <ActivityBadge label={t("forum.activityBadge")} /> : null}
                {item.to === "/bottles" && bottleUnread ? <ActivityBadge label={t("bottle.activityBadge")} /> : null}
              </span>
            </NavLink>
          ))}
        </nav>

        {user && (location.pathname === "/forum" || location.pathname.startsWith("/forum/")) ? (
          <nav
            className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-neutral-300 py-3"
            aria-label="Forum"
          >
            {[
              { to: "/forum", end: true, label: "forum.recommended" },
              { to: "/forum/latest", label: "forum.latest" },
              { to: "/forum/all", label: "forum.all" },
              { to: "/forum/mine", label: "forum.mine" },
            ].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className="nav-pill inline-flex items-center font-sans text-[14px] font-bold"
              >
                {() => (
                  <>
                    <span>{t(item.label)}</span>
                    {item.to === "/forum/mine" && forumUnread ? (
                      <ActivityBadge label={t("forum.activityBadge")} />
                    ) : null}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        ) : null}

        <Outlet />

        <p className="mt-16 border-t border-neutral-300 pt-5 font-sans text-[13px] font-medium leading-6 text-neutral-600">
          {t("shell.footer")}
        </p>
      </div>
      {termsOpen ? <TermsDialog onClose={() => setTermsOpen(false)} /> : null}
    </div>
  );
}
