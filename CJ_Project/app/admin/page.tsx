import { ShieldAlert } from "lucide-react";
import { requireChatGPTUser } from "../chatgpt-auth";
import { isAllowedAdminUser } from "@/lib/admin-auth";
import { AdminEditor } from "./admin-editor";

export default async function AdminPage() {
  const user = await requireChatGPTUser("/admin");
  if (!isAllowedAdminUser(user)) {
    return (
      <main className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
        <section className="mx-auto flex max-w-2xl flex-col items-center px-4 py-24 text-center">
          <div className="mb-5 grid size-14 place-items-center rounded-2xl bg-[var(--accent)] text-[var(--blue-600)]">
            <ShieldAlert />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">没有访问权限</h1>
          <p className="mt-2 max-w-md text-sm text-[var(--muted-foreground)]">
            当前 ChatGPT 账号不在管理员名单中。如果你认为这是错误，请联系管理员把你的账号加入
            CJ_ADMIN_ALLOWLIST。
          </p>
        </section>
      </main>
    );
  }
  return <AdminEditor />;
}
