from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from deps import get_core_db, get_current_user, get_db, get_moderator, require_not_muted
from errors import ApiError, StorageError, forbidden, validation_error
from identity import user_has
from models import Bottle, BottleMessage, BottlePick, BottleReport, User, to_iso, utc_now
from schemas import MODERATOR_ROLES, BottleTextBody
from store import add_system_notice, delete_bottle_graph, users_by_ids
from validate import parse_page, parse_page_size, parse_uuid

router = APIRouter()

THROW_LIMIT = 3
PICK_LIMIT = 5
BODY_MAX = 500
EXCERPT_MAX = 120
BOTTLE_REMOVED = "Your drift bottle was removed."
REPLY_REMOVED = "Your reply in a drift bottle was removed."


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _day_start() -> datetime:
    now = utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _excerpt(body: str) -> str:
    return body.strip()[:EXCERPT_MAX]


def _parse_body(value: str) -> str:
    text = value.strip()
    if not text or len(text) > BODY_MAX:
        raise validation_error([{"field": "body", "message": "Body must be 1–500 characters."}])
    return text


def _count_since(db: Session, model, column, user_id: str) -> int:
    try:
        return (
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(column == user_id, model.created_at >= _day_start())
            )
            or 0
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc


def _random_order(db: Session):
    if db.get_bind().dialect.name == "mysql":
        return func.rand()
    return func.random()


def _party(user: User | None, user_id: str) -> dict:
    if user is None:
        return {"id": user_id, "display_name": "Unknown", "email": ""}
    return {"id": user.id, "display_name": user.display_name, "email": user.email}


def _load_bottle(db: Session, bottle_id: str) -> Bottle:
    try:
        bottle = db.get(Bottle, bottle_id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if bottle is None:
        raise ApiError(404, "not_found", "Bottle not found.")
    return bottle


def _load_pick(db: Session, pick_id: str) -> tuple[BottlePick, Bottle]:
    try:
        pick = db.get(BottlePick, pick_id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if pick is None:
        raise ApiError(404, "not_found", "That conversation was not found.")
    bottle = _load_bottle(db, pick.bottle_id)
    return pick, bottle


def _messages_for(db: Session, pick_ids: list[str]) -> dict[str, list[BottleMessage]]:
    grouped: dict[str, list[BottleMessage]] = {pick_id: [] for pick_id in pick_ids}
    if not pick_ids:
        return grouped
    try:
        rows = db.scalars(
            select(BottleMessage)
            .where(BottleMessage.pick_id.in_(pick_ids))
            .order_by(BottleMessage.created_at.asc())
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    for row in rows:
        grouped.setdefault(row.pick_id, []).append(row)
    return grouped


def _is_unread(user_id: str, pick: BottlePick, bottle: Bottle, messages: list[BottleMessage]) -> int:
    if user_id == bottle.author_id:
        read_at = _as_utc(pick.thrower_read_at)
    elif user_id == pick.picker_id:
        read_at = _as_utc(pick.picker_read_at)
    else:
        return 0
    for message in messages:
        if message.author_id != user_id and _as_utc(message.created_at) > read_at:
            return 1
    return 0


def _message_out(message: BottleMessage, user_id: str, thrower_id: str) -> dict:
    return {
        "id": message.id,
        "body": message.body,
        "created_at": to_iso(message.created_at),
        "mine": message.author_id == user_id,
        "from": "thrower" if message.author_id == thrower_id else "picker",
    }


def _role(user: User, pick: BottlePick, bottle: Bottle) -> str:
    if user.id == bottle.author_id:
        return "thrower"
    if user.id == pick.picker_id:
        return "picker"
    return "moderator"


def _can_view(user: User, pick: BottlePick, bottle: Bottle) -> bool:
    return user.id in (bottle.author_id, pick.picker_id) or user_has(user, *MODERATOR_ROLES)


def _require_view(user: User, pick: BottlePick, bottle: Bottle) -> None:
    if not _can_view(user, pick, bottle):
        raise forbidden()


def _require_participant(user: User, pick: BottlePick, bottle: Bottle) -> None:
    if user.id not in (bottle.author_id, pick.picker_id):
        raise forbidden()


def _thread_out(
    user: User,
    pick: BottlePick,
    bottle: Bottle,
    messages: list[BottleMessage],
    core: Session | None = None,
) -> dict:
    payload = {
        "id": pick.id,
        "bottle_id": bottle.id,
        "bottle_body": bottle.body,
        "bottle_created_at": to_iso(bottle.created_at),
        "created_at": to_iso(pick.created_at),
        "messages": [_message_out(message, user.id, bottle.author_id) for message in messages],
        "role": _role(user, pick, bottle),
        "unread": _is_unread(user.id, pick, bottle, messages),
    }
    if core is not None and user_has(user, *MODERATOR_ROLES):
        people = users_by_ids(core, [bottle.author_id, pick.picker_id])
        thrower = _party(people.get(bottle.author_id), bottle.author_id)
        picker = _party(people.get(pick.picker_id), pick.picker_id)
        if user.id == pick.picker_id:
            thrower.pop("email", None)
        if user.id == bottle.author_id:
            picker.pop("email", None)
        payload["thrower"] = thrower
        payload["picker"] = picker
    return payload


def _mine_item(
    bottle: Bottle,
    pick: BottlePick | None,
    messages: list[BottleMessage],
    user_id: str,
) -> dict:
    created = pick.created_at if pick is not None else bottle.created_at
    return {
        "bottle_id": bottle.id,
        "pick_id": pick.id if pick is not None else None,
        "excerpt": _excerpt(bottle.body),
        "created_at": to_iso(created),
        "reply_count": len(messages),
        "unread": _is_unread(user_id, pick, bottle, messages) if pick is not None else 0,
    }


def _stamp_after(previous: datetime) -> datetime:
    now = utc_now()
    prior = _as_utc(previous)
    if now <= prior:
        return prior + timedelta(seconds=1)
    return now


@router.post("/bottles", status_code=201)
def throw_bottle(
    body: BottleTextBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    text = _parse_body(body.body)
    if _count_since(db, Bottle, Bottle.author_id, user.id) >= THROW_LIMIT:
        raise forbidden("You can throw 3 bottles each day.")
    bottle = Bottle(
        id=str(uuid4()),
        author_id=user.id,
        body=text,
        created_at=utc_now(),
    )
    try:
        db.add(bottle)
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {"id": bottle.id, "body": bottle.body, "created_at": to_iso(bottle.created_at)}


@router.post("/bottles/pick")
def pick_bottle(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    if _count_since(db, BottlePick, BottlePick.picker_id, user.id) >= PICK_LIMIT:
        raise forbidden("You can pick 5 bottles each day.")
    already = select(BottlePick.id).where(
        BottlePick.bottle_id == Bottle.id,
        BottlePick.picker_id == user.id,
    )
    try:
        bottle = db.scalar(
            select(Bottle)
            .where(Bottle.author_id != user.id)
            .where(~already.exists())
            .order_by(_random_order(db))
            .limit(1)
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if bottle is None:
        return {"pick": None}
    now = utc_now()
    pick = BottlePick(
        id=str(uuid4()),
        bottle_id=bottle.id,
        picker_id=user.id,
        created_at=now,
        thrower_read_at=now,
        picker_read_at=now,
    )
    try:
        db.add(pick)
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return {"pick": _thread_out(user, pick, bottle, [])}


@router.get("/bottles/mine")
def my_bottles(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        thrown_bottles = db.scalars(
            select(Bottle).where(Bottle.author_id == user.id).order_by(Bottle.created_at.desc())
        ).all()
        thrown_ids = [bottle.id for bottle in thrown_bottles]
        thrown_picks = []
        if thrown_ids:
            thrown_picks = db.scalars(
                select(BottlePick).where(BottlePick.bottle_id.in_(thrown_ids))
            ).all()
        picked = db.scalars(
            select(BottlePick)
            .where(BottlePick.picker_id == user.id)
            .order_by(BottlePick.created_at.desc())
        ).all()
        picked_bottles = {}
        picked_ids = [pick.bottle_id for pick in picked]
        if picked_ids:
            for bottle in db.scalars(select(Bottle).where(Bottle.id.in_(picked_ids))).all():
                picked_bottles[bottle.id] = bottle
    except SQLAlchemyError as exc:
        raise StorageError() from exc

    bottles_by_id = {bottle.id: bottle for bottle in thrown_bottles}
    bottles_by_id.update(picked_bottles)
    grouped = _messages_for(db, [pick.id for pick in thrown_picks] + [pick.id for pick in picked])
    picks_by_bottle: dict[str, list[BottlePick]] = {}
    for pick in thrown_picks:
        picks_by_bottle.setdefault(pick.bottle_id, []).append(pick)

    thrown = []
    for bottle in thrown_bottles:
        related = picks_by_bottle.get(bottle.id) or []
        if not related:
            thrown.append(_mine_item(bottle, None, [], user.id))
            continue
        for pick in related:
            thrown.append(_mine_item(bottle, pick, grouped.get(pick.id, []), user.id))
    thrown.sort(key=lambda item: item["created_at"], reverse=True)

    picked_items = []
    for pick in picked:
        bottle = bottles_by_id.get(pick.bottle_id)
        if bottle is None:
            continue
        picked_items.append(_mine_item(bottle, pick, grouped.get(pick.id, []), user.id))
    return {"thrown": thrown, "picked": picked_items}


@router.get("/bottles/reports")
def list_reports(
    page: str | None = Query(default=None),
    page_size: str | None = Query(default=None),
    _moderator: User = Depends(get_moderator),
    db: Session = Depends(get_db),
):
    parsed_page = parse_page(page)
    parsed_size = parse_page_size(page_size)
    try:
        total = db.scalar(select(func.count()).select_from(BottleReport)) or 0
        reports = db.scalars(
            select(BottleReport)
            .order_by(BottleReport.created_at.desc())
            .offset((parsed_page - 1) * parsed_size)
            .limit(parsed_size)
        ).all()
        pick_ids = [report.pick_id for report in reports]
        picks = {}
        if pick_ids:
            for pick in db.scalars(select(BottlePick).where(BottlePick.id.in_(pick_ids))).all():
                picks[pick.id] = pick
        bottle_ids = [pick.bottle_id for pick in picks.values()]
        bottles = {}
        if bottle_ids:
            for bottle in db.scalars(select(Bottle).where(Bottle.id.in_(bottle_ids))).all():
                bottles[bottle.id] = bottle
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    items = []
    for report in reports:
        pick = picks.get(report.pick_id)
        bottle = bottles.get(pick.bottle_id) if pick is not None else None
        if pick is None or bottle is None:
            continue
        items.append(
            {
                "id": report.id,
                "pick_id": pick.id,
                "bottle_id": bottle.id,
                "excerpt": _excerpt(bottle.body),
                "created_at": to_iso(report.created_at),
            }
        )
    return {"items": items, "page": parsed_page, "page_size": parsed_size, "total": total}


@router.get("/me/bottle-activity")
def bottle_activity(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            select(BottlePick, Bottle)
            .join(Bottle, Bottle.id == BottlePick.bottle_id)
            .where((BottlePick.picker_id == user.id) | (Bottle.author_id == user.id))
        ).all()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    grouped = _messages_for(db, [pick.id for pick, _bottle in rows])
    unread = 0
    for pick, bottle in rows:
        if _is_unread(user.id, pick, bottle, grouped.get(pick.id, [])):
            unread = 1
            break
    return {"unread": unread}


@router.get("/bottles/picks/{pick_id}")
def get_pick(
    pick_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    pick, bottle = _load_pick(db, parse_uuid(pick_id, field="pick_id"))
    _require_view(user, pick, bottle)
    grouped = _messages_for(db, [pick.id])
    return _thread_out(user, pick, bottle, grouped.get(pick.id, []), core)


@router.post("/bottles/picks/{pick_id}/messages", status_code=201)
def reply_to_pick(
    pick_id: str,
    body: BottleTextBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_not_muted(user)
    text = _parse_body(body.body)
    pick, bottle = _load_pick(db, parse_uuid(pick_id, field="pick_id"))
    _require_participant(user, pick, bottle)
    recipient_read = pick.picker_read_at if user.id == bottle.author_id else pick.thrower_read_at
    message = BottleMessage(
        id=str(uuid4()),
        pick_id=pick.id,
        author_id=user.id,
        body=text,
        created_at=_stamp_after(recipient_read),
    )
    if user.id == bottle.author_id:
        pick.thrower_read_at = message.created_at
    else:
        pick.picker_read_at = message.created_at
    try:
        db.add(message)
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return _message_out(message, user.id, bottle.author_id)


@router.post("/bottles/picks/{pick_id}/read", status_code=204)
def read_pick(
    pick_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pick, bottle = _load_pick(db, parse_uuid(pick_id, field="pick_id"))
    _require_view(user, pick, bottle)
    if user.id not in (bottle.author_id, pick.picker_id):
        return None
    grouped = _messages_for(db, [pick.id])
    latest = utc_now()
    for message in grouped.get(pick.id, []):
        stamped = _as_utc(message.created_at)
        if stamped > latest:
            latest = stamped
    if user.id == bottle.author_id:
        pick.thrower_read_at = latest
    else:
        pick.picker_read_at = latest
    try:
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return None


@router.post("/bottles/picks/{pick_id}/report", status_code=204)
def report_pick(
    pick_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pick, bottle = _load_pick(db, parse_uuid(pick_id, field="pick_id"))
    _require_participant(user, pick, bottle)
    try:
        existing = db.scalar(
            select(BottleReport).where(
                BottleReport.pick_id == pick.id,
                BottleReport.reporter_id == user.id,
            )
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if existing is None:
        db.add(
            BottleReport(
                id=str(uuid4()),
                pick_id=pick.id,
                reporter_id=user.id,
                created_at=utc_now(),
            )
        )
        try:
            db.flush()
        except SQLAlchemyError as exc:
            raise StorageError() from exc
    return None


@router.delete("/bottles/{bottle_id}", status_code=204)
def delete_bottle(
    bottle_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    bottle = _load_bottle(db, parse_uuid(bottle_id, field="bottle_id"))
    if bottle.author_id != user.id and not user_has(user, *MODERATOR_ROLES):
        raise forbidden()
    if bottle.author_id != user.id:
        add_system_notice(core, user_id=bottle.author_id, body=BOTTLE_REMOVED)
    try:
        delete_bottle_graph(db, bottle)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return None


@router.delete("/bottles/picks/{pick_id}/messages/{message_id}", status_code=204)
def delete_message(
    pick_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    pick, _bottle = _load_pick(db, parse_uuid(pick_id, field="pick_id"))
    parsed_message = parse_uuid(message_id, field="message_id")
    try:
        message = db.get(BottleMessage, parsed_message)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if message is None or message.pick_id != pick.id:
        raise ApiError(404, "not_found", "Message not found.")
    if message.author_id != user.id and not user_has(user, *MODERATOR_ROLES):
        raise forbidden()
    if message.author_id != user.id:
        add_system_notice(core, user_id=message.author_id, body=REPLY_REMOVED)
    try:
        db.delete(message)
        db.flush()
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return None
