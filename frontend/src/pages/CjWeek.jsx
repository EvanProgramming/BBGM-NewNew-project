import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import CjPortalBadge from "../components/CjPortalBadge";
import CjSchedulePicker from "../components/CjSchedulePicker";
import CjStudentActions from "../components/CjStudentActions";
import CjDateNavigation from "../components/CjDateNavigation";
import {
  PERIOD_COUNT,
  SCHEDULE_KEY,
  SCHEDULE_PROFILE_KEY,
  WEEKDAY_SHORT,
  dateForDay,
  dateFromIso,
  defaultSchedule,
  isoDate,
  mondayIso,
  normalizeSchedule,
  periodTimeLabel,
} from "../cjDates";
import { useLiveRefresh } from "../live";
import { isExamComplete, useHomeworkProgress } from "../cjProgress";
import { colorTint, courseColor, DEFAULT_CJ_COLOR, FIXED_PERIODS } from "../cjColors";

function readSchedule(subjects) {
  const profile = window.localStorage.getItem(SCHEDULE_PROFILE_KEY) || "custom";
  let saved;
  try { saved = JSON.parse(window.localStorage.getItem(SCHEDULE_KEY) || "null"); } catch { saved = null; }
  return { profile, schedule: normalizeSchedule(saved || defaultSchedule(subjects, profile), subjects, profile) };
}

export default function CjWeek({ portal = "student" }) {
  const [params, setParams] = useSearchParams();
  const start = /^\d{4}-\d{2}-\d{2}$/.test(params.get("start") || "") ? params.get("start") : mondayIso();
  const weekStart = useMemo(() => dateFromIso(start), [start]);
  const [data, setData] = useState(null);
  const [selection, setSelection] = useState([]);
  const [draftSelection, setDraftSelection] = useState([]);
  const [profile, setProfile] = useState("custom");
  const [draftProfile, setDraftProfile] = useState("custom");
  const [coursesOpen, setCoursesOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const homeworkProgress = useHomeworkProgress();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.readCj(isoDate(weekStart));
      setData(payload);
      const saved = readSchedule(payload.subjects);
      setSelection(saved.schedule);
      setDraftSelection(saved.schedule);
      setProfile(saved.profile);
      setDraftProfile(saved.profile);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load CJ.");
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  const refreshWeek = useCallback(async () => {
    const payload = await api.readCj(isoDate(weekStart));
    setData(payload);
  }, [weekStart]);

  useEffect(() => { load(); }, [load]);
  useLiveRefresh(Boolean(data) && !coursesOpen, refreshWeek);

  const subjectMap = useMemo(() => new Map((data?.subjects || []).map((subject) => [subject.id, subject])), [data]);
  const rows = useMemo(() => Array.from({ length: PERIOD_COUNT }, (_, index) => ({
    period: index + 1,
    subject: subjectMap.get(selection[index]) || null,
  })), [selection, subjectMap]);

  function moveWeek(offset) {
    const next = new Date(weekStart);
    next.setDate(next.getDate() + offset * 7);
    setParams({ start: isoDate(next) });
  }

  function saveCourses(next, nextProfile) {
    setSelection(next);
    setDraftSelection(next);
    setProfile(nextProfile);
    setDraftProfile(nextProfile);
    window.localStorage.setItem(SCHEDULE_KEY, JSON.stringify(next));
    window.localStorage.setItem(SCHEDULE_PROFILE_KEY, nextProfile);
    setCoursesOpen(false);
  }

  const weekEnd = dateForDay(weekStart, 4);
  const homework = (data?.entries || []).filter((entry) => entry.hw && selection.includes(entry.subject_id));

  const dayWeights = useMemo(() => {
    const totals = Array(5).fill(0);
    for (const { subject } of rows) {
      if (!subject) continue;
      for (let dayIndex = 0; dayIndex < 5; dayIndex += 1) {
        const entry = (data?.entries || []).find(
          (item) => item.day_index === dayIndex && item.subject_id === subject.id,
        );
        totals[dayIndex] +=
          (subject.short_name || "").length +
          (entry?.ic || "").length +
          (entry?.hw || "").length +
          (entry?.announcement || "").length;
      }
    }
    const sum = totals.reduce((total, value) => total + value, 0);
    if (!sum) return [1, 1, 1, 1, 1];
    const average = sum / 5;
    return totals.map((total) => Math.max(0.8, Math.min(1.5, total / average)));
  }, [data, rows]);

  const weekGridStyle = {
    gridTemplateColumns: `66px ${dayWeights
      .map((weight) => `minmax(168px, ${weight.toFixed(2)}fr)`)
      .join(" ")}`,
  };

  return (
    <section className="mt-5">
      <CjPortalBadge portal={portal} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <CjDateNavigation
          date={weekStart}
          weekEnd={weekEnd}
          mode="week"
          eyebrow={`Weekly CJ · ${profile === "custom" ? "Manual" : profile}`}
          onPrevious={() => moveWeek(-1)}
          onNext={() => moveWeek(1)}
        />
        <CjStudentActions
          onToday={() => setParams({ start: mondayIso() })}
          onRefresh={load}
          onCourses={() => setCoursesOpen((open) => !open)}
          coursesOpen={coursesOpen}
          coursesDisabled={!data}
        />
      </div>

      {coursesOpen ? (
        <CjSchedulePicker
          subjects={data?.subjects || []}
          profile={draftProfile}
          selection={draftSelection}
          onProfileChange={setDraftProfile}
          onSelectionChange={setDraftSelection}
          onSave={saveCourses}
        />
      ) : null}

      {error ? <p className="mt-4 border border-red-700 p-3 font-sans text-sm text-red-700">{error}</p> : null}

      <div className="mt-4 overflow-x-auto border border-black bg-neutral-200">
        <div className="grid min-w-[920px] gap-px" style={weekGridStyle}>
          <div className="bg-white" />
          {WEEKDAY_SHORT.map((day, index) => {
            const date = dateForDay(weekStart, index);
            return (
              <Link key={day} to={`/cj/student/day?date=${isoDate(date)}`} className="bg-white px-2 py-2 text-center text-inherit no-underline hover:bg-[#edf3ff]">
                <span className="block font-sans text-xs font-semibold">{day}</span>
                <span className="font-sans text-[10px] text-neutral-500">{date.getMonth() + 1}/{date.getDate()}</span>
              </Link>
            );
          })}

          {rows.map(({ period, subject }) => (
            <WeekRow key={period} period={period} subject={subject} entries={data?.entries || []} weekStart={weekStart} loading={loading} />
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <HighlightList icon="✓" title="Homework" empty="No homework posted this week." groupByDay items={homework.map((entry) => ({
          id: entry.id,
          dayIndex: entry.day_index,
          meta: subjectMap.get(entry.subject_id)?.short_name || entry.subject_id,
          text: entry.hw,
          completed: homeworkProgress.isComplete(entry),
          checkable: true,
          onToggle: () => homeworkProgress.toggle(entry),
          color: courseColor(subjectMap.get(entry.subject_id), entry.period),
          useCourseColor: !FIXED_PERIODS.has(entry.period),
        }))} />
        <HighlightList icon="!" title="Exams" empty="No exams posted this week." items={(data?.exams || []).map((exam) => ({
          id: exam.id,
          meta: `${WEEKDAY_SHORT[exam.day_index]} ${exam.time} · ${subjectMap.get(exam.subject_id)?.short_name || exam.subject_id}`,
          text: exam.title,
          note: exam.note,
          completed: isExamComplete(exam, weekStart),
        }))} />
      </div>
    </section>
  );
}

function WeekRow({ period, subject, entries, weekStart, loading }) {
  const accent = courseColor(subject, period);
  const useCourseColor = Boolean(subject) && !FIXED_PERIODS.has(period);
  return (
    <>
      <div className="flex min-h-12 flex-col items-center justify-center bg-white px-1 py-1 font-sans">
        <b className="text-xs">P{period}</b>
        <span className="mt-0.5 text-[8px] text-neutral-500">{periodTimeLabel(period)}</span>
      </div>
      {WEEKDAY_SHORT.map((day, dayIndex) => {
        const date = dateForDay(weekStart, dayIndex);
        const entry = subject ? entries.find((item) => item.day_index === dayIndex && item.subject_id === subject.id) : null;
        if (loading) return <div key={day} className="min-h-12 animate-pulse bg-white" />;
        if (!subject) return <div key={day} className="min-h-12 bg-neutral-50" />;
        const query = new URLSearchParams({ date: isoDate(date), period: String(period), subject: subject.id });
        return (
          <Link
            key={day}
            to={`/cj/student/course?${query}`}
            className="min-h-12 bg-white px-2 py-1.5 text-inherit no-underline"
            style={useCourseColor ? { backgroundColor: colorTint(accent), boxShadow: `inset 0 3px 0 ${accent}` } : undefined}
          >
            <p className="font-sans text-[11px] font-semibold leading-4 [overflow-wrap:anywhere]">{subject.short_name}</p>
            {entry?.ic ? <p className="font-sans text-[9px] leading-3.5 text-neutral-600 [overflow-wrap:anywhere]"><b style={{ color: accent }}>IC</b> {entry.ic}</p> : null}
            {entry?.hw ? <p className="font-sans text-[9px] leading-3.5 text-neutral-600 [overflow-wrap:anywhere]"><b style={{ color: accent }}>HW</b> {entry.hw}</p> : null}
            {entry?.announcement ? <p className="font-sans text-[9px] leading-3.5 text-neutral-600 [overflow-wrap:anywhere]"><b style={{ color: accent }}>A</b> {entry.announcement}</p> : null}
          </Link>
        );
      })}
    </>
  );
}

function HighlightList({ icon, title, empty, items, groupByDay = false }) {
  if (groupByDay) {
    const dayColumns = WEEKDAY_SHORT.map((_, dayIndex) => items.filter((item) => item.dayIndex === dayIndex));
    const rowCount = Math.max(...dayColumns.map((column) => column.length), 0);
    return (
      <section className="border border-black bg-white p-3">
        <h2 className="flex items-center gap-2 font-sans text-sm font-semibold"><span className="flex h-6 w-6 items-center justify-center bg-[#1A4FBF] text-white">{icon}</span>{title}</h2>
        {items.length ? (
          <div className="mt-2 grid grid-cols-5 gap-x-1.5 gap-y-1.5">
            {WEEKDAY_SHORT.map((day) => (
              <p key={day} className="border-b border-neutral-300 pb-1 text-center font-sans text-[9px] font-semibold uppercase tracking-[0.12em] text-neutral-500">{day}</p>
            ))}
            {Array.from({ length: rowCount }, (_, rowIndex) => (
              dayColumns.map((column, dayIndex) => {
                const item = column[rowIndex];
                return item
                  ? <HomeworkCard key={item.id} item={item} />
                  : <div key={`${dayIndex}-${rowIndex}`} aria-hidden="true" className="min-h-14" />;
              })
            ))}
          </div>
        ) : <p className="mt-2 font-sans text-xs text-neutral-500">{empty}</p>}
      </section>
    );
  }

  return (
    <section className="border border-black bg-white p-3">
      <h2 className="flex items-center gap-2 font-sans text-sm font-semibold"><span className="flex h-6 w-6 items-center justify-center bg-[#1A4FBF] text-white">{icon}</span>{title}</h2>
      {items.length ? (
        <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
          {items.map((item) => (
            <article
              key={item.id}
              className={`border-l-2 bg-[#f6f8fd] px-2 py-1.5 ${item.completed ? "opacity-55" : ""}`}
              style={item.useCourseColor ? { borderColor: item.color, backgroundColor: colorTint(item.color) } : { borderColor: DEFAULT_CJ_COLOR }}
            >
              <div className="flex gap-2">
                {item.checkable ? (
                  <input
                    type="checkbox"
                    checked={item.completed}
                    onChange={item.onToggle}
                    aria-label={`Mark ${item.text} complete`}
                    className="mt-0.5 h-4 w-4 shrink-0"
                    style={{ accentColor: item.useCourseColor ? item.color : DEFAULT_CJ_COLOR }}
                  />
                ) : item.completed ? <span aria-label="Completed" className="text-[#1A4FBF]">✓</span> : null}
                <div className="min-w-0">
                  <p className={`font-sans text-[9px] uppercase tracking-[0.1em] ${item.completed ? "line-through" : ""}`} style={{ color: item.useCourseColor ? item.color : DEFAULT_CJ_COLOR }}>{item.meta}</p>
                  <p className={`truncate font-sans text-xs ${item.completed ? "line-through" : ""}`}>{item.text}</p>
                  {item.note ? <p className={`mt-0.5 truncate font-sans text-[10px] text-neutral-500 ${item.completed ? "line-through" : ""}`}>{item.note}</p> : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : <p className="mt-2 font-sans text-xs text-neutral-500">{empty}</p>}
    </section>
  );
}

function HomeworkCard({ item }) {
  return (
    <label
      className={`flex min-h-14 cursor-pointer gap-1.5 border-l-2 bg-[#f6f8fd] px-1.5 py-1.5 ${item.completed ? "opacity-55" : ""}`}
      style={item.useCourseColor ? { borderColor: item.color, backgroundColor: colorTint(item.color) } : { borderColor: DEFAULT_CJ_COLOR }}
    >
      <input
        type="checkbox"
        checked={item.completed}
        onChange={item.onToggle}
        aria-label={`Mark ${item.text} complete`}
        className="mt-0.5 h-3.5 w-3.5 shrink-0"
        style={{ accentColor: item.useCourseColor ? item.color : DEFAULT_CJ_COLOR }}
      />
      <span className="min-w-0">
        <span className={`block truncate font-sans text-[8px] uppercase tracking-[0.08em] ${item.completed ? "line-through" : ""}`} style={{ color: item.useCourseColor ? item.color : DEFAULT_CJ_COLOR }}>{item.meta}</span>
        <span className={`block font-sans text-[10px] leading-3.5 ${item.completed ? "line-through" : ""}`}>{item.text}</span>
      </span>
    </label>
  );
}
