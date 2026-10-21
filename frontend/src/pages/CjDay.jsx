import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import CjPortalBadge from "../components/CjPortalBadge";
import CjSchedulePicker from "../components/CjSchedulePicker";
import CjStudentActions from "../components/CjStudentActions";
import CjDateNavigation from "../components/CjDateNavigation";
import CjTooltip from "../components/CjTooltip";
import {
  PERIOD_COUNT,
  SCHEDULE_KEY,
  SCHEDULE_PROFILE_KEY,
  WEEKDAY_SHORT,
  dateFromIso,
  defaultSchedule,
  isoDate,
  mondayOf,
  nextSchoolDay,
  normalizeSchedule,
  periodTimeLabel,
  previousSchoolDay,
} from "../cjDates";
import { useLiveRefresh } from "../live";
import { isExamComplete, useHomeworkProgress } from "../cjProgress";
import { colorTint, courseColor, DEFAULT_CJ_COLOR, FIXED_PERIODS } from "../cjColors";

const ISO = /^\d{4}-\d{2}-\d{2}$/;

export function CjWeekRedirect() {
  const [params] = useSearchParams();
  const start = params.get("start") || "";
  const date = ISO.test(start) ? start : isoDate(new Date());
  return <Navigate to={`/cj/student/day?date=${date}`} replace />;
}

function readSavedSchedule(subjects) {
  const profile = window.localStorage.getItem(SCHEDULE_PROFILE_KEY) || "custom";
  let saved = null;
  try {
    saved = JSON.parse(window.localStorage.getItem(SCHEDULE_KEY) || "null");
  } catch {
    saved = null;
  }
  return { profile, schedule: normalizeSchedule(saved || defaultSchedule(subjects, profile), subjects, profile) };
}

export default function CjDay({
  portal = "student",
  detailPath = "/cj/student/course",
}) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("date") || "";
  const date = useMemo(() => (ISO.test(raw) ? dateFromIso(raw) : dateFromIso(isoDate(new Date()))), [raw]);
  const weekStart = useMemo(() => mondayOf(date), [date]);
  const dayIndex = Math.round((date.getTime() - weekStart.getTime()) / 86400000);
  const schoolDay = dayIndex >= 0 && dayIndex <= 4;

  const [data, setData] = useState(null);
  const [selected, setSelected] = useState([]);
  const [draftSelection, setDraftSelection] = useState([]);
  const [profile, setProfile] = useState("custom");
  const [draftProfile, setDraftProfile] = useState("custom");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const homeworkProgress = useHomeworkProgress();

  const loadDay = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.readCj(isoDate(weekStart));
      setData(payload);
      const saved = readSavedSchedule(payload.subjects);
      setProfile(saved.profile);
      setDraftProfile(saved.profile);
      setSelected(saved.schedule);
      setDraftSelection(saved.schedule);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Could not load CJ.");
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  useEffect(() => { loadDay(); }, [loadDay]);

  const refreshDay = useCallback(async () => {
    const payload = await api.readCj(isoDate(weekStart));
    setData(payload);
  }, [weekStart]);
  useLiveRefresh(Boolean(data) && !pickerOpen, refreshDay);

  const subjectMap = useMemo(
    () => new Map((data?.subjects || []).map((subject) => [subject.id, subject])),
    [data],
  );
  const periods = useMemo(
    () => Array.from({ length: PERIOD_COUNT }, (_, index) => ({
      period: index + 1,
      subject: subjectMap.get(selected[index]) || null,
    })),
    [selected, subjectMap],
  );
  const exams = (data?.exams || []).filter((exam) => exam.day_index === dayIndex);
  const homework = (data?.entries || []).filter(
    (entry) => entry.day_index === dayIndex && entry.hw && selected.includes(entry.subject_id),
  );

  function saveSelection(next, nextProfile) {
    setSelected(next);
    setDraftSelection(next);
    setProfile(nextProfile);
    setDraftProfile(nextProfile);
    window.localStorage.setItem(SCHEDULE_KEY, JSON.stringify(next));
    window.localStorage.setItem(SCHEDULE_PROFILE_KEY, nextProfile);
    setPickerOpen(false);
  }

  function moveDay(nextDate) {
    setParams({ date: isoDate(nextDate) });
  }

  const heading = date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const selectedCount = periods.filter((item) => item.subject).length;

  return (
    <section className="mt-8">
      <CjPortalBadge portal={portal} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        {portal === "student" ? (
          <CjDateNavigation
            date={date}
            mode="day"
            eyebrow={`Daily CJ · ${profile === "custom" ? "Manual" : profile}`}
            detail={`${selectedCount} courses · 11 periods`}
            onPrevious={() => moveDay(previousSchoolDay(date))}
            onNext={() => moveDay(nextSchoolDay(date))}
          />
        ) : (
          <div className="flex items-center gap-2">
          <CjTooltip label="Previous school day" align="left">
            <button type="button" aria-label="Previous school day" onClick={() => moveDay(previousSchoolDay(date))} className="h-9 w-9 border border-black text-lg">‹</button>
          </CjTooltip>
          <div>
          <p className="font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]">
            Daily CJ · {profile === "custom" ? "Manual" : profile}
          </p>
          <h1 className="mt-1 font-sans text-2xl font-semibold">{heading}</h1>
          <p className="mt-1 font-sans text-xs text-neutral-500">{selectedCount} courses · 11 periods</p>
          </div>
          <CjTooltip label="Next school day" align="left">
            <button type="button" aria-label="Next school day" onClick={() => moveDay(nextSchoolDay(date))} className="h-9 w-9 border border-black text-lg">›</button>
          </CjTooltip>
          </div>
        )}
        <CjStudentActions
          onToday={() => setParams({ date: isoDate(new Date()) })}
          onRefresh={loadDay}
          onCourses={() => setPickerOpen((open) => !open)}
          coursesOpen={pickerOpen}
          coursesDisabled={!data}
        />
      </div>

      {pickerOpen ? (
        <CjSchedulePicker
          subjects={data?.subjects || []}
          profile={draftProfile}
          selection={draftSelection}
          onProfileChange={setDraftProfile}
          onSelectionChange={setDraftSelection}
          onSave={saveSelection}
        />
      ) : null}

      {error ? (
        <div className="mt-6 border border-black p-4">
          <p className="font-sans text-sm">{error}</p>
          <button type="button" onClick={loadDay} className="mt-3 font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">Reload</button>
        </div>
      ) : schoolDay ? (
        <section className="mt-4 overflow-hidden border border-black bg-white">
          <header className="border-b border-black px-3 py-2">
            <p className="font-sans text-[10px] uppercase tracking-[0.16em] text-[#1A4FBF]">{WEEKDAY_SHORT[dayIndex]}</p>
            <div className="flex items-end justify-between gap-4">
              <h2 className="font-serif text-2xl">{heading}</h2>
              <span className="font-sans text-xs text-neutral-500">{isoDate(date)}</span>
            </div>
          </header>
          <div className="grid gap-px bg-neutral-200">
            {loading
              ? Array.from({ length: PERIOD_COUNT }, (_, index) => <div key={index} className="h-24 bg-white" />)
              : periods.map(({ period, subject }) => {
                  const entry = subject
                    ? (data?.entries || []).find((item) => item.day_index === dayIndex && item.subject_id === subject.id)
                    : null;
                  return (
                    <CourseRow
                      key={period}
                      period={period}
                      subject={subject}
                      entry={entry}
                      date={isoDate(date)}
                      detailPath={detailPath}
                    />
                  );
                })}
          </div>
        </section>
      ) : (
        <p className="mt-6 border border-neutral-200 p-4 font-sans text-sm text-neutral-500">This date is not a school day.</p>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <HomeworkList homework={homework} subjects={data?.subjects || []} loading={loading} progress={homeworkProgress} />
        <ExamList exams={exams} subjects={data?.subjects || []} loading={loading} weekStart={weekStart} />
      </div>
    </section>
  );
}

function CourseRow({ period, subject, entry, date, detailPath }) {
  const accent = courseColor(subject, period);
  const useCourseColor = Boolean(subject) && !FIXED_PERIODS.has(period);
  const content = (
    <article
      className="grid min-h-14 gap-2 bg-white px-3 py-2 transition-colors sm:grid-cols-[125px_1fr]"
      style={useCourseColor ? { backgroundColor: colorTint(accent), boxShadow: `inset 3px 0 0 ${accent}` } : undefined}
    >
      <div className="flex items-center gap-2 border-b border-neutral-200 pb-2 sm:border-b-0 sm:border-r sm:pb-0 sm:pr-3">
        <span className="inline-block bg-black px-2 py-1 font-sans text-[10px] text-white" style={useCourseColor ? { backgroundColor: accent } : undefined}>P{period}</span>
        <p className="font-sans text-[10px] text-neutral-600">{periodTimeLabel(period)}</p>
      </div>
      {subject ? (
        <div className="grid items-center gap-2 sm:grid-cols-[minmax(150px,0.8fr)_2fr]">
          <div className="min-w-0">
            <h3 className="truncate font-sans text-sm font-semibold">{subject.short_name}</h3>
            <p className="truncate font-sans text-[10px] text-neutral-500">{subject.teacher} · {subject.room}</p>
          </div>
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start">
            <Info label="IC" value={entry?.ic} color={accent} />
            <Info label="HW" value={entry?.hw} color={accent} />
            <Info label="A" value={entry?.announcement} color={accent} />
          </div>
        </div>
      ) : (
        <div className="flex items-center font-sans text-xs text-neutral-400">—</div>
      )}
    </article>
  );
  if (!subject) return content;
  const query = new URLSearchParams({ date, period: String(period), subject: subject.id });
  return <Link to={`${detailPath}?${query}`} className="block text-inherit no-underline">{content}</Link>;
}

function textWeight(value) {
  return Math.max(1, Math.min(6, Math.ceil((value || "").length / 20)));
}

function Info({ label, value, color }) {
  return (
    <div
      className="min-w-[6rem] flex-1"
      style={{ flexBasis: 0, flexGrow: textWeight(value) }}
    >
      <p className="font-sans text-[10px] uppercase tracking-[0.14em]" style={{ color }}>{label}</p>
      <p className="font-sans text-[11px] leading-4 [overflow-wrap:anywhere]">{value || "—"}</p>
    </div>
  );
}

function HomeworkList({ homework, subjects, loading, progress }) {
  const subjectMap = new Map(subjects.map((subject) => [subject.id, subject]));
  return (
    <section className="border border-black bg-white p-3">
      <h2 className="flex items-center gap-2 font-sans text-sm font-semibold"><span className="flex h-6 w-6 items-center justify-center bg-[#1A4FBF] text-white">✓</span>Today's homework</h2>
      {loading ? <p className="mt-2 font-sans text-xs text-neutral-500">Loading…</p> : homework.length ? (
        <div className="mt-2 grid gap-1.5">
          {homework.map((entry) => {
            const complete = progress.isComplete(entry);
            const subject = subjectMap.get(entry.subject_id);
            const accent = courseColor(subject, entry.period);
            const useCourseColor = !FIXED_PERIODS.has(entry.period);
            return (
              <label
                key={entry.id}
                className={`flex cursor-pointer gap-2 border-l-2 bg-[#f6f8fd] px-2 py-1.5 ${complete ? "opacity-55" : ""}`}
                style={useCourseColor ? { borderColor: accent, backgroundColor: colorTint(accent) } : { borderColor: DEFAULT_CJ_COLOR }}
              >
                <input type="checkbox" checked={complete} onChange={() => progress.toggle(entry)} className="mt-0.5 h-4 w-4" style={{ accentColor: useCourseColor ? accent : DEFAULT_CJ_COLOR }} />
                <span>
                  <span className={`block font-sans text-[9px] uppercase tracking-[0.1em] ${complete ? "line-through" : ""}`} style={{ color: useCourseColor ? accent : DEFAULT_CJ_COLOR }}>{subject?.short_name || entry.subject_id}</span>
                  <span className={`block font-sans text-xs ${complete ? "line-through" : ""}`}>{entry.hw}</span>
                </span>
              </label>
            );
          })}
        </div>
      ) : <p className="mt-2 font-sans text-xs text-neutral-500">No homework posted today.</p>}
    </section>
  );
}

function ExamList({ exams, subjects, loading, weekStart }) {
  const subjectMap = new Map(subjects.map((subject) => [subject.id, subject]));
  return (
    <section className="border border-black bg-white p-3">
      <h2 className="flex items-center gap-2 font-sans text-sm font-semibold"><span className="flex h-6 w-6 items-center justify-center bg-[#1A4FBF] text-white">!</span>Today's exams</h2>
      {loading ? (
        <p className="mt-3 font-sans text-sm text-neutral-500">Loading exams…</p>
      ) : exams.length ? (
        <div className="mt-2 grid gap-1.5">
          {exams.map((exam) => {
            const subject = subjectMap.get(exam.subject_id);
            const complete = isExamComplete(exam, weekStart);
            return (
              <article key={exam.id} className={`border-l-2 border-[#1A4FBF] bg-[#f6f8fd] px-2 py-1.5 ${complete ? "opacity-55" : ""}`}>
                <p className={`font-sans text-[11px] uppercase tracking-[0.14em] text-neutral-500 ${complete ? "line-through" : ""}`}>{complete ? "✓ " : ""}{exam.time}{exam.location ? ` · ${exam.location}` : ""}</p>
                <h3 className={`mt-1 font-sans text-sm font-semibold ${complete ? "line-through" : ""}`}>{subject ? `${subject.short_name} · ${exam.title}` : exam.title}</h3>
                {exam.note ? <p className={`mt-1 font-sans text-sm text-neutral-600 ${complete ? "line-through" : ""}`}>{exam.note}</p> : null}
              </article>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 font-sans text-sm text-neutral-500">No exams scheduled for this day.</p>
      )}
    </section>
  );
}
