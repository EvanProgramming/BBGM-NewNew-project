/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, api } from "./api";
import { clearCjHello } from "./cjHello";
import { useLiveRefresh } from "./live";

const AuthContext = createContext(null);

function sameProfile(left, right) {
  return (
    left?.id === right?.id &&
    left?.email === right?.email &&
    left?.display_name === right?.display_name &&
    JSON.stringify(left?.roles || []) === JSON.stringify(right?.roles || []) &&
    left?.avatar === right?.avatar &&
    Boolean(left?.muted) === Boolean(right?.muted)
  );
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch((err) => {
        if (!cancelled) setUser(null);
        if (!(err instanceof ApiError && err.status === 401)) {
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      const profile = await api.me();
      setUser((current) => (sameProfile(current, profile) ? current : profile));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      }
    }
  }, []);

  useLiveRefresh(ready && Boolean(user), refreshMe);

  const signIn = useCallback((profile) => {
    clearCjHello(profile?.id);
    setUser(profile);
  }, []);

  const signOut = useCallback(async () => {
    const userId = user?.id;
    try {
      await api.logout();
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        throw err;
      }
    }
    clearCjHello(userId);
    setUser(null);
    if (
      location.pathname === "/me/posts" ||
      location.pathname === "/me/avatar" ||
      location.pathname === "/me/password" ||
      location.pathname === "/admin/users" ||
      location.pathname === "/admin/forum-agents" ||
      location.pathname === "/news/drafts" ||
      location.pathname === "/system"
    ) {
      navigate("/");
    }
  }, [user, location.pathname, navigate]);

  const value = useMemo(
    () => ({ user, ready, signIn, signOut, setUser }),
    [user, ready, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
