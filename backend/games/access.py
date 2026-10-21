from fastapi import WebSocket

from security import COOKIE_NAME, unsign_cookie_value
from store import get_session_by_token


def websocket_user(websocket: WebSocket):
    factory = websocket.app.state.core_session_factory
    db = factory()
    try:
        raw = websocket.cookies.get(COOKIE_NAME)
        if not raw:
            return None
        token = unsign_cookie_value(raw, websocket.app.state.settings.session_secret)
        if not token:
            return None
        record = get_session_by_token(db, token)
        if record is None or record.revoked_at is not None:
            return None
        user = record.user
        _ = user.display_name
        return user
    finally:
        db.close()
