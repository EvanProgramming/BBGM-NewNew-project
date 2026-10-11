import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { ButtonSpinner, ErrorBanner, FrontPageLink, SectionRule } from "../components/ui";
import { useI18n } from "../i18n";
import { useLiveRefresh } from "../live";

const ASSIGNABLE = ["student", "teacher", "editor", "admin"];

export default function AdminUsers() {
  const { user, ready, setUser } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState("");

  useEffect(() => {
    if (!ready) return;
    if (!user) {
      navigate("/sign-in?next=/admin/users", { replace: true });
      return;
    }
    if (!user.roles?.includes("super_admin")) {
      navigate("/", { replace: true });
    }
  }, [ready, user, navigate]);

  const refreshUsers = useCallback(async () => {
    const data = await api.listUsers({ pageSize: 50 });
    setItems(data.items);
    setError(null);
  }, []);

  useEffect(() => {
    if (!user?.roles?.includes("super_admin")) return undefined;
    let cancelled = false;
    setLoading(true);
    refreshUsers()
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setUser(null);
          navigate("/sign-in?next=/admin/users");
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          navigate("/", { replace: true });
          return;
        }
        setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, navigate, setUser, refreshUsers]);

  useLiveRefresh(Boolean(user?.roles?.includes("super_admin")) && !loading, refreshUsers);

  function replaceItem(updated) {
    setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function runAction(key, action) {
    setPending(key);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err);
    } finally {
      setPending("");
    }
  }

  function toggleRole(target, role) {
    const current = (target.roles || []).filter((item) => ASSIGNABLE.includes(item));
    const next = current.includes(role)
      ? current.filter((item) => item !== role)
      : [...current, role];
    return runAction(`${target.id}:role:${role}`, async () => {
      const updated = await api.patchUserRoles(target.id, next);
      replaceItem(updated);
      if (updated.id === user.id) setUser(updated);
    });
  }

  function setMuted(target, muted) {
    return runAction(`${target.id}:muted`, async () => {
      replaceItem(await api.setUserMuted(target.id, muted));
    });
  }

  function removeUser(target) {
    if (!window.confirm(t("users.deleteConfirm", { name: target.display_name }))) return undefined;
    return runAction(`${target.id}:delete`, async () => {
      await api.deleteUser(target.id);
      setItems((current) => current.filter((item) => item.id !== target.id));
    });
  }

  if (!ready || !user?.roles?.includes("super_admin")) return null;

  return (
    <div className="mt-8">
      <FrontPageLink />
      <SectionRule>{t("users.title")}</SectionRule>
      <ErrorBanner error={error} />
      {loading ? (
        <p className="font-sans text-sm text-neutral-500">{t("users.loading")}</p>
      ) : (
        <table className="w-full border-t border-black font-sans text-sm">
          <thead>
            <tr className="border-b border-black text-left text-[11px] uppercase tracking-[0.14em]">
              <th className="py-3 font-medium">{t("users.name")}</th>
              <th className="py-3 font-medium">{t("users.email")}</th>
              <th className="py-3 font-medium">{t("users.role")}</th>
              <th className="py-3 font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const roles = item.roles || [];
              const protectedAccount = roles.includes("super_admin") || item.id === user.id;
              return (
                <tr key={item.id} className="border-b border-neutral-200 align-top">
                  <td className="py-3">{item.display_name}</td>
                  <td className="py-3">{item.email}</td>
                  <td className="py-3">
                    <div className="flex max-w-[18rem] flex-wrap gap-1">
                      {ASSIGNABLE.map((role) => {
                        const active = roles.includes(role);
                        const key = `${item.id}:role:${role}`;
                        return (
                          <button
                            key={role}
                            type="button"
                            disabled={Boolean(pending)}
                            onClick={() => toggleRole(item, role)}
                            className={`inline-flex items-center gap-1 border px-1.5 py-0.5 font-sans text-[10px] uppercase tracking-[0.08em] disabled:opacity-40 ${
                              active ? "border-black bg-black text-white" : "border-black bg-white text-black"
                            }`}
                          >
                            {pending === key ? <ButtonSpinner /> : null}
                            {t(`users.${role}`)}
                          </button>
                        );
                      })}
                      {roles.includes("super_admin") ? (
                        <span className="border border-[#1A4FBF] px-1.5 py-0.5 font-sans text-[10px] uppercase tracking-[0.08em] text-[#1A4FBF]">
                          {t("users.superAdmin")}
                        </span>
                      ) : null}
                    </div>
                  </td>
                  <td className="py-3 text-right">
                    {protectedAccount ? null : (
                      <div className="flex flex-wrap justify-end gap-x-4 gap-y-2">
                        <button
                          type="button"
                          disabled={Boolean(pending)}
                          onClick={() => setMuted(item, !item.muted)}
                          className="inline-flex items-center gap-1 uppercase tracking-[0.12em] text-[#1A4FBF] disabled:opacity-40"
                        >
                          {pending === `${item.id}:muted` ? <ButtonSpinner /> : null}
                          {item.muted ? t("users.unmute") : t("users.mute")}
                        </button>
                        <button
                          type="button"
                          disabled={Boolean(pending)}
                          onClick={() => removeUser(item)}
                          className="inline-flex items-center gap-1 uppercase tracking-[0.12em] text-red-700 disabled:opacity-40"
                        >
                          {pending === `${item.id}:delete` ? <ButtonSpinner /> : null}
                          {t("users.delete")}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
