import { NextResponse } from "next/server";
import { getD1 } from "@/db";
import { getChatGPTUser } from "@/app/chatgpt-auth";
import { adminGate } from "@/lib/admin-auth";

export const dynamic = "force-dynamic";

const subjects = [
  ["ap-calculus", "AP Calculus AB", "AP Cal AB", "#2563eb", 1, 1],
  ["biology", "Biology", "Biology", "#0891b2", 1, 2],
  ["ap-physics", "AP Physics 1", "AP Physics", "#3b82f6", 2, 3],
  ["chinese", "Chinese", "Chinese", "#6366f1", 3, 4],
  ["ap-language", "AP English Language", "AP Lang", "#1d4ed8", 4, 5],
  ["world-history", "World History", "History", "#0e7490", 4, 6],
  ["ap-economics", "AP Economics", "AP Eco", "#0284c7", 5, 7],
  ["ap-csa", "AP Computer Science A", "AP CSA", "#4f46e5", 7, 8],
] as const;

const sampleEntries = [
  [0, 1, "ap-calculus", "Limits and continuity review", "Complete FRQ Set 2 · Q1–4", "Quiz on Wednesday"],
  [0, 1, "biology", "Cellular respiration overview", "Complete lab analysis questions 1–5", "Bring safety goggles Wednesday"],
  [0, 2, "ap-physics", "Newton’s 3rd Law", "ES 7 · Q3, 5, 38, 46", "Lab groups posted"],
  [0, 4, "ap-language", "Rhetorical situation & audience", "Annotate ‘The Gettysburg Address’", "Bring the blue reader"],
  [0, 5, "ap-economics", "Demand shifts and market equilibrium", "Module 3.2 practice", "Unit 2 exam Friday"],
  [0, 7, "ap-csa", "String methods and immutability", "CodingBat String-1 · 1–8", "Office hour 16:20"],
  [1, 1, "ap-calculus", "Implicit differentiation", "RB 3.2 · #7–12", ""],
  [1, 1, "biology", "Aerobic and anaerobic respiration", "Read 6.3 and complete notes", ""],
  [1, 2, "ap-physics", "Free-body diagrams", "Finish cart lab analysis", "Lab report due Thursday"],
  [1, 4, "ap-language", "Claims, evidence, commentary", "Draft body paragraph", "Peer review next class"],
  [1, 5, "ap-economics", "Price elasticity of demand", "3.3 guided notes", "Bring calculator"],
  [1, 7, "ap-csa", "Nested loops", "Program: pattern printer", "Check rubric before upload"],
  [2, 1, "ap-calculus", "Related rates", "Worksheet · #1–6", "Quiz today"],
  [2, 1, "biology", "Mitosis and the cell cycle", "Cell cycle diagram", "Lab next class"],
  [2, 2, "ap-physics", "Friction and inclined planes", "ES 8 · odd questions", ""],
  [2, 4, "ap-language", "Synthesis source evaluation", "Read sources A–D", "Timed write Friday"],
  [2, 5, "ap-economics", "Tax incidence", "Graph 4 market scenarios", "Unit 2 review opens"],
  [2, 7, "ap-csa", "ArrayList traversal", "Lab checkpoint 1", "Commit before 20:00"],
  [3, 1, "ap-calculus", "Linearization", "Textbook 4.1 · #9–21 odd", ""],
  [3, 1, "biology", "DNA replication", "Complete replication worksheet", ""],
  [3, 2, "ap-physics", "Circular motion introduction", "Lab report final draft", "Lab report due 22:00"],
  [3, 4, "ap-language", "Counterargument workshop", "Revise thesis + outline", "Conference sign-up"],
  [3, 5, "ap-economics", "Government intervention", "Unit 2 review sheet", "Exam tomorrow"],
  [3, 7, "ap-csa", "2D arrays", "GridWalker methods", ""],
  [4, 1, "ap-calculus", "Optimization", "Weekend mixed practice", "Corrections due Monday"],
  [4, 1, "biology", "Protein synthesis", "Transcription practice", ""],
  [4, 2, "ap-physics", "Centripetal force", "Read 6.2 + notes", ""],
  [4, 4, "ap-language", "Timed synthesis essay", "Reflection form", "Submit by 18:00"],
  [4, 5, "ap-economics", "Unit 2 assessment", "No HW", "Assessment in class"],
  [4, 7, "ap-csa", "2D array algorithms", "Finish GridWalker", "Demo next Monday"],
] as const;

const sampleExams = [
  [2, "AP Calculus AB · Unit Quiz", "10:05", "Room 402", "Related rates and implicit differentiation"],
  [4, "AP Economics · Unit 2 Exam", "13:35", "Room 305", "Bring a calculator"],
] as const;

async function ensureSeed(weekStart: string) {
  const db = getD1();
  await db.batch(
    subjects.map((subject) =>
      db
        .prepare(
          `INSERT INTO subjects (id, name, short_name, color, period, sort_order)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET name = excluded.name, short_name = excluded.short_name,
             color = excluded.color, period = excluded.period, sort_order = excluded.sort_order`,
        )
        .bind(...subject),
    ),
  );

  const total = await db.prepare("SELECT COUNT(*) AS count FROM cj_entries").first<{ count: number }>();
  if (Number(total?.count ?? 0) === 0) {
    const now = new Date().toISOString();
    await db.batch(
      sampleEntries.map((entry, index) =>
        db
          .prepare(
            `INSERT OR IGNORE INTO cj_entries
             (id, week_start, day_index, period, subject_id, ic, hw, announcement, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .bind(`sample-${index + 1}`, weekStart, ...entry, now),
      ),
    );
  }

  const biologyEntries = sampleEntries.filter((entry) => entry[2] === "biology");
  await db.batch(
    biologyEntries.map((entry) =>
      db
        .prepare(
          `INSERT OR IGNORE INTO cj_entries
           (id, week_start, day_index, period, subject_id, ic, hw, announcement, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        )
        .bind(`biology-v2-${entry[0]}`, weekStart, ...entry, new Date().toISOString()),
    ),
  );

  const examTotal = await db.prepare("SELECT COUNT(*) AS count FROM exams").first<{ count: number }>();
  if (Number(examTotal?.count ?? 0) === 0) {
    const now = new Date().toISOString();
    await db.batch(
      sampleExams.map((exam, index) =>
        db
          .prepare(
            `INSERT INTO exams
             (id, week_start, day_index, title, time, location, note, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
          )
          .bind(`exam-sample-${index + 1}`, weekStart, ...exam, now),
      ),
    );
  }
}

export async function GET(request: Request) {
  try {
    const weekStart = new URL(request.url).searchParams.get("weekStart") ?? "";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(weekStart)) {
      return NextResponse.json({ error: "weekStart 格式无效" }, { status: 400 });
    }
    const db = getD1();
    const [subjectResult, entryResult, examResult] = await db.batch([
      db.prepare(
        `SELECT id, name, short_name AS shortName, color
         FROM subjects
         WHERE id NOT IN ('period-6', 'period-8')
         ORDER BY sort_order, name`,
      ),
      db
        .prepare(
          `SELECT id, week_start AS weekStart, day_index AS dayIndex, period,
                  subject_id AS subjectId, ic, hw, announcement, updated_at AS updatedAt
           FROM cj_entries WHERE week_start = ? ORDER BY day_index, period`,
        )
        .bind(weekStart),
      db
        .prepare(
          `SELECT id, week_start AS weekStart, day_index AS dayIndex, title, time,
                  location, note, updated_at AS updatedAt
           FROM exams WHERE week_start = ? ORDER BY day_index, time`,
        )
        .bind(weekStart),
    ]);
    return NextResponse.json({
      weekStart,
      subjects: subjectResult.results,
      entries: entryResult.results,
      exams: examResult.results,
    });
  } catch (error) {
    console.error("Failed to load CJ", error);
    return NextResponse.json({ error: "CJ 数据暂时不可用" }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const gate = adminGate(request, await getChatGPTUser());
    if (!gate.ok) {
      return NextResponse.json({ error: gate.message }, { status: gate.status });
    }
    const input = (await request.json()) as Record<string, unknown>;
    const weekStart = String(input.weekStart ?? "");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(weekStart)) {
      return NextResponse.json({ error: "weekStart 格式无效" }, { status: 400 });
    }
    await ensureSeed(weekStart);
    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Failed to seed CJ", error);
    return NextResponse.json({ error: "初始化失败，请稍后重试" }, { status: 500 });
  }
}

export async function PUT(request: Request) {
  try {
    const gate = adminGate(request, await getChatGPTUser());
    if (!gate.ok) {
      return NextResponse.json({ error: gate.message }, { status: gate.status });
    }
    const input = (await request.json()) as Record<string, unknown>;
    const weekStart = String(input.weekStart ?? "");
    const subjectId = String(input.subjectId ?? "");
    const dayIndex = Number(input.dayIndex);
    const ic = String(input.ic ?? "").trim();
    const hw = String(input.hw ?? "").trim();
    const announcement = String(input.announcement ?? "").trim();

    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(weekStart) ||
      !subjectId ||
      !Number.isInteger(dayIndex) ||
      dayIndex < 0 ||
      dayIndex > 4 ||
      [ic, hw, announcement].some((value) => value.length > 800)
    ) {
      return NextResponse.json({ error: "请检查日期、课程与内容" }, { status: 400 });
    }

    const db = getD1();
    const subject = await db
      .prepare("SELECT period FROM subjects WHERE id = ?")
      .bind(subjectId)
      .first<{ period: number }>();
    if (!subject) return NextResponse.json({ error: "Subject 不存在" }, { status: 404 });
    const period = Number(subject.period);
    const existing = await db
      .prepare(
        `SELECT id FROM cj_entries
         WHERE week_start = ? AND day_index = ? AND period = ? AND subject_id = ?`,
      )
      .bind(weekStart, dayIndex, period, subjectId)
      .first<{ id: string }>();
    const id = existing?.id ?? crypto.randomUUID();
    const updatedAt = new Date().toISOString();
    await db
      .prepare(
        `INSERT INTO cj_entries
         (id, week_start, day_index, period, subject_id, ic, hw, announcement, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(week_start, day_index, period, subject_id)
         DO UPDATE SET ic = excluded.ic, hw = excluded.hw,
                       announcement = excluded.announcement, updated_at = excluded.updated_at`,
      )
      .bind(id, weekStart, dayIndex, period, subjectId, ic, hw, announcement, updatedAt)
      .run();
    return NextResponse.json({ ok: true, id, updatedAt });
  } catch (error) {
    console.error("Failed to save CJ", error);
    return NextResponse.json({ error: "保存失败，请稍后重试" }, { status: 500 });
  }
}
