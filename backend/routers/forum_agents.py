from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from deps import get_core_db, get_db, get_super_admin
from errors import ApiError, StorageError, validation_error
from forum_agents import (
    action_payload,
    agent_payload,
    manual_act,
    shanghai_day,
    valid_clock,
)
from identity import dump_roles, primary_role
from models import ForumAgent, ForumAgentAction, User, utc_now
from schemas import DEFAULT_AVATAR
from security import hash_password
from store import get_user_by_email
from validate import email_field_error, normalize_email, parse_uuid

router = APIRouter()


class CreateAgentBody(BaseModel):
    email: str
    password: str
    display_name: str
    personality: str
    hobbies: str
    tone: str
    enabled: bool = False
    posts_per_day: int = 1
    comments_per_day: int = 3
    likes_per_day: int = 5
    min_interval_minutes: int = 30
    active_start: str = "08:00"
    active_end: str = "22:00"


class PatchAgentBody(BaseModel):
    enabled: bool | None = None
    personality: str | None = None
    hobbies: str | None = None
    tone: str | None = None
    posts_per_day: int | None = None
    comments_per_day: int | None = None
    likes_per_day: int | None = None
    min_interval_minutes: int | None = None
    active_start: str | None = None
    active_end: str | None = None


def _text_error(field: str, value: str) -> dict | None:
    text = value.strip()
    if not text or len(text) > 500:
        return {"field": field, "message": "Use 1–500 characters."}
    return None


def _count_error(field: str, value: int) -> dict | None:
    if value < 0 or value > 20:
        return {"field": field, "message": "Use a number from 0 to 20."}
    return None


def _window_errors(start: str, end: str) -> list[dict]:
    fields = []
    if not valid_clock(start):
        fields.append({"field": "active_start", "message": "Use HH:MM."})
    if not valid_clock(end):
        fields.append({"field": "active_end", "message": "Use HH:MM."})
    if not fields and start >= end:
        fields.append({"field": "active_end", "message": "End must be later than start."})
    return fields


def _load(db: Session, agent_id: str) -> ForumAgent:
    try:
        agent = db.get(ForumAgent, agent_id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    if agent is None:
        raise ApiError(404, "not_found", "Forum agent not found.")
    return agent


@router.get("/admin/forum-agents")
def list_agents(_: User = Depends(get_super_admin), db: Session = Depends(get_core_db)):
    try:
        agents = list(db.scalars(select(ForumAgent).order_by(ForumAgent.created_at.desc())).all())
        actions = list(
            db.scalars(select(ForumAgentAction).order_by(ForumAgentAction.created_at.desc()).limit(200)).all()
        )
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_([row.user_id for row in agents]))).all()} if agents else {}
    return {
        "items": [agent_payload(row, users[row.user_id]) for row in agents if row.user_id in users],
        "actions": [action_payload(row) for row in actions],
    }


@router.post("/admin/forum-agents", status_code=201)
def create_agent(body: CreateAgentBody, db: Session = Depends(get_core_db), _: User = Depends(get_super_admin)):
    fields = []
    email_error = email_field_error(body.email)
    if email_error:
        fields.append(email_error)
    if len(body.password) < 8 or len(body.password) > 128:
        fields.append({"field": "password", "message": "Password must be 8–128 characters."})
    name = body.display_name.strip()
    if not name or len(name) > 40:
        fields.append({"field": "display_name", "message": "Display name must be 1–40 characters."})
    for field in ("personality", "hobbies", "tone"):
        error = _text_error(field, getattr(body, field))
        if error:
            fields.append(error)
    for field in ("posts_per_day", "comments_per_day", "likes_per_day"):
        error = _count_error(field, getattr(body, field))
        if error:
            fields.append(error)
    if body.min_interval_minutes < 1 or body.min_interval_minutes > 1440:
        fields.append({"field": "min_interval_minutes", "message": "Use 1–1440 minutes."})
    fields.extend(_window_errors(body.active_start, body.active_end))
    if fields:
        raise validation_error(fields)
    email = normalize_email(body.email)
    if get_user_by_email(db, email) is not None:
        raise ApiError(
            409,
            "email_taken",
            "An account with this email already exists.",
            [{"field": "email", "message": "This email is already registered."}],
        )
    now = utc_now()
    user = User(
        id=str(uuid4()),
        email=email,
        password_hash=hash_password(body.password),
        display_name=name,
        role=primary_role(["student"]),
        roles=dump_roles(["student"]),
        muted=False,
        avatar=DEFAULT_AVATAR,
        terms_accepted_at=now,
        created_at=now,
    )
    agent = ForumAgent(
        id=str(uuid4()),
        user_id=user.id,
        enabled=body.enabled,
        personality=body.personality.strip(),
        hobbies=body.hobbies.strip(),
        tone=body.tone.strip(),
        posts_per_day=body.posts_per_day,
        comments_per_day=body.comments_per_day,
        likes_per_day=body.likes_per_day,
        min_interval_minutes=body.min_interval_minutes,
        active_start=body.active_start,
        active_end=body.active_end,
        last_acted_at=None,
        count_day=shanghai_day(now),
        posts_today=0,
        comments_today=0,
        likes_today=0,
        created_at=now,
    )
    try:
        db.add(user)
        db.flush()
        db.add(agent)
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            409,
            "email_taken",
            "An account with this email already exists.",
            [{"field": "email", "message": "This email is already registered."}],
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError() from exc
    return agent_payload(agent, user)


@router.patch("/admin/forum-agents/{agent_id}")
def patch_agent(
    agent_id: str,
    body: PatchAgentBody,
    db: Session = Depends(get_core_db),
    _: User = Depends(get_super_admin),
):
    agent_id = parse_uuid(agent_id, "id")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise validation_error([{"field": "enabled", "message": "Change at least one field."}])
    fields = []
    for field in ("personality", "hobbies", "tone"):
        if field in changes:
            error = _text_error(field, changes[field] or "")
            if error:
                fields.append(error)
    for field in ("posts_per_day", "comments_per_day", "likes_per_day"):
        if field in changes:
            error = _count_error(field, changes[field])
            if error:
                fields.append(error)
    if "min_interval_minutes" in changes and (
        changes["min_interval_minutes"] < 1 or changes["min_interval_minutes"] > 1440
    ):
        fields.append({"field": "min_interval_minutes", "message": "Use 1–1440 minutes."})
    start = changes.get("active_start")
    end = changes.get("active_end")
    if start is not None or end is not None:
        agent = _load(db, agent_id)
        fields.extend(_window_errors(start or agent.active_start, end or agent.active_end))
    else:
        agent = _load(db, agent_id)
    if fields:
        raise validation_error(fields)
    for field, value in changes.items():
        setattr(agent, field, value.strip() if isinstance(value, str) else value)
    try:
        db.flush()
        user = db.get(User, agent.user_id)
    except SQLAlchemyError as exc:
        raise StorageError() from exc
    return agent_payload(agent, user)


@router.post("/admin/forum-agents/{agent_id}/act")
def act_agent(
    agent_id: str,
    request: Request,
    core: Session = Depends(get_core_db),
    content: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    agent = _load(core, parse_uuid(agent_id, "id"))
    action = manual_act(core, content, request.app.state.settings, agent)
    user = core.get(User, agent.user_id)
    return {"agent": agent_payload(agent, user), "action": action_payload(action)}


@router.post("/admin/forum-agents/{agent_id}/post")
def post_once(
    agent_id: str,
    request: Request,
    core: Session = Depends(get_core_db),
    content: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return _direct(agent_id, request, core, content, "post")


@router.post("/admin/forum-agents/{agent_id}/comment")
def comment_once(
    agent_id: str,
    request: Request,
    core: Session = Depends(get_core_db),
    content: Session = Depends(get_db),
    _: User = Depends(get_super_admin),
):
    return _direct(agent_id, request, core, content, "comment")


def _direct(agent_id: str, request: Request, core: Session, content: Session, kind: str):
    agent = _load(core, parse_uuid(agent_id, "id"))
    action = manual_act(core, content, request.app.state.settings, agent, kind=kind)
    user = core.get(User, agent.user_id)
    return {"agent": agent_payload(agent, user), "action": action_payload(action)}
