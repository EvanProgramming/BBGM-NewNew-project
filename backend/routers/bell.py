import re
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from deps import get_core_db, get_current_user, get_db, require_not_muted
from errors import ApiError, forbidden, validation_error
from models import BellRound, BellTrack, BellVote, User, to_iso, utc_now
from qqmusic import QqUnavailable, fetch_cover, fetch_song, search_songs
from store import users_by_ids
from validate import parse_uuid

router = APIRouter()

_SHANGHAI = ZoneInfo("Asia/Shanghai")

_SONG_ID = re.compile(r"^[0-9A-Za-z]{14}$")
_ALBUM_MID = re.compile(r"^[0-9A-Za-z]{1,32}$")
_CLOSED = [{"field": "round", "message": "This round is closed."}]
_NOT_STARTED = [{"field": "round", "message": "Voting has not started."}]
_HOLDING_VOTE = [{"field": "track_id", "message": "Withdraw your vote before choosing another song."}]
_HOLDING_SONG = [{"field": "song_id", "message": "Withdraw your vote before choosing another song."}]
_ALREADY_ADDED = [{"field": "song_id", "message": "You already added a song this round."}]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _settle(db: Session) -> None:
    now = utc_now()
    changed = False
    rows = db.scalars(select(BellRound).where(BellRound.status == "open")).all()
    for row in rows:
        if _as_utc(row.ends_at) <= now:
            row.status = "closed"
            row.closed_at = now
            changed = True
    if changed:
        db.flush()


def _open_round(db: Session) -> BellRound | None:
    _settle(db)
    return db.scalar(
        select(BellRound).where(BellRound.status == "open").order_by(BellRound.created_at.desc())
    )


def _latest_round(db: Session) -> BellRound | None:
    _settle(db)
    return db.scalar(select(BellRound).order_by(BellRound.created_at.desc()))


def _require_open(db: Session) -> BellRound:
    row = _open_round(db)
    if row is not None:
        return row
    if _latest_round(db) is not None:
        raise validation_error(_CLOSED)
    raise ApiError(404, "not_found", "There is no open round.")


def _parse_when(value, field: str) -> datetime:
    label = "start" if field == "starts_at" else "end"
    if not isinstance(value, str):
        raise validation_error([{"field": field, "message": f"Enter a {label} time."}])
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise validation_error(
            [{"field": field, "message": "Use a UTC time like 2026-11-01T00:00:00Z."}]
        ) from exc
    if parsed <= utc_now():
        raise validation_error([{"field": field, "message": f"The {label} must be in the future."}])
    return parsed


def _vote_day(moment: datetime | None = None) -> str:
    current = _as_utc(moment or utc_now())
    return current.astimezone(_SHANGHAI).date().isoformat()


def _today_vote(db: Session, round_id: str, user_id: str) -> BellVote | None:
    return db.scalar(
        select(BellVote).where(
            BellVote.round_id == round_id,
            BellVote.user_id == user_id,
            BellVote.vote_day == _vote_day(),
        )
    )


def _require_voting(db: Session) -> BellRound:
    row = _require_open(db)
    if _as_utc(row.starts_at) > utc_now():
        raise validation_error(_NOT_STARTED)
    return row


def _counts(db: Session, round_id: str) -> dict[str, int]:
    rows = db.execute(
        select(BellVote.track_id, func.count())
        .where(BellVote.round_id == round_id)
        .group_by(BellVote.track_id)
    ).all()
    return {track_id: int(count) for track_id, count in rows}


def _ordered_tracks(db: Session, round_id: str) -> list[BellTrack]:
    tracks = list(db.scalars(select(BellTrack).where(BellTrack.round_id == round_id)).all())
    counts = _counts(db, round_id)
    tracks.sort(key=lambda track: (-counts.get(track.id, 0), _as_utc(track.created_at), track.id))
    return tracks


def _bell_admin(user: User, request: Request) -> bool:
    admin_email = request.app.state.settings.admin_email
    return bool(admin_email) and user.email == admin_email


def _require_bell_admin(user: User, request: Request) -> None:
    if not _bell_admin(user, request):
        raise forbidden()


def _forget_earlier_rounds(db: Session, keep_id: str) -> None:
    earlier = list(db.scalars(select(BellRound.id).where(BellRound.id != keep_id)).all())
    if not earlier:
        return
    db.execute(delete(BellVote).where(BellVote.round_id.in_(earlier)))
    db.execute(delete(BellTrack).where(BellTrack.round_id.in_(earlier)))
    db.execute(delete(BellRound).where(BellRound.id.in_(earlier)))
    db.flush()


def _history(db: Session, can_manage: bool) -> list[dict]:
    if not can_manage:
        return []
    _settle(db)
    rows = db.scalars(select(BellRound).order_by(BellRound.created_at.desc())).all()
    return [
        {
            "id": row.id,
            "status": row.status,
            "starts_at": to_iso(_as_utc(row.starts_at)),
            "ends_at": to_iso(_as_utc(row.ends_at)),
            "closed_at": to_iso(_as_utc(row.closed_at)) if row.closed_at else None,
        }
        for row in rows
    ]


def _board(db: Session, core: Session, user: User, row: BellRound | None, request: Request) -> dict:
    can_manage = _bell_admin(user, request)
    history = _history(db, can_manage)
    if row is None:
        return {
            "round": None,
            "tracks": [],
            "my_track_id": None,
            "my_vote_track_id": None,
            "can_manage": can_manage,
            "history": history,
        }
    tracks = _ordered_tracks(db, row.id)
    counts = _counts(db, row.id)
    people = users_by_ids(core, [track.author_id for track in tracks])
    closed = row.status == "closed"
    my_track_id = None
    qualified_ids = []
    items = []
    for index, track in enumerate(tracks, start=1):
        if track.author_id == user.id:
            my_track_id = track.id
        author = people.get(track.author_id)
        qualified = closed and index <= 4
        if qualified:
            qualified_ids.append(track.id)
        items.append(
            {
                "id": track.id,
                "song_id": track.song_id,
                "title": track.title,
                "artists": track.artists,
                "external_url": track.external_url,
                "cover_url": track.cover_url or "",
                "vote_count": counts.get(track.id, 0),
                "rank": index,
                "qualified": qualified,
                "nominated_by": {"display_name": author.display_name if author else ""},
                "mine": track.author_id == user.id,
            }
        )
    vote = _today_vote(db, row.id, user.id)
    return {
        "round": {
            "id": row.id,
            "status": row.status,
            "starts_at": to_iso(_as_utc(row.starts_at)),
            "ends_at": to_iso(_as_utc(row.ends_at)),
            "closed_at": to_iso(_as_utc(row.closed_at)) if row.closed_at else None,
            "qualified_track_ids": qualified_ids,
        },
        "tracks": items,
        "my_track_id": my_track_id,
        "my_vote_track_id": vote.track_id if vote else None,
        "can_manage": can_manage,
        "history": history,
    }


def _visible(db: Session) -> BellRound | None:
    return _open_round(db) or _latest_round(db)


def _catalog_error() -> ApiError:
    return ApiError(503, "qq_unavailable", "QQ Music could not be reached.")


@router.get("/bell")
def get_bell(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    return _board(db, core, user, _visible(db), request)


@router.get("/bell/covers/{album_mid}")
def bell_cover(album_mid: str, _user: User = Depends(get_current_user)) -> Response:
    if not _ALBUM_MID.fullmatch(album_mid):
        raise ApiError(404, "not_found", "That cover was not found.")
    try:
        body, media_type = fetch_cover(album_mid)
    except QqUnavailable as exc:
        raise _catalog_error() from exc
    return Response(content=body, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"})


@router.get("/bell/search")
def search_bell(
    q: str = Query(default=""),
    user: User = Depends(get_current_user),
):
    del user
    query = q.strip()
    if not query or len(query) > 80:
        raise validation_error([{"field": "q", "message": "Enter 1 to 80 characters."}])
    try:
        items = search_songs(query)
    except QqUnavailable as exc:
        raise _catalog_error() from exc
    return {"items": items}


@router.post("/bell/tracks", status_code=201)
def add_track(
    body: dict,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    row = _require_open(db)
    song_id = body.get("song_id") if isinstance(body, dict) else None
    if not isinstance(song_id, str) or not _SONG_ID.fullmatch(song_id):
        raise validation_error(
            [{"field": "song_id", "message": "Choose a song from the results."}]
        )
    manager = _bell_admin(user, request)
    if not manager:
        mine = db.scalar(
            select(BellTrack).where(BellTrack.round_id == row.id, BellTrack.author_id == user.id)
        )
        if mine is not None:
            raise validation_error(_ALREADY_ADDED)
    existing = db.scalar(
        select(BellTrack).where(BellTrack.round_id == row.id, BellTrack.song_id == song_id)
    )
    if existing is not None:
        raise ApiError(
            409,
            "track_taken",
            "This song is already in this round. Vote for it.",
            [{"field": "song_id", "message": existing.id}],
        )
    held = _today_vote(db, row.id, user.id)
    if held is not None and not manager:
        raise validation_error(_HOLDING_SONG)
    try:
        found = fetch_song(song_id)
    except QqUnavailable as exc:
        raise _catalog_error() from exc
    expected = f"https://y.qq.com/n/ryqq/songDetail/{song_id}"
    if found is None or found.get("song_id") != song_id:
        raise validation_error(
            [{"field": "song_id", "message": "QQ Music does not have this song."}]
        )
    if found.get("external_url") != expected:
        raise validation_error(
            [{"field": "song_id", "message": "QQ Music does not have this song."}]
        )
    track_id = str(uuid4())
    db.add(
        BellTrack(
            id=track_id,
            round_id=row.id,
            song_id=song_id,
            title=found["title"],
            artists=found["artists"],
            external_url=expected,
            cover_url=found.get("cover_url") or "",
            author_id=user.id,
            created_at=utc_now(),
        )
    )
    if held is None:
        db.add(
            BellVote(
                id=str(uuid4()),
                round_id=row.id,
                track_id=track_id,
                user_id=user.id,
                vote_day=_vote_day(),
                created_at=utc_now(),
            )
        )
    db.flush()
    return _board(db, core, user, row, request)


@router.post("/bell/votes")
def cast_vote(
    body: dict,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    row = _require_voting(db)
    raw_id = body.get("track_id") if isinstance(body, dict) else None
    track_id = parse_uuid(raw_id if isinstance(raw_id, str) else "", "track_id")
    track = db.get(BellTrack, track_id)
    if track is None or track.round_id != row.id:
        raise ApiError(404, "not_found", "That song is not in this round.")
    vote = _today_vote(db, row.id, user.id)
    if vote is not None and vote.track_id != track.id:
        raise validation_error(_HOLDING_VOTE)
    if vote is None:
        db.add(
            BellVote(
                id=str(uuid4()),
                round_id=row.id,
                track_id=track.id,
                user_id=user.id,
                vote_day=_vote_day(),
                created_at=utc_now(),
            )
        )
        db.flush()
    return _board(db, core, user, row, request)


@router.delete("/bell/votes")
def withdraw_vote(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    require_not_muted(user)
    row = _require_voting(db)
    vote = _today_vote(db, row.id, user.id)
    if vote is not None:
        db.delete(vote)
        db.flush()
    return _board(db, core, user, row, request)


@router.delete("/bell/tracks/{track_id}")
def remove_track(
    track_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    row = _require_open(db)
    track = db.get(BellTrack, parse_uuid(track_id, "id"))
    if track is None or track.round_id != row.id:
        raise ApiError(404, "not_found", "That song is not in this round.")
    if not _bell_admin(user, request):
        if track.author_id != user.id:
            raise forbidden()
        require_not_muted(user)
    db.execute(delete(BellVote).where(BellVote.track_id == track.id))
    db.delete(track)
    db.flush()
    return _board(db, core, user, row, request)


@router.post("/bell/rounds", status_code=201)
def open_round(
    body: dict,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    _require_bell_admin(user, request)
    if _open_round(db) is not None:
        raise ApiError(409, "round_open", "A round is already open.")
    payload = body if isinstance(body, dict) else {}
    starts_at = _parse_when(payload.get("starts_at"), "starts_at")
    ends_at = _parse_when(payload.get("ends_at"), "ends_at")
    if ends_at <= starts_at:
        raise validation_error([{"field": "ends_at", "message": "The end must be after the start."}])
    row = BellRound(
        id=str(uuid4()),
        status="open",
        starts_at=starts_at,
        ends_at=ends_at,
        closed_at=None,
        created_at=utc_now(),
    )
    db.add(row)
    db.flush()
    _forget_earlier_rounds(db, row.id)
    return _board(db, core, user, row, request)


@router.post("/bell/rounds/{round_id}/close")
def close_round(
    round_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    core: Session = Depends(get_core_db),
):
    _require_bell_admin(user, request)
    row = db.get(BellRound, parse_uuid(round_id, "id"))
    if row is None:
        raise ApiError(404, "not_found", "That round was not found.")
    if row.status != "closed":
        row.status = "closed"
        row.closed_at = utc_now()
        db.flush()
    return _board(db, core, user, _visible(db), request)
