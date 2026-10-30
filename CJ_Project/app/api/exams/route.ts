import { NextResponse } from "next/server";
import { getD1 } from "@/db";
import { getChatGPTUser } from "@/app/chatgpt-auth";
import { adminGate } from "@/lib/admin-auth";

export const dynamic = "force-dynamic";

export async function PUT(request: Request) {
  try {
    const gate = adminGate(request, await getChatGPTUser());
    if (!gate.ok) {
      return NextResponse.json({ error: gate.message }, { status: gate.status });
    }
    const input = (await request.json()) as Record<string, unknown>;
    const id = String(input.id ?? "") || crypto.randomUUID();
    const weekStart = String(input.weekStart ?? "");
    const dayIndex = Number(input.dayIndex);
    const title = String(input.title ?? "").trim();
    const time = String(input.time ?? "").trim();
    const location = String(input.location ?? "").trim();
    const note = String(input.note ?? "").trim();
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(weekStart) ||
      !Number.isInteger(dayIndex) || dayIndex < 0 || dayIndex > 4 ||
      !title || !/^\d{2}:\d{2}$/.test(time) ||
      [title, location, note].some((value) => value.length > 800)
    ) {
      return NextResponse.json({ error: "请检查考试日期、时间与内容" }, { status: 400 });
    }
    const updatedAt = new Date().toISOString();
    await getD1()
      .prepare(
        `INSERT INTO exams (id, week_start, day_index, title, time, location, note, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(id) DO UPDATE SET week_start = excluded.week_start,
           day_index = excluded.day_index, title = excluded.title, time = excluded.time,
           location = excluded.location, note = excluded.note, updated_at = excluded.updated_at`,
      )
      .bind(id, weekStart, dayIndex, title, time, location, note, updatedAt)
      .run();
    return NextResponse.json({ ok: true, id, updatedAt });
  } catch (error) {
    console.error("Failed to save exam", error);
    return NextResponse.json({ error: "考试安排保存失败" }, { status: 500 });
  }
}
