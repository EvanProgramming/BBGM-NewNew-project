import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import CjPortalBadge from "../components/CjPortalBadge";
import { ButtonSpinner } from "../components/ui";
import { dateForDay, dateFromIso, isoDate, mondayIso } from "../cjDates";
import { useI18n } from "../i18n";

export default function CjAdmin({ portal = "admin" }) {
  const { t } = useI18n();
  const [weekStart, setWeekStart] = useState(mondayIso);
  const [syncStatus, setSyncStatus] = useState(null);
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("cj");
  const [dayIndex, setDayIndex] = useState(0);
  const [subjectId, setSubjectId] = useState("");
  const [ic, setIc] = useState("");
  const [hw, setHw] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const [examId, setExamId] = useState("");
  const [examDayIndex, setExamDayIndex] = useState(0);
  const [examSubjectId, setExamSubjectId] = useState("");
  const [examTitle, setExamTitle] = useState("");
  const [examTime, setExamTime] = useState("09:00");
  const [examLocation, setExamLocation] = useState("");
  const [examNote, setExamNote] = useState("");
  const [courseName, setCourseName] = useState("");
  const [courseShortName, setCourseShortName] = useState("");
  const [courseGrade, setCourseGrade] = useState(11);
  const [courseSection, setCourseSection] = useState("All");
  const [coursePeriod, setCoursePeriod] = useState(1);
  const [courseTeacher, setCourseTeacher] = useState("");
  const [courseRoom, setCourseRoom] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const saving = Boolean(busyKey);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadWeek = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = await api.readCj(weekStart);
      setData(payload);
      setSubjectId((current) => (
        payload.subjects.some((subject) => subject.id === current) ? current : payload.subjects[0]?.id || ""
      ));
      setExamSubjectId((current) => (
        payload.subjects.some((subject) => subject.id === current) ? current : payload.subjects[0]?.id || ""
      ));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "load");
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  useEffect(() => {
    loadWeek();
  }, [loadWeek]);

  useEffect(() => {
    let cancelled = false;
    api.cjSyncStatus()
      .then((status) => {
        if (!cancelled) setSyncStatus(status);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const currentEntry = useMemo(
    () => (data?.entries || []).find((entry) => entry.day_index === dayIndex && entry.subject_id === subjectId),
    [data, dayIndex, subjectId],
  );

  useEffect(() => {
    setIc(currentEntry?.ic || "");
    setHw(currentEntry?.hw || "");
    setAnnouncement(currentEntry?.announcement || "");
  }, [currentEntry]);

  const subjectMap = useMemo(
    () => new Map((data?.subjects || []).map((subject) => [subject.id, subject])),
    [data],
  );

  async function handlePhoto(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusyKey("photo");
    setNotice("");
    try {
      const result = await api.recognizeCj(file, { weekStart, dayIndex });
      setSubjectId(result.subject_id);
      setNotice(
        result.inferred
          ? `${t("cj.photoFiled")} ${result.subject_name}. ${result.inferred}`
          : `${t("cj.photoFiled")} ${result.subject_name}.`,
      );
      await loadWeek();
    } catch (photoError) {
      setNotice(photoError instanceof Error ? photoError.message : t("cj.saveFailed"));
    } finally {
      setBusyKey("");
    }
  }

  async function handleCjSave(event) {
    event.preventDefault();
    setBusyKey("cj-save");
    setNotice("");
    try {
      await api.saveCj({ week_start: weekStart, day_index: dayIndex, subject_id: subjectId, ic, hw, announcement });
      setNotice(t("cj.saved"));
      await loadWeek();
    } catch (saveError) {
      setNotice(saveError instanceof Error ? saveError.message : t("cj.saveFailed"));
    } finally {
      setBusyKey("");
    }
  }

  async function handleExamSave(event) {
    event.preventDefault();
    setBusyKey("exam-save");
    setNotice("");
    try {
      await api.saveExam({
        id: examId || undefined,
        week_start: weekStart,
        day_index: examDayIndex,
        subject_id: examSubjectId,
        title: examTitle,
        time: examTime,
        location: examLocation,
        note: examNote,
      });
      setNotice(t("cj.examSaved"));
      await loadWeek();
      resetExamForm();
    } catch (saveError) {
      setNotice(saveError instanceof Error ? saveError.message : t("cj.saveFailed"));
    } finally {
      setBusyKey("");
    }
  }

  async function handleCourseSave(event) {
    event.preventDefault();
    setBusyKey("course-save");
    setNotice("");
    try {
      const created = await api.createCjSubject({
        name: courseName,
        short_name: courseShortName,
        grade: courseGrade,
        class_section: courseSection,
        default_period: coursePeriod,
        teacher: courseTeacher,
        room: courseRoom,
      });
      setNotice(`${created.name} added.`);
      setCourseName("");
      setCourseShortName("");
      setCourseTeacher("");
      setCourseRoom("");
      await loadWeek();
    } catch (saveError) {
      setNotice(saveError instanceof Error ? saveError.message : "Could not add course.");
    } finally {
      setBusyKey("");
    }
  }

  async function handleExamDelete() {
    if (!examId || !window.confirm("Delete this exam? Students will no longer see it.")) return;
    setBusyKey("exam-delete");
    setNotice("");
    try {
      await api.deleteExam(examId);
      setNotice("Exam deleted.");
      resetExamForm();
      await loadWeek();
    } catch (deleteError) {
      setNotice(deleteError instanceof Error ? deleteError.message : "Could not delete exam.");
    } finally {
      setBusyKey("");
    }
  }

  async function handleCourseDelete(subject) {
    if (!window.confirm(`Delete ${subject.name}? Its CJ entries and exams will also be removed.`)) return;
    setBusyKey(`course-delete:${subject.id}`);
    setNotice("");
    try {
      await api.deleteCjSubject(subject.id);
      setNotice(`${subject.name} deleted.`);
      await loadWeek();
    } catch (deleteError) {
      setNotice(deleteError instanceof Error ? deleteError.message : "Could not delete course.");
    } finally {
      setBusyKey("");
    }
  }

  async function handleSync() {
    setBusyKey("sync");
    setNotice("");
    try {
      const status = await api.syncCj();
      setSyncStatus(status);
      setNotice(t("cj.syncDone"));
      await loadWeek();
    } catch (syncError) {
      setNotice(syncError instanceof Error ? syncError.message : t("cj.syncFailed"));
      try {
        setSyncStatus(await api.cjSyncStatus());
      } catch {
        // The button already shows the request error.
      }
    } finally {
      setBusyKey("");
    }
  }

  function resetExamForm() {
    setExamId("");
    setExamTitle("");
    setExamLocation("");
    setExamNote("");
  }

  function selectDate(value, setSelectedDay) {
    const selected = dateFromIso(value);
    const selectedDay = (selected.getDay() + 6) % 7;
    if (selectedDay > 4) {
      setNotice("Choose a school day from Monday to Friday.");
      return;
    }
    setNotice("");
    setWeekStart(mondayIso(selected));
    setSelectedDay(selectedDay);
  }

  return (
    <section className="mt-8">
      <CjPortalBadge portal={portal} />
      <p className="font-sans text-[11px] uppercase tracking-[0.16em] text-[#1A4FBF]">{t("cj.adminKicker")}</p>
      <h1 className="mt-2 font-serif text-4xl">{t("cj.adminTitle")}</h1>
      <p className="mt-2 font-sans text-sm text-neutral-600">{t("cj.adminLead")}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSync}
          disabled={saving}
          className="inline-flex items-center gap-2 bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.16em] text-white disabled:opacity-40"
        >
          {busyKey === "sync" ? <ButtonSpinner /> : null}
          {busyKey === "sync" ? t("cj.syncing") : t("cj.sync")}
        </button>
        <p className="font-sans text-sm text-neutral-600">{syncSummary(syncStatus, t)}</p>
      </div>
      <p className="mt-3 flex flex-wrap gap-4 font-sans text-sm">
        <Link to="/" className="text-[#1A4FBF]">
          {t("link.frontPage")}
        </Link>
        <Link to={`/cj/admin/student-preview?date=${weekStart}`} className="text-[#1A4FBF]">
          {t("cj.studentPreview")}
        </Link>
      </p>

      {notice ? <p className="mt-3 font-sans text-sm">{notice}</p> : null}

      <div className="mt-6 flex gap-3 font-sans text-[11px] uppercase tracking-[0.14em]">
        <button type="button" onClick={() => setTab("cj")} className={tab === "cj" ? "border-b-2 border-black pb-1" : "pb-1 text-neutral-500"}>
          {t("cj.daily")}
        </button>
        <button type="button" onClick={() => setTab("exams")} className={tab === "exams" ? "border-b-2 border-black pb-1" : "pb-1 text-neutral-500"}>
          {t("cj.examTab")}
        </button>
        <button type="button" onClick={() => setTab("courses")} className={tab === "courses" ? "border-b-2 border-black pb-1" : "pb-1 text-neutral-500"}>
          Courses
        </button>
      </div>

      {tab === "cj" ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <form onSubmit={handleCjSave} className="border border-black p-4">
            <h2 className="font-serif text-2xl">{currentEntry ? t("cj.updateEntry") : t("cj.addEntry")}</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <DateField
                weekStart={weekStart}
                dayIndex={dayIndex}
                onChange={(value) => selectDate(value, setDayIndex)}
              />
              <label className="block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
                {t("cj.subject")}
                <select
                  value={subjectId}
                  onChange={(event) => setSubjectId(event.target.value)}
                  className="mt-2 w-full border border-black bg-white p-2 font-sans text-sm normal-case tracking-normal"
                >
                  {(data?.subjects || []).map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-4 block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
              <span className="inline-flex items-center gap-2">
                {t("cj.photo")}
                {busyKey === "photo" ? <ButtonSpinner /> : null}
              </span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                disabled={saving || loading}
                onChange={handlePhoto}
                className="mt-2 block w-full font-sans text-sm normal-case tracking-normal"
              />
            </label>
            <p className="mt-1 font-sans text-xs normal-case tracking-normal text-neutral-500">{t("cj.photoHint")}</p>
            <TextField label="IC" value={ic} onChange={setIc} />
            <TextField label="HW" value={hw} onChange={setHw} />
            <TextField label="A" value={announcement} onChange={setAnnouncement} />
            <button type="submit" disabled={saving || loading || !subjectId} className="mt-4 inline-flex items-center gap-2 bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.16em] text-white disabled:opacity-40">
              {busyKey === "cj-save" ? <ButtonSpinner /> : null}
              {busyKey === "cj-save" ? t("cj.saving") : t("cj.saveEntry")}
            </button>
          </form>
          <EntryList
            title={t("cj.weekEntries")}
            loading={loading}
            error={error}
            items={(data?.entries || []).map((entry) => ({
              id: entry.id,
              title: subjectMap.get(entry.subject_id)?.short_name || entry.subject_id,
              detail: entry.ic || t("cj.noIc"),
              meta: t(`cj.wd.${entry.day_index}`),
              onClick: () => {
                setDayIndex(entry.day_index);
                setSubjectId(entry.subject_id);
              },
            }))}
          />
        </div>
      ) : tab === "exams" ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <form onSubmit={handleExamSave} className="border border-black p-4">
            <div className="flex items-center justify-between gap-4">
              <h2 className="font-serif text-2xl">{examId ? t("cj.updateExam") : t("cj.addExam")}</h2>
              {examId ? (
                <button type="button" onClick={resetExamForm} className="font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
                  {t("cj.newExam")}
                </button>
              ) : null}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <DateField
                weekStart={weekStart}
                dayIndex={examDayIndex}
                onChange={(value) => selectDate(value, setExamDayIndex)}
              />
              <label className="block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
                {t("cj.time")}
                <input
                  type="time"
                  value={examTime}
                  onChange={(event) => setExamTime(event.target.value)}
                  className="mt-2 w-full border border-black p-2 font-sans text-sm normal-case tracking-normal"
                />
              </label>
            </div>
            <label className="mt-4 block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
              {t("cj.subject")}
              <select
                value={examSubjectId}
                onChange={(event) => setExamSubjectId(event.target.value)}
                className="mt-2 w-full border border-black bg-white p-2 font-sans text-sm normal-case tracking-normal"
              >
                {(data?.subjects || []).map((subject) => (
                  <option key={subject.id} value={subject.id}>{subject.name}</option>
                ))}
              </select>
            </label>
            <LineField label={t("cj.examName")} value={examTitle} onChange={setExamTitle} />
            <LineField label={t("cj.location")} value={examLocation} onChange={setExamLocation} />
            <TextField label={t("cj.note")} value={examNote} onChange={setExamNote} />
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="submit" disabled={saving || loading || !examSubjectId || !examTitle.trim()} className="inline-flex items-center gap-2 bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.16em] text-white disabled:opacity-40">
                {busyKey === "exam-save" ? <ButtonSpinner /> : null}
                {busyKey === "exam-save" ? t("cj.saving") : t("cj.saveExam")}
              </button>
              {examId ? (
                <button type="button" disabled={saving} onClick={handleExamDelete} className="inline-flex items-center gap-2 border border-red-700 px-5 py-2 font-sans text-[11px] uppercase tracking-[0.16em] text-red-700 disabled:opacity-40">
                  {busyKey === "exam-delete" ? <ButtonSpinner /> : null}
                  Delete exam
                </button>
              ) : null}
            </div>
          </form>
          <EntryList
            title={t("cj.weekExams")}
            loading={loading}
            error={error}
            items={(data?.exams || []).map((exam) => ({
              id: exam.id,
              title: examDisplayTitle(exam, subjectMap, t("cj.unassignedSubject")),
              detail: exam.location || t("cj.noLocation"),
              meta: `${t(`cj.wd.${exam.day_index}`)} · ${exam.time}`,
              onClick: () => {
                setExamId(exam.id);
                setExamDayIndex(exam.day_index);
                setExamSubjectId(exam.subject_id || data?.subjects?.[0]?.id || "");
                setExamTitle(exam.title);
                setExamTime(exam.time);
                setExamLocation(exam.location);
                setExamNote(exam.note);
              },
            }))}
          />
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <form onSubmit={handleCourseSave} className="border border-black p-4">
            <h2 className="font-serif text-2xl">Add course</h2>
            <p className="mt-1 font-sans text-sm text-neutral-500">New courses become available immediately in Course setup.</p>
            <LineField label="Course name" value={courseName} onChange={setCourseName} />
            <LineField label="Short name" value={courseShortName} onChange={setCourseShortName} />
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <SelectField label="Grade" value={courseGrade} onChange={(value) => setCourseGrade(Number(value))} options={[9, 10, 11]} />
              <SelectField label="Class" value={courseSection} onChange={setCourseSection} options={["All", "Ac", "Mc"]} />
              <SelectField label="Default period" value={coursePeriod} onChange={(value) => setCoursePeriod(Number(value))} options={Array.from({ length: 11 }, (_, index) => index + 1)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <LineField label="Teacher" value={courseTeacher} onChange={setCourseTeacher} />
              <LineField label="Room" value={courseRoom} onChange={setCourseRoom} />
            </div>
            <button type="submit" disabled={saving || !courseName.trim() || !courseShortName.trim()} className="mt-4 inline-flex items-center gap-2 bg-black px-5 py-2 font-sans text-[11px] uppercase tracking-[0.16em] text-white disabled:opacity-40">
              {busyKey === "course-save" ? <ButtonSpinner /> : null}
              {busyKey === "course-save" ? "Adding…" : "Add course"}
            </button>
          </form>
          <aside className="border border-black p-4">
            <h2 className="font-serif text-2xl">Course catalog</h2>
            <div className="mt-3 grid gap-2">
              {(data?.subjects || []).map((subject) => (
                <div key={subject.id} className="flex items-center justify-between gap-3 border-b border-neutral-200 py-2 font-sans text-sm">
                  <div>
                    <span className="block">{subject.name}</span>
                    <span className="text-xs text-neutral-500">G{subject.grade} · {subject.class_section} · P{subject.default_period}</span>
                  </div>
                  {subject.is_custom ? (
                    <button type="button" disabled={saving} onClick={() => handleCourseDelete(subject)} className="inline-flex items-center gap-1 border border-red-700 px-2 py-1 text-[10px] uppercase tracking-[0.12em] text-red-700 disabled:opacity-40">
                      {busyKey === `course-delete:${subject.id}` ? <ButtonSpinner /> : null}
                      Delete
                    </button>
                  ) : (
                    <span className="text-[10px] uppercase tracking-[0.1em] text-neutral-400">{subject.is_custom ? "Custom" : "School"}</span>
                  )}
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}

function syncSummary(status, t) {
  if (!status || status.status === "idle" || !status.synced_at) return t("cj.syncIdle");
  const time = new Date(status.synced_at).toLocaleString();
  if (status.status === "error") return t("cj.syncError", { time, message: status.message });
  return t("cj.syncOk", { time, courses: status.courses, entries: status.entries });
}

function examDisplayTitle(exam, subjectMap, unassignedLabel) {
  const subject = subjectMap.get(exam.subject_id);
  if (!subject) return `${unassignedLabel} · ${exam.title}`;
  if (exam.title.startsWith(subject.name) || exam.title.startsWith(subject.short_name)) return exam.title;
  return `${subject.short_name} · ${exam.title}`;
}

function DateField({ weekStart, dayIndex, onChange }) {
  const { t } = useI18n();
  return (
    <label className="block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
      {t("cj.date")}
      <input
        type="date"
        value={isoDate(dateForDay(dateFromIso(weekStart), dayIndex))}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border border-black bg-white p-2 font-sans text-sm normal-case tracking-normal"
      />
    </label>
  );
}

function TextField({ label, value, onChange }) {
  return (
    <label className="mt-4 block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
      {label}
      <textarea
        value={value}
        maxLength={800}
        onChange={(event) => onChange(event.target.value)}
        rows={4}
        className="mt-2 w-full border border-black p-2 font-sans text-sm normal-case tracking-normal text-neutral-900"
      />
    </label>
  );
}

function LineField({ label, value, onChange }) {
  return (
    <label className="mt-4 block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
      {label}
      <input
        value={value}
        maxLength={800}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full border border-black p-2 font-sans text-sm normal-case tracking-normal text-neutral-900"
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block font-sans text-[11px] uppercase tracking-[0.14em] text-[#1A4FBF]">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full border border-black bg-white p-2 font-sans text-sm normal-case tracking-normal text-neutral-900">
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
}

function EntryList({ title, loading, error, items }) {
  const { t } = useI18n();
  return (
    <aside className="border border-black">
      <div className="flex items-center justify-between border-b border-black px-4 py-3">
        <h2 className="font-serif text-2xl">{title}</h2>
        <span className="font-sans text-sm">{items.length}</span>
      </div>
      {error ? <p className="p-4 font-sans text-sm text-red-700">{error === "load" ? t("cj.loadFailed") : error}</p> : null}
      {loading ? <p className="p-4 font-sans text-sm text-neutral-500">{t("cj.reading")}</p> : null}
      <div>
        {items.map((item) => (
          <button key={item.id} type="button" onClick={item.onClick} className="block w-full border-b border-neutral-200 px-4 py-3 text-left last:border-b-0">
            <span className="font-sans text-sm font-semibold">{item.title}</span>
            <span className="mt-1 block font-sans text-xs text-neutral-500">{item.detail}</span>
            <span className="mt-1 block font-sans text-[11px] uppercase tracking-[0.12em] text-[#1A4FBF]">{item.meta}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}
