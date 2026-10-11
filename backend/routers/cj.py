import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from cj_vision import recognize_homework
from deps import get_cj_editor, get_cj_viewer, get_core_db, get_super_admin
from errors import ApiError, validation_error
from models import CJEntry, CJTeacherSubject, Exam, Subject, User, to_iso, utc_now

router = APIRouter()

_WEEK = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}$")
_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
_PHOTO_LIMIT = 4 * 1024 * 1024

_SUBJECTS = [
    ("advisory-11ac", "Morning Advisory · 11Ac", "Advisory", "#1d4ed8", 1, 1),
    ("advisory-11mc", "Morning Advisory · 11Mc", "Advisory", "#1d4ed8", 1, 2),
    ("chinese-11ac", "Chinese 11 · Ac", "Chinese 11", "#F04444", 2, 3),
    ("chinese-11mc", "Chinese 11 · Mc", "Chinese 11", "#F04444", 6, 4),
    ("ap-lang-11ac", "AP English Language & Composition · 11Ac", "AP Lang", "#8B5CF6", 5, 5),
    ("ap-lang-11mc", "AP English Language & Composition · 11Mc", "AP Lang", "#8B5CF6", 2, 6),
    ("ap-euro-11ac", "AP European History · 11Ac", "AP Euro", "#F97316", 6, 7),
    ("ap-euro-11mc", "AP European History · 11Mc", "AP Euro", "#F97316", 10, 8),
    ("lunch-11ac", "Lunch · 11Ac", "Lunch", "#64748b", 7, 9),
    ("lunch-11mc", "Lunch · 11Mc", "Lunch", "#64748b", 7, 10),
    ("ae-11ac", "AE · 11Ac", "AE", "#475569", 8, 11),
    ("ae-11mc", "AE · 11Mc", "AE", "#475569", 8, 12),
    ("ap-calculus-11ac", "AP Calculus AB · 11Ac", "AP Calculus AB", "#1677FF", 10, 13),
    ("ap-calculus-11mc", "AP Calculus AB · 11Mc", "AP Calculus AB", "#1677FF", 5, 14),
    ("ap-micro-macro", "AP Microeconomics / AP Macroeconomics (Mr. Peterson's Class)", "AP Econ · Peterson", "#00A86B", 3, 15),
    ("ap-micro-bruce", "AP Microeconomics / AP Macroeconomics (Mr. Bruce's Class)", "AP Econ · Bruce", "#14B8A6", 3, 16),
    ("ap-environmental", "AP Environmental Sciences", "APES", "#84CC16", 3, 17),
    ("ap-geography", "AP Geography", "AP Geo", "#0EA5E9", 3, 18),
    ("study-hall-3", "Study Hall · Period 3", "Study Hall", "#E6A000", 3, 19),
    ("study-hall", "Study Hall · Period 4", "Study Hall", "#E6A000", 4, 20),
    ("ap-biology", "AP Biology", "AP Biology", "#16A34A", 4, 21),
    ("ap-physics-2", "AP Physics 2", "AP Physics 2", "#0284C7", 4, 22),
    ("ap-physics", "AP Physics 1", "AP Physics 1", "#00AFC1", 9, 23),
    ("honors-chemistry", "Honors Chemistry", "Honors Chem", "#F43F5E", 9, 24),
    ("study-hall-9", "Study Hall · Period 9", "Study Hall", "#E6A000", 9, 25),
    ("ap-stats", "AP Statistics", "AP Statistics", "#E83E8C", 11, 26),
    ("ap-csa", "AP Computer Science A", "AP CSA", "#5B4BFF", 11, 27),
    ("study-hall-11", "Study Hall · Period 11", "Study Hall", "#E6A000", 11, 28),
]

_CUSTOM_COLORS = ["#14B8A6", "#A855F7", "#F97316", "#0EA5E9", "#F43F5E", "#84CC16"]

_SUBJECT_DETAILS = {
    "advisory-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Rudi Herman Scheepers", "room": "E307", "required": True},
    "advisory-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Chantal Eloise Rudman", "room": "E302", "required": True},
    "chinese-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Niu Weijia", "room": "E529", "required": True},
    "chinese-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Niu Weijia", "room": "E529", "required": True},
    "ap-lang-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Vivian Chong", "room": "E525", "required": True},
    "ap-lang-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Vivian Chong", "room": "E525", "required": True},
    "ap-euro-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Stewart Mark Smith", "room": "E528", "required": True},
    "ap-euro-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Stewart Mark Smith", "room": "E528", "required": True},
    "lunch-11ac": {"grade": 11, "class_section": "Ac", "teacher": "—", "room": "Canteen", "required": True},
    "lunch-11mc": {"grade": 11, "class_section": "Mc", "teacher": "—", "room": "Canteen", "required": True},
    "ae-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Rudi Herman Scheepers", "room": "E307", "required": True},
    "ae-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Chantal Eloise Rudman", "room": "E302", "required": True},
    "ap-calculus-11ac": {"grade": 11, "class_section": "Ac", "teacher": "Kyle Sheldon Manzoni", "room": "E522", "required": True},
    "ap-calculus-11mc": {"grade": 11, "class_section": "Mc", "teacher": "Kyle Sheldon Manzoni", "room": "E522", "required": True},
    "ap-micro-macro": {"grade": 11, "class_section": "All", "teacher": "Andrew Mark Peterson", "room": "E530", "required": False},
    "ap-micro-bruce": {"grade": 11, "class_section": "All", "teacher": "Bruce Arthur Zeemel", "room": "E523", "required": False},
    "ap-environmental": {"grade": 11, "class_section": "All", "teacher": "To be confirmed", "room": "To be confirmed", "required": False},
    "ap-geography": {"grade": 11, "class_section": "All", "teacher": "To be confirmed", "room": "To be confirmed", "required": False},
    "study-hall-3": {"grade": 11, "class_section": "All", "teacher": "—", "room": "Collaboratory", "required": False},
    "study-hall": {"grade": 11, "class_section": "All", "teacher": "—", "room": "Collaboratory", "required": False},
    "ap-biology": {"grade": 11, "class_section": "All", "teacher": "To be confirmed", "room": "To be confirmed", "required": False},
    "ap-physics-2": {"grade": 11, "class_section": "All", "teacher": "To be confirmed", "room": "To be confirmed", "required": False},
    "ap-physics": {"grade": 11, "class_section": "All", "teacher": "Chantal Eloise Rudman", "room": "E302", "required": False},
    "honors-chemistry": {"grade": 11, "class_section": "All", "teacher": "To be confirmed", "room": "To be confirmed", "required": False},
    "study-hall-9": {"grade": 11, "class_section": "All", "teacher": "—", "room": "Collaboratory", "required": False},
    "ap-stats": {"grade": 11, "class_section": "All", "teacher": "Herman", "room": "BBGM", "required": False},
    "ap-csa": {"grade": 11, "class_section": "All", "teacher": "Chantal Eloise Rudman", "room": "E302", "required": False},
    "study-hall-11": {"grade": 11, "class_section": "All", "teacher": "—", "room": "Collaboratory", "required": False},
}

# day_index, period, subject_id, ic, hw, announcement
_SAMPLE_ENTRIES = [
    (0, 2, "chinese-11ac", "Classical Chinese reading and annotation", "Finish the vocabulary sheet", "Bring the course reader"),
    (0, 3, "ap-micro-macro", "Demand shifts and market equilibrium", "Module 3.2 practice", "Unit quiz Friday"),
    (0, 5, "ap-lang-11ac", "Rhetorical situation and audience", "Annotate the assigned speech", "Bring the blue reader"),
    (0, 6, "ap-euro-11ac", "The French Revolution: causes", "Read pages 214–226", "Seminar Wednesday"),
    (0, 9, "ap-physics", "Newton's third law", "Problems 3, 5, 38 and 46", "Lab groups posted"),
    (0, 10, "ap-calculus-11ac", "Limits and continuity review", "Complete FRQ Set 2 · Q1–4", "Quiz on Wednesday"),
    (0, 11, "ap-csa", "String methods and immutability", "CodingBat String-1 · 1–8", "Office hour 16:20"),
    (1, 2, "chinese-11ac", "Modern prose close reading", "Draft the response paragraph", ""),
    (1, 5, "ap-lang-11ac", "Claims, evidence and commentary", "Draft one body paragraph", "Peer review next class"),
    (1, 6, "ap-euro-11ac", "Revolutionary France", "Complete source comparison", ""),
    (1, 9, "ap-physics", "Free-body diagrams", "Finish cart lab analysis", "Lab report due Thursday"),
    (1, 10, "ap-calculus-11ac", "Implicit differentiation", "Practice 3.2 · #7–12", ""),
    (2, 5, "ap-lang-11ac", "Synthesis source evaluation", "Read sources A–D", "Timed write Friday"),
    (2, 6, "ap-euro-11ac", "Napoleonic Europe", "Timeline checkpoint", ""),
    (2, 9, "ap-physics", "Friction and inclined planes", "Odd-numbered practice", ""),
    (2, 10, "ap-calculus-11ac", "Related rates", "Worksheet · #1–6", "Quiz today"),
    (3, 5, "ap-lang-11ac", "Counterargument workshop", "Revise thesis and outline", "Conference sign-up"),
    (3, 6, "ap-euro-11ac", "Congress of Vienna", "Primary-source notes", ""),
    (3, 9, "ap-physics", "Circular motion introduction", "Lab report final draft", "Due 22:00"),
    (3, 10, "ap-calculus-11ac", "Linearization", "Textbook 4.1 · #9–21 odd", ""),
    (4, 5, "ap-lang-11ac", "Timed synthesis essay", "Reflection form", "Submit by 18:00"),
    (4, 6, "ap-euro-11ac", "Unit review", "Prepare two discussion questions", "Assessment next week"),
    (4, 9, "ap-physics", "Centripetal force", "Read 6.2 and take notes", ""),
    (4, 10, "ap-calculus-11ac", "Optimization", "Weekend mixed practice", "Corrections due Monday"),
]

_SAMPLE_EXAMS = [
    (2, "ap-calculus-11ac", "Unit Quiz", "14:25", "E522", "Related rates and implicit differentiation"),
    (4, "ap-micro-macro", "Unit 2 Exam", "09:05", "E530", "Bring a calculator"),
]


def _week_or_error(value: str) -> str:
    if not _WEEK.fullmatch(value or ""):
        raise validation_error([{"field": "week_start", "message": "Use a YYYY-MM-DD date."}])
    return value


def _slot(db: Session, week_start: str, day_index: int, period: int, subject_id: str) -> CJEntry | None:
    return db.scalar(
        select(CJEntry).where(
            CJEntry.week_start == week_start,
            CJEntry.day_index == day_index,
            CJEntry.period == period,
            CJEntry.subject_id == subject_id,
        )
    )


def _ensure_subjects(db: Session) -> None:
    for subject_id, name, short_name, color, period, sort_order in _SUBJECTS:
        details = _SUBJECT_DETAILS[subject_id]
        row = db.get(Subject, subject_id)
        if row is None:
            db.add(
                Subject(
                    id=subject_id,
                    name=name,
                    short_name=short_name,
                    color=color,
                    period=period,
                    sort_order=sort_order,
                    grade=details["grade"],
                    class_section=details["class_section"],
                    teacher=details["teacher"],
                    room=details["room"],
                    required=details["required"],
                    is_custom=False,
                )
            )
        else:
            row.name = name
            row.short_name = short_name
            row.color = color
            row.period = period
            row.sort_order = sort_order
            row.grade = details["grade"]
            row.class_section = details["class_section"]
            row.teacher = details["teacher"]
            row.room = details["room"]
            row.required = details["required"]
            row.is_custom = False
    db.flush()


def _ensure_seed(db: Session, week_start: str) -> None:
    now = to_iso(utc_now())
    _ensure_subjects(db)

    for index, entry in enumerate(_SAMPLE_ENTRIES):
        day_index, period, subject_id, ic, hw, announcement = entry
        if _slot(db, week_start, day_index, period, subject_id) is None:
            db.add(
                CJEntry(
                    id=f"catalog-v4-{week_start}-{index + 1}",
                    week_start=week_start,
                    day_index=day_index,
                    period=period,
                    subject_id=subject_id,
                    ic=ic,
                    hw=hw,
                    announcement=announcement,
                    updated_at=now,
                )
            )

    for index, exam in enumerate(_SAMPLE_EXAMS):
        day_index, subject_id, title, time, location, note = exam
        existing_exam = db.scalar(
            select(Exam).where(
                Exam.week_start == week_start,
                Exam.day_index == day_index,
                Exam.subject_id == subject_id,
                Exam.title == title,
            )
        )
        if existing_exam is None:
            db.add(
                Exam(
                    id=f"exam-catalog-v4-{week_start}-{index + 1}",
                    week_start=week_start,
                    day_index=day_index,
                    subject_id=subject_id,
                    title=title,
                    time=time,
                    location=location,
                    note=note,
                    updated_at=now,
                )
            )
    db.flush()


def _subject_payload(row: Subject) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "short_name": row.short_name,
        "color": row.color,
        "default_period": row.period,
        "grade": row.grade,
        "class_section": row.class_section,
        "teacher": row.teacher,
        "room": row.room,
        "required": row.required,
        "is_custom": row.is_custom,
    }


def _entry_payload(row: CJEntry) -> dict:
    return {
        "id": row.id,
        "week_start": row.week_start,
        "day_index": row.day_index,
        "period": row.period,
        "subject_id": row.subject_id,
        "ic": row.ic,
        "hw": row.hw,
        "announcement": row.announcement,
        "updated_at": row.updated_at,
    }


def _exam_payload(row: Exam) -> dict:
    return {
        "id": row.id,
        "week_start": row.week_start,
        "day_index": row.day_index,
        "subject_id": row.subject_id,
        "title": row.title,
        "time": row.time,
        "location": row.location,
        "note": row.note,
        "updated_at": row.updated_at,
    }


def _teacher_subject_ids(db: Session, user_id: str) -> list[str]:
    return list(
        db.scalars(
            select(CJTeacherSubject.subject_id)
            .where(CJTeacherSubject.user_id == user_id)
            .order_by(CJTeacherSubject.subject_id)
        ).all()
    )


def _teacher_payload(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "subject_ids": _teacher_subject_ids(db, user.id),
    }


@router.get("/cj")
def read_cj(
    week_start: str = "",
    user: User = Depends(get_cj_viewer),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(week_start)
    _ensure_seed(db, week)
    catalog_ids = list(_SUBJECT_DETAILS) + list(
        db.scalars(select(Subject.id).where(Subject.is_custom.is_(True))).all()
    )
    subject_query = (
        select(Subject)
        .where(Subject.id.in_(catalog_ids))
        .order_by(Subject.sort_order, Subject.name)
    )
    entry_query = (
        select(CJEntry)
        .where(CJEntry.week_start == week, CJEntry.subject_id.in_(catalog_ids))
        .order_by(CJEntry.day_index, CJEntry.period)
    )
    subjects = db.scalars(subject_query).all()
    entries = db.scalars(entry_query).all()
    exams = db.scalars(
        select(Exam)
        .where(Exam.week_start == week, Exam.subject_id.in_(catalog_ids))
        .order_by(Exam.day_index, Exam.time)
    ).all()
    return {
        "week_start": week,
        "subjects": [_subject_payload(row) for row in subjects],
        "entries": [_entry_payload(row) for row in entries],
        "exams": [_exam_payload(row) for row in exams],
    }


@router.post("/cj/subjects", status_code=201)
def create_cj_subject(
    body: dict,
    _: User = Depends(get_cj_editor),
    db: Session = Depends(get_core_db),
):
    name = str(body.get("name") or "").strip()
    short_name = str(body.get("short_name") or "").strip()
    teacher = str(body.get("teacher") or "").strip() or "To be confirmed"
    room = str(body.get("room") or "").strip() or "To be confirmed"
    class_section = str(body.get("class_section") or "All").strip()
    grade = body.get("grade", 11)
    period = body.get("default_period", 1)
    fields = []
    if not name or len(name) > 120:
        fields.append({"field": "name", "message": "Enter a course name up to 120 characters."})
    if not short_name or len(short_name) > 40:
        fields.append({"field": "short_name", "message": "Enter a short name up to 40 characters."})
    if not isinstance(grade, int) or isinstance(grade, bool) or grade not in (9, 10, 11):
        fields.append({"field": "grade", "message": "Choose grade 9, 10 or 11."})
    if class_section not in ("All", "Ac", "Mc"):
        fields.append({"field": "class_section", "message": "Choose All, Ac or Mc."})
    if not isinstance(period, int) or isinstance(period, bool) or period < 1 or period > 11:
        fields.append({"field": "default_period", "message": "Choose period 1 through 11."})
    if len(teacher) > 120 or len(room) > 80:
        fields.append({"field": "teacher", "message": "Teacher or room is too long."})
    if db.scalar(select(Subject.id).where(func.lower(Subject.name) == name.lower())):
        fields.append({"field": "name", "message": "A course with this name already exists."})
    if fields:
        raise validation_error(fields)

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:42] or "course"
    custom_count = db.scalar(select(func.count()).select_from(Subject).where(Subject.is_custom.is_(True))) or 0
    subject = Subject(
        id=f"custom-{slug}-{uuid4().hex[:6]}",
        name=name,
        short_name=short_name,
        color=_CUSTOM_COLORS[custom_count % len(_CUSTOM_COLORS)],
        period=period,
        sort_order=1000 + custom_count,
        grade=grade,
        class_section=class_section,
        teacher=teacher,
        room=room,
        required=False,
        is_custom=True,
    )
    db.add(subject)
    db.flush()
    return _subject_payload(subject)


@router.delete("/cj/subjects/{subject_id}", status_code=204)
def delete_cj_subject(
    subject_id: str,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise ApiError(404, "not_found", "Course not found.")
    if not subject.is_custom:
        raise validation_error([
            {"field": "subject_id", "message": "Built-in school courses cannot be deleted."}
        ])
    db.execute(delete(CJTeacherSubject).where(CJTeacherSubject.subject_id == subject_id))
    db.execute(delete(CJEntry).where(CJEntry.subject_id == subject_id))
    db.execute(delete(Exam).where(Exam.subject_id == subject_id))
    db.delete(subject)
    db.flush()
    return None


@router.put("/cj")
def save_cj(
    body: dict,
    user: User = Depends(get_cj_editor),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(str(body.get("week_start") or ""))
    subject_id = str(body.get("subject_id") or "").strip()
    day_index = body.get("day_index")
    ic = str(body.get("ic") or "").strip()
    hw = str(body.get("hw") or "").strip()
    announcement = str(body.get("announcement") or "").strip()
    fields = []
    if not subject_id:
        fields.append({"field": "subject_id", "message": "Choose a subject."})
    if not isinstance(day_index, int) or isinstance(day_index, bool) or day_index < 0 or day_index > 4:
        fields.append({"field": "day_index", "message": "Choose Monday through Friday."})
    if any(len(value) > 800 for value in (ic, hw, announcement)):
        fields.append({"field": "ic", "message": "IC, HW, and A must be 800 characters or fewer."})
    if fields:
        raise validation_error(fields)

    subject = db.get(Subject, subject_id)
    if subject is None:
        raise ApiError(404, "not_found", "Subject not found.")
    existing = _slot(db, week, day_index, subject.period, subject_id)
    updated_at = to_iso(utc_now())
    if existing is None:
        existing = CJEntry(
            id=str(uuid4()),
            week_start=week,
            day_index=day_index,
            period=subject.period,
            subject_id=subject_id,
            ic=ic,
            hw=hw,
            announcement=announcement,
            updated_at=updated_at,
        )
        db.add(existing)
    else:
        existing.ic = ic
        existing.hw = hw
        existing.announcement = announcement
        existing.updated_at = updated_at
    db.flush()
    return {"id": existing.id, "updated_at": updated_at}


def _clip(value: str) -> str:
    return value.strip()[:800]


@router.post("/cj/recognize")
async def recognize_cj_photo(
    request: Request,
    image: UploadFile = File(...),
    week_start: str = Form(""),
    day_index: str = Form(""),
    _: User = Depends(get_cj_editor),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(week_start)
    try:
        day = int(day_index)
    except ValueError:
        day = -1
    if day < 0 or day > 4:
        raise validation_error([{"field": "day_index", "message": "Choose Monday through Friday."}])
    content_type = (image.content_type or "").split(";")[0].strip().lower()
    if content_type not in _PHOTO_TYPES:
        raise validation_error([{"field": "image", "message": "Use a jpeg, png, or webp photo."}])
    raw = await image.read()
    if not raw or len(raw) > _PHOTO_LIMIT:
        raise validation_error([{"field": "image", "message": "Photo must be under 4MB."}])

    _ensure_seed(db, week)
    subjects = db.scalars(select(Subject).order_by(Subject.sort_order, Subject.name)).all()
    reading = recognize_homework(
        request.app.state.settings.dashscope_api_key,
        raw,
        content_type,
        [{"id": row.id, "name": row.name} for row in subjects],
    )
    subject = next((row for row in subjects if row.id == reading["subject_id"]), None)
    if subject is None:
        wanted = reading["subject_id"].lower()
        subject = next(
            (row for row in subjects if row.name.lower() == wanted or row.short_name.lower() == wanted),
            None,
        )
    if subject is None:
        raise validation_error([{"field": "subject_id", "message": "Could not match this photo to a course."}])

    ic = _clip(reading["ic"])
    hw = _clip(reading["hw"] or reading["transcribed"])
    announcement = _clip(reading["announcement"])
    if not any((ic, hw, announcement)):
        raise validation_error([{"field": "image", "message": "Could not read homework from this photo."}])

    updated_at = to_iso(utc_now())
    existing = _slot(db, week, day, subject.period, subject.id)
    if existing is None:
        existing = CJEntry(
            id=str(uuid4()),
            week_start=week,
            day_index=day,
            period=subject.period,
            subject_id=subject.id,
            ic=ic,
            hw=hw,
            announcement=announcement,
            updated_at=updated_at,
        )
        db.add(existing)
    else:
        if ic:
            existing.ic = ic
        if hw:
            existing.hw = hw
        if announcement:
            existing.announcement = announcement
        existing.updated_at = updated_at
    db.flush()
    return {
        "id": existing.id,
        "subject_id": subject.id,
        "subject_name": subject.name,
        "ic": existing.ic,
        "hw": existing.hw,
        "announcement": existing.announcement,
        "transcribed": _clip(reading["transcribed"]),
        "inferred": _clip(reading["inferred"]),
        "updated_at": existing.updated_at,
    }


@router.put("/cj/exams")
def save_exam(
    body: dict,
    user: User = Depends(get_cj_editor),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(str(body.get("week_start") or ""))
    day_index = body.get("day_index")
    subject_id = str(body.get("subject_id") or "").strip()
    title = str(body.get("title") or "").strip()
    time = str(body.get("time") or "").strip()
    location = str(body.get("location") or "").strip()
    note = str(body.get("note") or "").strip()
    fields = []
    if not subject_id:
        fields.append({"field": "subject_id", "message": "Choose a subject."})
    if not isinstance(day_index, int) or isinstance(day_index, bool) or day_index < 0 or day_index > 4:
        fields.append({"field": "day_index", "message": "Choose Monday through Friday."})
    if not title:
        fields.append({"field": "title", "message": "Enter the exam name."})
    if not _TIME.fullmatch(time):
        fields.append({"field": "time", "message": "Use a HH:MM time."})
    if any(len(value) > 800 for value in (title, location, note)):
        fields.append({"field": "title", "message": "Exam text must be 800 characters or fewer."})
    if fields:
        raise validation_error(fields)

    subject = db.get(Subject, subject_id)
    if subject is None:
        raise ApiError(404, "not_found", "Subject not found.")
    exam_id = str(body.get("id") or "").strip() or str(uuid4())
    updated_at = to_iso(utc_now())
    row = db.get(Exam, exam_id)
    if row is None:
        row = Exam(
            id=exam_id,
            week_start=week,
            day_index=day_index,
            subject_id=subject_id,
            title=title,
            time=time,
            location=location,
            note=note,
            updated_at=updated_at,
        )
        db.add(row)
    else:
        row.week_start = week
        row.day_index = day_index
        row.subject_id = subject_id
        row.title = title
        row.time = time
        row.location = location
        row.note = note
        row.updated_at = updated_at
    db.flush()
    return {"id": row.id, "updated_at": updated_at}


@router.delete("/cj/exams/{exam_id}", status_code=204)
def delete_exam(
    exam_id: str,
    _: User = Depends(get_cj_editor),
    db: Session = Depends(get_core_db),
):
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise ApiError(404, "not_found", "Exam not found.")
    db.delete(exam)
    db.flush()
    return None


@router.get("/cj/teachers")
def list_cj_teachers(
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    teachers = db.scalars(
        select(User).where(User.role == "teacher").order_by(User.display_name, User.email)
    ).all()
    return {"items": [_teacher_payload(db, teacher) for teacher in teachers]}


@router.put("/cj/teachers/{teacher_id}")
def assign_cj_teacher_subjects(
    teacher_id: str,
    body: dict,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    teacher = db.get(User, teacher_id)
    if teacher is None or teacher.role != "teacher":
        raise ApiError(404, "not_found", "Teacher not found.")

    raw_ids = body.get("subject_ids")
    if not isinstance(raw_ids, list) or any(not isinstance(value, str) for value in raw_ids):
        raise validation_error([{"field": "subject_ids", "message": "Choose one subject."}])
    subject_ids = list(dict.fromkeys(value.strip() for value in raw_ids if value.strip()))
    if len(subject_ids) > 1:
        raise validation_error([{"field": "subject_ids", "message": "Each teacher can manage one CJ subject."}])
    existing_ids = set(
        db.scalars(select(Subject.id).where(Subject.id.in_(subject_ids))).all()
    ) if subject_ids else set()
    if len(existing_ids) != len(subject_ids):
        raise validation_error([{"field": "subject_ids", "message": "One or more subjects do not exist."}])

    db.execute(delete(CJTeacherSubject).where(CJTeacherSubject.user_id == teacher.id))
    for subject_id in subject_ids:
        db.add(
            CJTeacherSubject(
                id=str(uuid4()),
                user_id=teacher.id,
                subject_id=subject_id,
            )
        )
    db.flush()
    return _teacher_payload(db, teacher)
