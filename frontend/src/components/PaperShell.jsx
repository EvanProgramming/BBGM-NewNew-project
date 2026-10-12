import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth";
import { Avatar } from "./Avatar";
import { ButtonSpinner } from "./ui";
import { canEditNews, CATEGORY_ROUTES, formatToday, hasRole } from "../format";
import { useI18n } from "../i18n";
import { TermsDialog } from "../pages/Terms";

function navClass({ isActive }) {
  return `font-sans text-[12px] font-medium uppercase tracking-[0.18em] ${
    isActive ? "text-neutral-900" : "text-neutral-900 hover:text-[#1A4FBF]"
  }`;
}

const menuItemClass =
  "block w-full px-4 py-2 text-left uppercase tracking-[0.18em] hover:text-[#1A4FBF]";

function BarMenu({ label, open, onToggle, children }) {
  return (
    <div className="relative">
      <button
        type="button"
        className="uppercase"
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

function SearchIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[15px] w-[15px] shrink-0 text-[#1A4FBF]"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16.2 16.2 4.3 4.3" />
    </svg>
  );
}

const NAV_KEYS = {
  "/forum": "nav.forum",
  "/cj": "nav.cj",
  "/opinion": "nav.opinion",
};

export default function PaperShell() {
  const { user, signOut } = useAuth();
  const { lang, t } = useI18n();
  const location = useLocation();
  const barRef = useRef(null);
  const [query, setQuery] = useState("");
  const [searchNotice, setSearchNotice] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [openMenu, setOpenMenu] = useState(null);

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

  function onSearch(event) {
    event.preventDefault();
    setSearchNotice(true);
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
      <div className="mx-auto max-w-[1180px] px-8 pb-20">
        <div
          ref={barRef}
          className="border-b border-black py-[10px] font-sans text-[11px] font-medium tracking-[0.18em] text-[#111111]"
        >
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 uppercase" aria-label="Site">
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
                <Link to="/me/posts" className="uppercase">
                  {t("shell.myPosts")}
                </Link>
              ) : null}
              <Link to="/system" className="uppercase">
                {t("shell.notices")}
              </Link>
            </nav>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              {user ? (
                <>
                  <Link
                    to="/me/avatar"
                    className="flex items-center gap-2.5 normal-case tracking-normal text-[#111111]"
                  >
                    <Avatar avatar={user.avatar} size={28} />
                    {user.display_name}
                  </Link>
                  <button type="button" onClick={onSignOut} disabled={signingOut} className="inline-flex items-center gap-2 uppercase disabled:opacity-40">
                    {signingOut ? <ButtonSpinner /> : null}
                    {t("shell.signOut")}
                  </button>
                </>
              ) : (
                <Link to="/sign-in" className="uppercase">
                  {t("shell.signIn")}
                </Link>
              )}
              <p className="font-medium tracking-[0.06em] text-[#111111] sm:ml-1 sm:border-l sm:border-black sm:pl-5">
                {t("shell.today", { date: formatToday(lang) })}
              </p>
            </div>
          </div>
        </div>

        <header className="grid grid-cols-[1fr_auto_1fr] items-center gap-6 pb-1 pt-8">
          <form onSubmit={onSearch} className="flex max-w-[13rem] items-end gap-2">
            <label className="sr-only" htmlFor="masthead-search">
              {t("shell.search")}
            </label>
            <SearchIcon />
            <input
              id="masthead-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("shell.searchPlaceholder")}
              className="w-full border-0 border-b border-black bg-transparent pb-[3px] font-sans text-[13px] font-normal text-[#111111] outline-none placeholder:text-neutral-400"
            />
          </form>

          <Link
            to="/"
            aria-label="Elegram"
            className="relative z-10 flex cursor-pointer items-center justify-center whitespace-nowrap no-underline"
          >
            <span className="font-wordmark-elegram text-[52px] sm:text-[68px]">Elegram</span>
          </Link>

          <div className="text-right">
            <p className="font-sans text-[10px] font-semibold tracking-[0.16em] text-[#1A4FBF]">
              {t("shell.ownedBy")}
            </p>
            <p className="mt-[3px] font-sans text-[10px] font-normal tracking-[0.01em] text-neutral-500">
              {t("shell.owners")}
            </p>
          </div>
        </header>

        <p className="pb-6 pt-4 text-center font-sans text-[13px] font-semibold uppercase tracking-[0.28em] text-[#111111]">
          <Link to="/" className="text-inherit no-underline">
            {t("shell.tagline")}
          </Link>
        </p>

        <nav className="flex flex-wrap items-center justify-center gap-x-10 gap-y-2 border-b-[2.5px] border-black pb-[14px]">
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
              {t(NAV_KEYS[item.to] || item.label)}
            </NavLink>
          ))}
        </nav>

        {location.pathname === "/forum" || location.pathname.startsWith("/forum/") ? (
          <nav
            className="flex flex-wrap items-center justify-center gap-x-8 gap-y-2 border-b border-neutral-200 py-3"
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
                className={({ isActive }) =>
                  `font-sans text-[13px] ${
                    isActive
                      ? "text-[#1A4FBF] underline decoration-2 underline-offset-[7px]"
                      : "text-neutral-900 hover:text-[#1A4FBF]"
                  }`
                }
              >
                {t(item.label)}
              </NavLink>
            ))}
          </nav>
        ) : null}

        {searchNotice ? (
          <p className="mt-3 font-sans text-sm text-neutral-500">{t("shell.searchLater")}</p>
        ) : null}

        <Outlet />

        <p className="mt-16 border-t border-neutral-200 pt-4 font-sans text-[11px] leading-5 text-neutral-500">
          {t("shell.footer")}
        </p>
      </div>
      {termsOpen ? <TermsDialog onClose={() => setTermsOpen(false)} /> : null}
    </div>
  );
}
