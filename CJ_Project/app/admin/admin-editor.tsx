"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookOpen, CheckCircle2, KeyRound, Save, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Toaster } from "@/components/ui/sonner";
import type { CJEntry, CJPayload, Exam } from "../cj-types";

const days = ["周一", "周二", "周三", "周四", "周五"];

type CJInput = { weekStart: string; dayIndex: number; subjectId: string; ic: string; hw: string; announcement: string };
type ExamInput = { id?: string; weekStart: string; dayIndex: number; title: string; time: string; location: string; note: string };
type ModelContext = { registerTool: (tool: { name: string; title: string; description: string; inputSchema: object; annotations: { readOnlyHint: boolean; untrustedContentHint: boolean }; execute: (input: unknown) => Promise<unknown> }, options: { signal: AbortSignal }) => void | Promise<void> };

function mondayIso(date = new Date()) {
  const result = new Date(date);
  const day = result.getDay();
  result.setDate(result.getDate() - (day === 0 ? 6 : day - 1));
  return `${result.getFullYear()}-${String(result.getMonth() + 1).padStart(2, "0")}-${String(result.getDate()).padStart(2, "0")}`;
}

export function AdminEditor() {
  const [weekStart, setWeekStart] = useState(mondayIso);
  const [data, setData] = useState<CJPayload | null>(null);
  const [adminCode, setAdminCode] = useState("");
  const [dayIndex, setDayIndex] = useState(0);
  const [subjectId, setSubjectId] = useState("");
  const [ic, setIc] = useState("");
  const [hw, setHw] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [examId, setExamId] = useState("");
  const [examDayIndex, setExamDayIndex] = useState(0);
  const [examTitle, setExamTitle] = useState("");
  const [examTime, setExamTime] = useState("09:00");
  const [examLocation, setExamLocation] = useState("");
  const [examNote, setExamNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const loadWeek = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/cj?weekStart=${weekStart}`, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取这一周的 CJ");
      const payload = (await response.json()) as CJPayload;
      setData(payload);
      setSubjectId((current) => current || payload.subjects[0]?.id || "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  // Data fetching intentionally owns the loading state for each selected week.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadWeek(); }, [loadWeek]);

  const currentEntry = useMemo(
    () => data?.entries.find((entry) => entry.dayIndex === dayIndex && entry.subjectId === subjectId),
    [data, dayIndex, subjectId],
  );
  // Keep the editor fields synchronized with the selected published entry.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIc(currentEntry?.ic ?? "");
    setHw(currentEntry?.hw ?? "");
    setAnnouncement(currentEntry?.announcement ?? "");
  }, [currentEntry]);

  const authorizedRequest = useCallback(async (method: "PUT" | "POST", url: string, body: object) => {
    if (!adminCode.trim()) throw new Error("请输入管理员口令");
    const response = await fetch(url, {
      method,
      headers: { "content-type": "application/json", "x-cj-admin-code": adminCode.trim() },
      body: JSON.stringify(body),
    });
    const result = (await response.json()) as { error?: string; id?: string; updatedAt?: string };
    if (!response.ok) throw new Error(result.error ?? "保存失败");
    await loadWeek();
    return result;
  }, [adminCode, loadWeek]);

  const persistCJ = useCallback((entry: CJInput) => authorizedRequest("PUT", "/api/cj", entry), [authorizedRequest]);
  const persistExam = useCallback((exam: ExamInput) => authorizedRequest("PUT", "/api/exams", exam), [authorizedRequest]);

  const seedSample = useCallback(async () => {
    setSaving(true);
    try {
      await authorizedRequest("POST", "/api/cj/seed", { weekStart });
      toast.success("示例数据已初始化");
    } catch (seedError) {
      toast.error(seedError instanceof Error ? seedError.message : "初始化失败");
    } finally {
      setSaving(false);
    }
  }, [authorizedRequest, weekStart]);

  async function handleCJSave() {
    if (!subjectId) return toast.error("请选择 Subject");
    setSaving(true);
    try {
      await persistCJ({ weekStart, dayIndex, subjectId, ic, hw, announcement });
      toast.success("CJ 已保存");
    } catch (saveError) {
      toast.error(saveError instanceof Error ? saveError.message : "保存失败");
    } finally { setSaving(false); }
  }

  async function handleExamSave() {
    if (!examTitle.trim()) return toast.error("请输入考试名称");
    setSaving(true);
    try {
      const result = await persistExam({ id: examId || undefined, weekStart, dayIndex: examDayIndex, title: examTitle, time: examTime, location: examLocation, note: examNote });
      setExamId(result.id ?? "");
      toast.success("考试安排已保存");
    } catch (saveError) {
      toast.error(saveError instanceof Error ? saveError.message : "保存失败");
    } finally { setSaving(false); }
  }

  useEffect(() => {
    const context = (document as Document & { modelContext?: ModelContext }).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const registrations = [
      context.registerTool({
        name: "update_cj_entry",
        title: "更新 CJ",
        description: "更新指定周、星期和学科的 IC、HW 与 A；学生可自行把该学科安排在任意 Period。",
        inputSchema: { type: "object", properties: { weekStart: { type: "string", pattern: "^\\d{4}-\\d{2}-\\d{2}$" }, dayIndex: { type: "integer", minimum: 0, maximum: 4 }, subjectId: { type: "string" }, ic: { type: "string", maxLength: 800 }, hw: { type: "string", maxLength: 800 }, announcement: { type: "string", maxLength: 800 } }, required: ["weekStart", "dayIndex", "subjectId", "ic", "hw", "announcement"], additionalProperties: false },
        annotations: { readOnlyHint: false, untrustedContentHint: false },
        execute: async (input) => {
          const entry = input as CJInput;
          const result = await persistCJ(entry);
          setWeekStart(entry.weekStart); setDayIndex(entry.dayIndex); setSubjectId(entry.subjectId); setIc(entry.ic); setHw(entry.hw); setAnnouncement(entry.announcement);
          return { status: "saved", id: result.id };
        },
      }, { signal: lifecycle.signal }),
      context.registerTool({
        name: "update_exam",
        title: "更新考试安排",
        description: "创建或更新指定周内的一条考试时间安排。",
        inputSchema: { type: "object", properties: { id: { type: "string" }, weekStart: { type: "string", pattern: "^\\d{4}-\\d{2}-\\d{2}$" }, dayIndex: { type: "integer", minimum: 0, maximum: 4 }, title: { type: "string", minLength: 1, maxLength: 800 }, time: { type: "string", pattern: "^\\d{2}:\\d{2}$" }, location: { type: "string", maxLength: 800 }, note: { type: "string", maxLength: 800 } }, required: ["weekStart", "dayIndex", "title", "time", "location", "note"], additionalProperties: false },
        annotations: { readOnlyHint: false, untrustedContentHint: false },
        execute: async (input) => {
          const exam = input as ExamInput;
          const result = await persistExam(exam);
          setWeekStart(exam.weekStart); setExamId(result.id ?? exam.id ?? ""); setExamDayIndex(exam.dayIndex); setExamTitle(exam.title); setExamTime(exam.time); setExamLocation(exam.location); setExamNote(exam.note);
          return { status: "saved", id: result.id };
        },
      }, { signal: lifecycle.signal }),
    ];
    void Promise.all(registrations.map((registration) => Promise.resolve(registration))).catch((registrationError) => {
      if (!(registrationError instanceof DOMException && registrationError.name === "AbortError")) console.warn("WebMCP registration failed", registrationError);
    });
    return () => lifecycle.abort();
  }, [persistCJ, persistExam]);

  function editEntry(entry: CJEntry) { setDayIndex(entry.dayIndex); setSubjectId(entry.subjectId); window.scrollTo({ top: 0, behavior: "smooth" }); }
  function editExam(exam: Exam) { setExamId(exam.id); setExamDayIndex(exam.dayIndex); setExamTitle(exam.title); setExamTime(exam.time); setExamLocation(exam.location); setExamNote(exam.note); window.scrollTo({ top: 0, behavior: "smooth" }); }

  const subjectMap = useMemo(() => new Map(data?.subjects.map((subject) => [subject.id, subject]) ?? []), [data]);

  return (
    <main className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <Toaster richColors position="top-center" />
      <header className="site-header">
        <div className="site-header-inner max-w-6xl">
          <Link href="/" className="brand-mark"><span className="brand-icon"><BookOpen /></span><span><strong>CJ 管理端</strong><small>BASIS BILINGUAL GUANGMING</small></span></Link>
          <Button asChild variant="ghost" className="rounded-full"><Link href="/"><ArrowLeft /> 返回月历</Link></Button>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-4 py-8 sm:px-7 lg:py-12">
        <div className="mb-7">
          <p className="eyebrow"><Settings2 /> ADMIN WORKSPACE</p>
          <h1 className="page-title">内容管理</h1>
          <p className="page-description">这里按日期和学科更新 CJ；学生会在自己的 Period 课表中查看。</p>
        </div>

        <div className="mb-5 grid gap-4 rounded-3xl border border-[var(--border)] bg-white p-5 shadow-sm sm:grid-cols-2">
          <Field label="管理员口令"><div className="relative"><KeyRound className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--muted-foreground)]" /><Input aria-label="管理员口令" type="password" value={adminCode} onChange={(event) => setAdminCode(event.target.value)} placeholder="与 CJ_ADMIN_CODE 一致的共享口令" className="h-11 rounded-xl pl-10" /></div></Field>
          <Field label="周一日期"><Input aria-label="周一日期" type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} className="h-11 rounded-xl" /></Field>
        </div>

        <Tabs defaultValue="cj" className="gap-5">
          <TabsList className="h-11 rounded-full bg-[var(--blue-100)] p-1">
            <TabsTrigger value="cj" className="rounded-full px-5">每日 CJ</TabsTrigger>
            <TabsTrigger value="exams" className="rounded-full px-5">考试安排</TabsTrigger>
          </TabsList>

          <TabsContent value="cj">
            <div className="admin-grid">
              <form className="admin-card" onSubmit={(event) => { event.preventDefault(); void handleCJSave(); }}>
                <AdminCardHeader title={currentEntry ? "更新现有 CJ" : "添加 CJ"} published={Boolean(currentEntry)} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="日期"><DaySelect value={dayIndex} onChange={setDayIndex} /></Field>
                  <Field label="Subject"><Select value={subjectId} onValueChange={setSubjectId}><SelectTrigger aria-label="Subject" className="h-11 w-full rounded-xl"><SelectValue placeholder="选择 Subject" /></SelectTrigger><SelectContent>{(data?.subjects ?? []).map((subject) => <SelectItem key={subject.id} value={subject.id}>{subject.name}</SelectItem>)}</SelectContent></Select></Field>
                  <div className="sm:col-span-2 rounded-2xl bg-[var(--blue-50)] p-4 text-sm text-[var(--blue-700)]"><strong>学科不绑定固定 Period</strong><p className="mt-1 text-xs opacity-70">学生可以在自己的课表中把这门课放到任意 Period。</p></div>
                  <div className="sm:col-span-2"><Field label="IC"><Textarea aria-label="IC" value={ic} onChange={(event) => setIc(event.target.value)} className="min-h-24 rounded-xl" maxLength={800} /></Field></div>
                  <div className="sm:col-span-2"><Field label="HW"><Textarea aria-label="HW" value={hw} onChange={(event) => setHw(event.target.value)} className="min-h-24 rounded-xl" maxLength={800} /></Field></div>
                  <div className="sm:col-span-2"><Field label="A"><Textarea aria-label="A" value={announcement} onChange={(event) => setAnnouncement(event.target.value)} className="min-h-20 rounded-xl" maxLength={800} /></Field></div>
                </div>
                <SaveButton saving={saving} disabled={loading || !subjectId} label="保存 CJ" />
              </form>
              <AdminList title="本周 CJ" count={data?.entries.length ?? 0} loading={loading} error={error} headerAction={!loading && !error && (data?.entries.length ?? 0) === 0 ? (<button type="button" onClick={() => void seedSample()} disabled={saving} className="rounded-full border border-[var(--blue-600)] px-3 py-1 text-xs font-bold text-[var(--blue-600)] hover:bg-[var(--blue-50)] disabled:opacity-40">初始化示例数据</button>) : null}>{(data?.entries ?? []).map((entry) => <button key={entry.id} type="button" onClick={() => editEntry(entry)} className="admin-list-item"><span><strong>{subjectMap.get(entry.subjectId)?.shortName}</strong><small>{entry.ic || "暂无 IC"}</small></span><b>{days[entry.dayIndex]}</b></button>)}</AdminList>
            </div>
          </TabsContent>

          <TabsContent value="exams">
            <div className="admin-grid">
              <form className="admin-card" onSubmit={(event) => { event.preventDefault(); void handleExamSave(); }}>
                <AdminCardHeader title={examId ? "更新考试安排" : "添加考试安排"} published={Boolean(examId)} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="日期"><DaySelect value={examDayIndex} onChange={setExamDayIndex} /></Field>
                  <Field label="时间"><Input aria-label="考试时间" type="time" value={examTime} onChange={(event) => setExamTime(event.target.value)} className="h-11 rounded-xl" /></Field>
                  <div className="sm:col-span-2"><Field label="考试名称"><Input aria-label="考试名称" value={examTitle} onChange={(event) => setExamTitle(event.target.value)} placeholder="例如 AP Physics · Unit Quiz" className="h-11 rounded-xl" maxLength={800} /></Field></div>
                  <div className="sm:col-span-2"><Field label="地点"><Input aria-label="考试地点" value={examLocation} onChange={(event) => setExamLocation(event.target.value)} placeholder="例如 Room 402" className="h-11 rounded-xl" maxLength={800} /></Field></div>
                  <div className="sm:col-span-2"><Field label="备注"><Textarea aria-label="考试备注" value={examNote} onChange={(event) => setExamNote(event.target.value)} placeholder="范围、需要携带的物品等" className="min-h-24 rounded-xl" maxLength={800} /></Field></div>
                </div>
                <SaveButton saving={saving} disabled={loading || !examTitle.trim()} label="保存考试安排" />
              </form>
              <AdminList title="本周考试" count={data?.exams.length ?? 0} loading={loading} error={error}>{(data?.exams ?? []).map((exam) => <button key={exam.id} type="button" onClick={() => editExam(exam)} className="admin-list-item"><span><strong>{exam.title}</strong><small>{exam.location || "未填写地点"}</small></span><b>{days[exam.dayIndex]} · {exam.time}</b></button>)}</AdminList>
            </div>
          </TabsContent>
        </Tabs>
      </section>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <div className="grid gap-2"><Label className="text-xs font-extrabold tracking-[.08em] text-[var(--muted-foreground)]">{label}</Label>{children}</div>; }
function DaySelect({ value, onChange }: { value: number; onChange: (value: number) => void }) { return <Select value={String(value)} onValueChange={(next) => onChange(Number(next))}><SelectTrigger aria-label="日期" className="h-11 w-full rounded-xl"><SelectValue /></SelectTrigger><SelectContent>{days.map((day, index) => <SelectItem key={day} value={String(index)}>{day}</SelectItem>)}</SelectContent></Select>; }
function SaveButton({ saving, disabled, label }: { saving: boolean; disabled: boolean; label: string }) { return <Button type="submit" disabled={saving || disabled} className="mt-6 h-12 w-full rounded-full bg-[var(--blue-600)] text-white hover:bg-[var(--blue-700)]"><Save /> {saving ? "正在保存…" : label}</Button>; }
function AdminCardHeader({ title, published }: { title: string; published: boolean }) { return <div className="mb-6 flex items-center justify-between gap-4 border-b border-[var(--border)] pb-5"><div><p className="text-xs font-black tracking-[.14em] text-[var(--blue-600)]">ENTRY</p><h2 className="mt-1 text-2xl font-bold tracking-tight">{title}</h2></div>{published && <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-700"><CheckCircle2 className="size-3.5" /> 已发布</span>}</div>; }
function AdminList({ title, count, loading, error, headerAction = null, children }: { title: string; count: number; loading: boolean; error: string; headerAction?: React.ReactNode; children: React.ReactNode }) { return <aside className="admin-list"><div className="admin-list-header"><div><p>THIS WEEK</p><h2>{title}</h2></div><div className="flex items-center gap-3">{headerAction}<span>{count}</span></div></div>{error ? <p className="p-4 text-sm text-red-600">{error}</p> : loading ? <p className="p-8 text-center text-sm text-[var(--muted-foreground)]">正在读取…</p> : <div className="admin-list-scroll">{children}</div>}</aside>; }
