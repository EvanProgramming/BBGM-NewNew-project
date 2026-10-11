import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from deps import get_core_db, get_optional_user, get_super_admin
from errors import ApiError, validation_error
from models import CJEntry, Subject, TeamsOAuthState, User, to_iso, utc_now
from routers.cj import _ensure_subjects, _slot, _week_or_error
from teams_cj import (
    UpstreamError,
    authorize_url,
    classify_entries,
    exchange_code,
    fetch_chat_texts,
    load_refresh_token,
    microsoft_ready,
    save_refresh_token,
    state_is_fresh,
    summarize_entries,
)

router = APIRouter()


def _settings(request: Request):
    return request.app.state.settings


def _upstream(exc: UpstreamError) -> ApiError:
    return ApiError(503, "storage_unavailable", exc.message)


def _catalog(db: Session) -> list[dict]:
    rows = db.scalars(select(Subject).order_by(Subject.sort_order, Subject.name)).all()
    return [{"id": row.id, "name": row.name, "short_name": row.short_name} for row in rows]


def _upsert(db: Session, week: str, entry: dict, subjects: dict[str, Subject]) -> None:
    subject = subjects[entry["subject_id"]]
    updated_at = to_iso(utc_now())
    existing = _slot(db, week, entry["day_index"], subject.period, subject.id)
    if existing is None:
        db.add(
            CJEntry(
                id=str(uuid4()),
                week_start=week,
                day_index=entry["day_index"],
                period=subject.period,
                subject_id=subject.id,
                ic=entry["ic"],
                hw=entry["hw"],
                announcement=entry["announcement"],
                updated_at=updated_at,
            )
        )
        return
    existing.ic = entry["ic"]
    existing.hw = entry["hw"]
    existing.announcement = entry["announcement"]
    existing.updated_at = updated_at


@router.get("/cj/teams/status")
def teams_status(
    request: Request,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    settings = _settings(request)
    return {
        "teams_connected": load_refresh_token(db, settings) is not None,
        "deepseek_configured": bool(settings.deepseek_api_key),
        "microsoft_configured": microsoft_ready(settings),
    }


@router.post("/cj/teams/connect")
def teams_connect(
    request: Request,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    settings = _settings(request)
    if not microsoft_ready(settings):
        raise ApiError(503, "storage_unavailable", "Microsoft Teams is not configured.")
    state = secrets.token_urlsafe(32)
    db.add(TeamsOAuthState(state=state, created_at=to_iso(utc_now())))
    db.flush()
    return {"authorize_url": authorize_url(settings, state)}


@router.get("/cj/teams/callback")
def teams_callback(
    request: Request,
    code: str = "",
    state: str = "",
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_core_db),
):
    settings = _settings(request)
    target = f"{settings.frontend_origin}/cj/admin"
    row = db.get(TeamsOAuthState, state) if state else None
    fresh = row is not None and state_is_fresh(row.created_at)
    if row is not None and not fresh:
        db.delete(row)
        db.flush()
    if not fresh or user is None or user.role != "super_admin" or not code:
        return RedirectResponse(f"{target}?teams=error", status_code=302)
    db.delete(row)
    db.flush()
    try:
        refresh = exchange_code(settings, code)
    except UpstreamError:
        return RedirectResponse(f"{target}?teams=error", status_code=302)
    save_refresh_token(db, settings, refresh)
    return RedirectResponse(f"{target}?teams=connected", status_code=302)


@router.post("/cj/teams/preview")
def teams_preview(
    body: dict,
    request: Request,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(str(body.get("week_start") or ""))
    settings = _settings(request)
    if not settings.deepseek_api_key:
        raise ApiError(503, "storage_unavailable", "DeepSeek is not configured.")
    token = load_refresh_token(db, settings)
    if not token:
        raise ApiError(503, "storage_unavailable", "Connect a Teams account before importing.")
    _ensure_subjects(db)
    catalog = _catalog(db)
    try:
        transcript, rotated = fetch_chat_texts(settings, token)
        if rotated:
            save_refresh_token(db, settings, rotated)
        raw = summarize_entries(settings, week, catalog, transcript)
    except UpstreamError as exc:
        raise _upstream(exc) from exc
    entries, skipped = classify_entries({item["id"] for item in catalog}, raw)
    return {"week_start": week, "entries": entries, "skipped": skipped}


@router.post("/cj/teams/apply")
def teams_apply(
    body: dict,
    _: User = Depends(get_super_admin),
    db: Session = Depends(get_core_db),
):
    week = _week_or_error(str(body.get("week_start") or ""))
    raw = body.get("entries")
    if not isinstance(raw, list):
        raise validation_error([{"field": "entries", "message": "Send the previewed CJ entries."}])
    _ensure_subjects(db)
    subjects = {row.id: row for row in db.scalars(select(Subject)).all()}
    entries, skipped = classify_entries(set(subjects), raw)
    for entry in entries:
        _upsert(db, week, entry, subjects)
    db.flush()
    return {"week_start": week, "written": len(entries), "skipped": skipped}
