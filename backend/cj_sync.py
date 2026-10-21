import json
import logging
import re
import threading
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from errors import ApiError
from models import CJEntry, CJSyncState, CJTeacherSubject, Exam, Subject, to_iso, utc_now

logger = logging.getLogger("elegram.cj")

sync_lock = threading.Lock()
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_STATE_ID = "current"
_JOURNAL_TIMEOUT = 45
_DEEPSEEK_TIMEOUT = 90
_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_CHUNK = 20
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PAIR_MATE = {
    "ap-calculus-11ac": "ap-calculus-11mc",
    "ap-calculus-11mc": "ap-calculus-11ac",
    "chinese-11ac": "chinese-11mc",
    "chinese-11mc": "chinese-11ac",
    "ap-lang-11ac": "ap-lang-11mc",
    "ap-lang-11mc": "ap-lang-11ac",
    "ap-euro-11ac": "ap-euro-11mc",
    "ap-euro-11mc": "ap-euro-11ac",
}
_JOURNAL_SUBJECTS = {
    "physics-2": "ap-physics-2",
    "physics": "ap-physics",
    "stats": "ap-stats",
    "calculus": {"Ac": "ap-calculus-11ac", "Mc": "ap-calculus-11mc"},
    "chinese": {"Ac": "chinese-11ac", "Mc": "chinese-11mc"},
    "lang": {"Ac": "ap-lang-11ac", "Mc": "ap-lang-11mc"},
    "euro": {"Ac": "ap-euro-11ac", "Mc": "ap-euro-11mc"},
    "biology": "ap-biology",
    "environmental": "ap-environmental",
    "geography": "ap-geography",
    "chemistry": "honors-chemistry",
    "csa": "ap-csa",
}
_CLEAN_PROMPT = (
    "You clean Classroom Journal fields. Reply with JSON only, shaped as "
    '{"items":[{"id":"...","ic":"...","hw":"...","an":"..."}]}.\n'
    "Rules:\n"
    "- Keep each string in its own field. Never move text between ic, hw, and an.\n"
    "- Do not add facts, assignments, or announcements that are not already in that field.\n"
    "- Trim whitespace. Complete an obvious cut-off word only when that same field already shows how it ends.\n"
    "- Leave an empty field empty.\n"
    "- Each field is at most 800 characters.\n"
    "- Return every id once."
)


def shanghai_today() -> date:
    return datetime.now(_SHANGHAI).date()


def sync_window(today: date | None = None) -> tuple[str, str]:
    current = today or shanghai_today()
    monday = current - timedelta(days=current.weekday())
    next_friday = monday + timedelta(days=11)
    return monday.isoformat(), next_friday.isoformat()


def sync_status_payload(row: CJSyncState | None) -> dict:
    if row is None or not row.synced_at:
        return {
            "synced_at": None,
            "from": None,
            "to": None,
            "courses": 0,
            "entries": 0,
            "status": "idle",
            "message": "",
        }
    return {
        "synced_at": row.synced_at,
        "from": row.window_from or None,
        "to": row.window_to or None,
        "courses": row.courses,
        "entries": row.entries,
        "status": row.status,
        "message": row.message,
    }


def run_sync(db: Session, settings, *, session_factory=None) -> dict:
    if not sync_lock.acquire(blocking=False):
        raise ApiError(409, "sync_in_progress", "A CJ sync is already running.")
    try:
        try:
            result = _perform(db, settings)
            _store_state(db, result)
            return result
        except ApiError as exc:
            db.rollback()
            if session_factory is not None:
                _store_failure(session_factory, exc.message)
            raise
    finally:
        sync_lock.release()


def run_scheduled_sync(app) -> None:
    settings = app.state.settings
    if not settings.cj_journal_base_url:
        return
    db = app.state.core_session_factory()
    try:
        run_sync(db, settings, session_factory=app.state.core_session_factory)
        db.commit()
    except ApiError as exc:
        db.rollback()
        if exc.status_code != 409:
            logger.warning("CJ journal sync failed: %s", exc.message)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetch_journal(base_url: str, api_key: str, start: str, end: str) -> list:
    url = f"{base_url.rstrip('/')}/public/journal"
    try:
        with httpx.Client(timeout=_JOURNAL_TIMEOUT) as client:
            response = client.get(
                url,
                params={"from": start, "to": end},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
    except httpx.HTTPError as exc:
        raise ApiError(503, "service_unavailable", "The journal service is unavailable.") from exc
    if response.status_code != 200:
        raise ApiError(503, "service_unavailable", _journal_message(response))
    try:
        data = response.json()
    except ValueError as exc:
        raise ApiError(503, "service_unavailable", "The journal service returned nothing usable.") from exc
    if isinstance(data, dict):
        for key in ("courses", "items", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ApiError(503, "service_unavailable", "The journal service returned nothing usable.")
    return data


def parse_courses(payload: list) -> list[dict]:
    courses = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        code = _text(_pick(raw, "code", "course_code", "courseCode"))
        name = _text(_pick(raw, "name", "course_name", "courseName"))
        if not code or not name:
            continue
        environment = _text(_pick(raw, "environment", "environment_code", "environmentCode"))
        teacher = _text(
            _pick(
                raw,
                "teacher",
                "teacher_name",
                "teacherName",
                "teacher_display_name",
                "teacherDisplayName",
            )
        ) or "To be confirmed"
        room = _text(_pick(raw, "classroom", "location", "room")) or "To be confirmed"
        period, periods = _schedule(raw)
        courses.append(
            {
                "id": _subject_id(environment, code),
                "code": code[:40],
                "name": name[:120],
                "teacher": teacher[:120],
                "room": room[:80],
                "period": period,
                "periods": periods,
                "days": _days(_pick(raw, "daily_content", "dailyContent", "content", "days")),
            }
        )
    return courses


def clean_daily_fields(api_key: str, model: str, items: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for start in range(0, len(items), _CHUNK):
        cleaned.extend(_clean_chunk(api_key, model, items[start : start + _CHUNK]))
    return cleaned


def _perform(db: Session, settings) -> dict:
    if not settings.cj_journal_base_url or not settings.cj_journal_api_key or not settings.deepseek_api_key:
        raise ApiError(503, "service_unavailable", "CJ journal sync is not configured.")
    start, end = sync_window()
    payload = fetch_journal(settings.cj_journal_base_url, settings.cj_journal_api_key, start, end)
    courses = parse_courses(payload)
    pending = _pending_fields(courses, start, end)
    cleaned = (
        clean_daily_fields(settings.deepseek_api_key, settings.deepseek_model, pending)
        if pending
        else []
    )
    by_id = _validated_clean(pending, cleaned)
    courses_written, entries_written = _apply(db, courses, by_id, start, end)
    return {
        "synced_at": to_iso(utc_now()),
        "from": start,
        "to": end,
        "courses": courses_written,
        "entries": entries_written,
        "status": "ok",
        "message": "",
    }


def _pending_fields(courses: list[dict], start: str, end: str) -> list[dict]:
    pending = []
    for course in courses:
        for day, fields in course["days"].items():
            if not (start <= day <= end):
                continue
            if not any(fields.values()):
                continue
            pending.append({"id": f"{course['id']}|{day}", **fields})
    return pending


def _validated_clean(pending: list[dict], cleaned: list[dict]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for item in cleaned:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ApiError(503, "service_unavailable", "DeepSeek could not clean the journal text.")
        found[item["id"]] = {
            "ic": _clip(item.get("ic")),
            "hw": _clip(item.get("hw")),
            "an": _clip(item.get("an")),
        }
    for source in pending:
        result = found.get(source["id"])
        if result is None:
            raise ApiError(503, "service_unavailable", "DeepSeek could not clean the journal text.")
        for key in ("ic", "hw", "an"):
            if source[key] and not result[key]:
                raise ApiError(503, "service_unavailable", "DeepSeek could not clean the journal text.")
    return found


def match_journal_course(name: str, teacher: str = "") -> str | None:
    folded = _fold(name)
    family = _family(folded)
    if family == "econ":
        who = _fold(f"{teacher} {name}")
        if "peterson" in who:
            return "ap-micro-macro"
        if "bruce" in who or "zeemel" in who:
            return "ap-micro-bruce"
        return None
    target = _JOURNAL_SUBJECTS.get(family or "")
    if target is None:
        return None
    if isinstance(target, str):
        return target
    return target.get(_section(folded) or "")


def _day_fields(course: dict | None, day: date, cleaned: dict[str, dict]) -> dict:
    if course is None:
        return {"ic": "", "hw": "", "an": ""}
    slot_id = f"{course['id']}|{day.isoformat()}"
    return cleaned.get(slot_id) or {"ic": "", "hw": "", "an": ""}


def _fill_empty(own: dict, other: dict) -> dict:
    return {key: own[key] or other[key] for key in ("ic", "hw", "an")}


def _apply(db: Session, courses: list[dict], cleaned: dict[str, dict], start: str, end: str) -> tuple[int, int]:
    from routers.cj import _SUBJECT_DETAILS, _ensure_subjects

    _ensure_subjects(db)
    by_subject: dict[str, dict] = {}
    for course in courses:
        subject_id = match_journal_course(course["name"], course["teacher"])
        subject = db.get(Subject, subject_id) if subject_id else None
        if subject is None:
            logger.warning("CJ journal course has no catalog subject: %s", course["name"])
            continue
        by_subject[subject_id] = course
    written = 0
    handled: set[str] = set()
    for subject_id, course in by_subject.items():
        if subject_id in handled:
            continue
        subject = db.get(Subject, subject_id)
        mate_id = _PAIR_MATE.get(subject_id)
        mate = db.get(Subject, mate_id) if mate_id else None
        mate_course = by_subject.get(mate_id) if mate_id else None
        handled.add(subject_id)
        if mate_id:
            handled.add(mate_id)
        for day in _school_days(start, end):
            own = _day_fields(course, day, cleaned)
            other = _day_fields(mate_course, day, cleaned)
            if subject is not None and _write_day(db, subject, day, _fill_empty(own, other), subject.period):
                written += 1
            if mate is not None and _write_day(db, mate, day, _fill_empty(other, own), mate.period):
                written += 1
    _drop_unmapped(db, set(_SUBJECT_DETAILS))
    db.flush()
    return len(by_subject), written


def _drop_unmapped(db: Session, catalog_ids: set[str]) -> None:
    extras = list(
        db.scalars(
            select(Subject.id).where(
                Subject.is_custom.is_(False),
                Subject.id.notin_(catalog_ids),
            )
        ).all()
    )
    if not extras:
        return
    db.execute(delete(CJEntry).where(CJEntry.subject_id.in_(extras)))
    referenced = set(
        db.scalars(select(Exam.subject_id).where(Exam.subject_id.in_(extras))).all()
    )
    referenced.update(
        db.scalars(
            select(CJTeacherSubject.subject_id).where(CJTeacherSubject.subject_id.in_(extras))
        ).all()
    )
    removable = [subject_id for subject_id in extras if subject_id not in referenced]
    if removable:
        db.execute(delete(Subject).where(Subject.id.in_(removable)))


def _write_day(db: Session, subject: Subject, day: date, fields: dict, period: int) -> bool:
    week_start = (day - timedelta(days=day.weekday())).isoformat()
    ic = fields["ic"]
    hw = fields["hw"]
    announcement = fields["an"]
    rows = list(
        db.scalars(
            select(CJEntry).where(
                CJEntry.week_start == week_start,
                CJEntry.day_index == day.weekday(),
                CJEntry.subject_id == subject.id,
            )
        ).all()
    )
    has_text = any((ic, hw, announcement))
    if not rows:
        if not has_text:
            return False
        db.add(
            CJEntry(
                id=str(uuid4()),
                week_start=week_start,
                day_index=day.weekday(),
                period=period,
                subject_id=subject.id,
                ic=ic,
                hw=hw,
                announcement=announcement,
                updated_at=to_iso(utc_now()),
            )
        )
        return True
    row = rows[0]
    for extra in rows[1:]:
        db.delete(extra)
    changed = (
        row.ic != ic
        or row.hw != hw
        or row.announcement != announcement
        or row.period != period
    )
    if not has_text and not any((row.ic, row.hw, row.announcement)):
        row.period = period
        return False
    row.period = period
    row.ic = ic
    row.hw = hw
    row.announcement = announcement
    row.updated_at = to_iso(utc_now())
    return changed or has_text


def _store_state(db: Session, result: dict) -> None:
    row = db.get(CJSyncState, _STATE_ID)
    if row is None:
        row = CJSyncState(id=_STATE_ID)
        db.add(row)
    row.synced_at = result["synced_at"]
    row.window_from = result["from"] or ""
    row.window_to = result["to"] or ""
    row.courses = result["courses"]
    row.entries = result["entries"]
    row.status = result["status"]
    row.message = result["message"][:500]


def _store_failure(session_factory, message: str) -> None:
    db = session_factory()
    try:
        _store_state(
            db,
            {
                "synced_at": to_iso(utc_now()),
                "from": "",
                "to": "",
                "courses": 0,
                "entries": 0,
                "status": "error",
                "message": message,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not record the CJ sync failure")
    finally:
        db.close()


def _clean_chunk(api_key: str, model: str, items: list[dict]) -> list[dict]:
    try:
        with httpx.Client(timeout=_DEEPSEEK_TIMEOUT) as client:
            response = client.post(
                _DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _CLEAN_PROMPT},
                        {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = _parse_json_object(content)
        rows = parsed.get("items")
        if not isinstance(rows, list):
            raise ValueError("missing items")
        return rows
    except ApiError:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ApiError(503, "service_unavailable", "DeepSeek could not clean the journal text.") from exc


def _parse_json_object(text: str) -> dict:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


def _journal_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        message = body.get("error") or body.get("message")
        if isinstance(message, dict):
            message = message.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:240]
    return "The journal service is unavailable."


def _school_days(start: str, end: str):
    current = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while current <= last:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def _fold(name: str) -> str:
    text = name.lower().replace("&", " and ")
    text = re.sub(r"(\d+)\s*(ac|mc)\b", r"\1 \2", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return f" {text} "


def _section(folded: str) -> str | None:
    has_ac = re.search(r"\bac\b", folded) is not None
    has_mc = re.search(r"\bmc\b", folded) is not None
    if has_ac and not has_mc:
        return "Ac"
    if has_mc and not has_ac:
        return "Mc"
    return None


def _family(folded: str) -> str | None:
    if "physics 2" in folded:
        return "physics-2"
    if "physics" in folded:
        return "physics"
    if "stat" in folded:
        return "stats"
    if "calculus" in folded:
        return "calculus"
    if "chinese" in folded:
        return "chinese"
    if "language" in folded or " ap lang " in folded or "composition" in folded:
        return "lang"
    if "european" in folded or " euro " in folded:
        return "euro"
    if "biology" in folded:
        return "biology"
    if "environmental" in folded:
        return "environmental"
    if "geography" in folded:
        return "geography"
    if "chemistry" in folded or " chem " in folded:
        return "chemistry"
    if "computer science" in folded or " csa " in folded:
        return "csa"
    if "micro" in folded or "macro" in folded or "econ" in folded:
        return "econ"
    return None


def _subject_id(environment: str, code: str) -> str:
    raw = f"{environment}-{code}" if environment else code
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return (slug or "course")[:64]


def _days(value) -> dict[str, dict]:
    rows = []
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, dict):
                rows.append({**item, "date": item.get("date") or key})
    found = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        day = _as_date(item.get("date"))
        if day is None or day.weekday() > 4:
            continue
        found[day.isoformat()] = {
            "ic": _text(_pick(item, "ic", "in_class")),
            "hw": _text(_pick(item, "hw", "homework")),
            "an": _text(_pick(item, "an", "announcement")),
        }
    return found


def _schedule(raw: dict) -> tuple[int, dict[int, int]]:
    periods: dict[int, int] = {}
    meetings = raw.get("meetings")
    if isinstance(meetings, list):
        for meeting in meetings:
            if not isinstance(meeting, dict):
                continue
            weekday = _meeting_weekday(meeting.get("weekday"))
            period = _explicit_period(meeting.get("period"))
            if weekday is None or period is None:
                continue
            periods[weekday] = period
    fallback = _explicit_period(_pick(raw, "period", "course_period", "coursePeriod"))
    if periods:
        values = list(periods.values())
        default = max(set(values), key=values.count)
    else:
        default = fallback or 1
    return default, periods


def _meeting_weekday(value) -> int | None:
    number = _explicit_int(value)
    if number is None:
        return None
    if 1 <= number <= 5:
        return number - 1
    if number == 0:
        return 0
    return None


def _explicit_int(value) -> int | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    match = re.search(r"\d+", _text(value))
    if match:
        return int(match.group(0))
    return None


def _explicit_period(value) -> int | None:
    number = _explicit_int(value)
    if number is not None and 1 <= number <= 11:
        return number
    return None


def _as_date(value) -> date | None:
    text = _text(value)[:10]
    if not _DATE.fullmatch(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _pick(raw: dict, *keys):
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return None


def _text(value) -> str:
    if isinstance(value, dict):
        return _text(value.get("display_name") or value.get("name") or value.get("code"))
    if value is None:
        return ""
    return str(value).strip()


def _clip(value) -> str:
    return _text(value)[:800]
