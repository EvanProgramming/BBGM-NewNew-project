import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import CjDateNavigation from "../components/CjDateNavigation";
import CjPortalBadge from "../components/CjPortalBadge";
import CjTooltip from "../components/CjTooltip";
import { dateFromIso, isoDate, mondayOf, periodTimeLabel } from "../cjDates";

const ISO = /^\d{4}-\d{2}-\d{2}$/;

export default function CjCourseDetail({ portal = "student", backPath = "/cj/student/day" }) {
  const [params] = useSearchParams();
  const dateValue = params.get("date") || isoDate(new Date());
  const safeDate = ISO.test(dateValue) ? dateValue : isoDate(new Date());
  const period = Math.min(11, Math.max(1, Number(params.get("period")) || 1));
  const subjectId = params.get("subject") || "";
  const date = useMemo(() => dateFromIso(safeDate), [safeDate]);
  const weekStart = useMemo(() => mondayOf(date), [date]);
  const dayIndex = Math.round((date.getTime() - weekStart.getTime()) / 86400000);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api.readCj(isoDate(weekStart))
      .then((payload) => { if (active) setData(payload); })
      .catch((loadError) => { if (active) setError(loadError instanceof Error ? loadError.message : "Could not load course details."); });
    return () => { active = false; };
  }, [weekStart]);

  const subject = data?.subjects?.find((item) => item.id === subjectId);
  const entry = data?.entries?.find((item) => item.day_index === dayIndex && item.subject_id === subjectId);
  const heading = date.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  return (
    <section className="mt-8">
      <CjPortalBadge portal={portal} />
      {portal === "student" ? (
        <CjDateNavigation date={date} mode="day" eyebrow="Course details" detail={heading} />
      ) : (
        <CjTooltip label="Back to daily CJ" align="left">
          <Link to={`${backPath}?date=${safeDate}`} aria-label="Back to daily CJ" className="inline-flex border border-black px-3 py-2 font-sans text-[10px] uppercase tracking-[0.14em] text-inherit no-underline">
            ← Back
          </Link>
        </CjTooltip>
      )}

      {error ? <p className="mt-6 border border-red-700 p-4 font-sans text-sm text-red-700">{error}</p> : null}
      {!data && !error ? <p className="mt-6 font-sans text-sm text-neutral-500">Loading course details…</p> : null}
      {data && !subject ? <p className="mt-6 border border-black p-4 font-sans text-sm">This course is no longer in your timetable.</p> : null}

      {subject ? (
        <>
          <header className="mt-6 border-y-2 border-black py-5">
            <p className="font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]">IC · HW · A · {heading}</p>
            <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
              <div>
                <h1 className="font-serif text-4xl">{subject.name}</h1>
                <p className="mt-2 font-sans text-sm text-neutral-600">Grade {subject.grade} · {subject.class_section === "All" ? "All Grade 11 classes" : `Class ${subject.class_section}`}</p>
              </div>
              <div className="bg-black px-4 py-3 text-white">
                <p className="font-sans text-[10px] uppercase tracking-[0.14em]">Period {period}</p>
                <p className="mt-1 font-sans text-lg font-semibold">{periodTimeLabel(period)}</p>
              </div>
            </div>
          </header>

          <section className="mt-5 grid gap-px border border-black bg-black sm:grid-cols-3">
            <CourseMeta label="Teacher" value={subject.teacher} />
            <CourseMeta label="Location" value={subject.room} />
            <CourseMeta label="Course type" value={subject.required ? "Required" : "Elective / configurable"} />
          </section>

          <section className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-stretch">
            <DetailPanel label="IC" title="In-class content" value={entry?.ic} />
            <DetailPanel label="HW" title="Homework" value={entry?.hw} />
            <DetailPanel label="A" title="Announcement" value={entry?.announcement} />
          </section>
        </>
      ) : null}
    </section>
  );
}

function CourseMeta({ label, value }) {
  return (
    <div className="bg-white p-4">
      <p className="font-sans text-[10px] uppercase tracking-[0.16em] text-[#1A4FBF]">{label}</p>
      <p className="mt-2 font-sans text-base font-semibold">{value || "To be confirmed"}</p>
    </div>
  );
}

function textWeight(value) {
  return Math.max(1, Math.min(6, Math.ceil((value || "").length / 40)));
}

function DetailPanel({ label, title, value }) {
  return (
    <article
      className="min-h-[220px] min-w-0 border-2 border-black p-5 lg:min-w-[15rem] lg:flex-1"
      style={{ flexBasis: 0, flexGrow: textWeight(value) }}
    >
      <span className="inline-block bg-[#1A4FBF] px-2 py-1 font-sans text-[11px] font-semibold text-white">{label}</span>
      <h2 className="mt-4 font-serif text-2xl">{title}</h2>
      <p className={`mt-4 whitespace-pre-wrap font-sans text-lg leading-7 [overflow-wrap:anywhere] ${value ? "text-neutral-900" : "text-neutral-400"}`}>
        {value || "No information has been posted yet."}
      </p>
    </article>
  );
}
