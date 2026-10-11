from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mail import peek_console_code
from main import create_app
from models import CJEntry
from teams_cj import UpstreamError, classify_entries
from validate import normalize_email


def _make_app(tmp_path, monkeypatch, name="scoop.db", admin_email=""):
    monkeypatch.setenv("SESSION_SECRET", "pytest-session-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / name}")
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{tmp_path / ('core_' + name)}")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    monkeypatch.setenv("MAIL_BACKEND", "console")
    return create_app()


def _register(client, email, password, display_name):
    sent = client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
    assert sent.status_code == 204, sent.text
    code = peek_console_code(normalize_email(email), "register")
    assert code
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
            "code": code,
            "accept_terms": True,
        },
    )


def _cj_count(app) -> int:
    db = app.state.core_session_factory()
    try:
        return db.scalar(select(func.count()).select_from(CJEntry)) or 0
    finally:
        db.close()


def test_classify_skips_unknown_subject_and_long_fields():
    accepted, skipped = classify_entries(
        {"ap-calculus-11ac"},
        [
            {
                "subject_id": "ap-calculus-11ac",
                "day_index": 0,
                "ic": "Limits",
                "hw": "FRQ",
                "announcement": "Quiz",
            },
            {
                "subject_id": "not-a-course",
                "day_index": 0,
                "ic": "x",
                "hw": "y",
                "announcement": "z",
            },
            {
                "subject_id": "ap-calculus-11ac",
                "day_index": 1,
                "ic": "x" * 801,
                "hw": "",
                "announcement": "",
            },
        ],
    )
    assert accepted == [
        {
            "subject_id": "ap-calculus-11ac",
            "day_index": 0,
            "ic": "Limits",
            "hw": "FRQ",
            "announcement": "Quiz",
        }
    ]
    assert {item["reason"] for item in skipped} == {"unknown_subject", "field_too_long"}


def test_teams_import_is_super_admin_only(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="sasha.lin@basischina.com")
    with (
        TestClient(app) as anonymous,
        TestClient(app) as super_client,
        TestClient(app) as student_client,
        TestClient(app) as teacher_client,
    ):
        _register(super_client, "sasha.lin@basischina.com", "super-desk-41", "Sasha Lin")
        teacher = _register(teacher_client, "evan.wu@basischina.com", "teacher-lab-43", "Evan Wu")
        _register(student_client, "mia.chen@basischina.com", "student-hall-42", "Mia Chen")
        promoted = super_client.patch(
            f"/api/v1/admin/users/{teacher.json()['id']}",
            json={"role": "teacher"},
        )
        assert promoted.status_code == 200, promoted.text
        assert teacher_client.post("/api/v1/auth/logout").status_code == 204
        login = teacher_client.post(
            "/api/v1/auth/login",
            json={"email": "evan.wu@basischina.com", "password": "teacher-lab-43"},
        )
        assert login.status_code == 200, login.text

        for client in (student_client, teacher_client):
            assert client.get("/api/v1/cj/teams/status").status_code == 403
            assert client.post("/api/v1/cj/teams/connect").status_code == 403
            assert client.post("/api/v1/cj/teams/preview", json={"week_start": "2026-10-05"}).status_code == 403
            assert client.post(
                "/api/v1/cj/teams/apply",
                json={"week_start": "2026-10-05", "entries": []},
            ).status_code == 403
        assert anonymous.get("/api/v1/cj/teams/status").status_code == 401

        status = super_client.get("/api/v1/cj/teams/status")
        assert status.status_code == 200, status.text
        assert status.json() == {
            "teams_connected": False,
            "deepseek_configured": False,
            "microsoft_configured": False,
        }
        blocked = super_client.post("/api/v1/cj/teams/preview", json={"week_start": "2026-10-05"})
        assert blocked.status_code == 503
        assert _cj_count(app) == 0
    app.state.engine.dispose()


def test_preview_skips_invalid_entries_and_apply_writes_the_rest(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "app-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "app-secret")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MICROSOFT_REDIRECT_URI", "http://localhost:8000/api/v1/cj/teams/callback")
    app = _make_app(tmp_path, monkeypatch, name="teams.db", admin_email="sasha.lin@basischina.com")

    def fail_fetch(_settings, _token):
        raise UpstreamError("Teams chats could not be read.")

    def read_chats(_settings, token):
        assert token == "refresh-secret-value"
        return "Monday calculus: limits and an FRQ set", None

    def summarize(_settings, week, catalog, transcript):
        assert week == "2026-10-05"
        assert "FRQ" in transcript
        assert any(item["id"] == "ap-calculus-11ac" for item in catalog)
        return [
            {
                "subject_id": "ap-calculus-11ac",
                "day_index": 0,
                "ic": "Limits",
                "hw": "FRQ",
                "announcement": "Quiz",
            },
            {
                "subject_id": "not-a-course",
                "day_index": 0,
                "ic": "skip me",
                "hw": "skip me",
                "announcement": "skip me",
            },
        ]

    monkeypatch.setattr("routers.teams.exchange_code", lambda _settings, _code: "refresh-secret-value")
    monkeypatch.setattr("routers.teams.fetch_chat_texts", fail_fetch)

    with TestClient(app) as super_client:
        _register(super_client, "sasha.lin@basischina.com", "super-desk-41", "Sasha Lin")
        connect = super_client.post("/api/v1/cj/teams/connect")
        assert connect.status_code == 200, connect.text
        authorize = connect.json()["authorize_url"]
        assert "client_id=app-id" in authorize
        assert "app-secret" not in authorize
        assert "sk-test-not-real" not in authorize
        state = parse_qs(urlparse(authorize).query)["state"][0]
        callback = super_client.get(
            f"/api/v1/cj/teams/callback?code=auth-code&state={state}",
            follow_redirects=False,
        )
        assert callback.status_code == 302
        assert callback.headers["location"].endswith("/cj/admin?teams=connected")
        assert "refresh-secret-value" not in callback.headers["location"]

        status = super_client.get("/api/v1/cj/teams/status")
        assert status.status_code == 200, status.text
        assert status.json()["teams_connected"] is True
        assert "refresh-secret-value" not in status.text
        assert "app-secret" not in status.text
        assert "sk-test-not-real" not in status.text

        failed = super_client.post("/api/v1/cj/teams/preview", json={"week_start": "2026-10-05"})
        assert failed.status_code == 503, failed.text
        assert _cj_count(app) == 0

        monkeypatch.setattr("routers.teams.fetch_chat_texts", read_chats)
        monkeypatch.setattr("routers.teams.summarize_entries", summarize)
        preview = super_client.post("/api/v1/cj/teams/preview", json={"week_start": "2026-10-05"})
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body["entries"] == [
            {
                "subject_id": "ap-calculus-11ac",
                "day_index": 0,
                "ic": "Limits",
                "hw": "FRQ",
                "announcement": "Quiz",
            }
        ]
        assert body["skipped"][0]["reason"] == "unknown_subject"
        assert "sk-test-not-real" not in preview.text
        assert _cj_count(app) == 0

        applied = super_client.post(
            "/api/v1/cj/teams/apply",
            json={
                "week_start": "2026-10-05",
                "entries": body["entries"]
                + [
                    {
                        "subject_id": "not-a-course",
                        "day_index": 1,
                        "ic": "no",
                        "hw": "no",
                        "announcement": "no",
                    }
                ],
            },
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["written"] == 1
        assert applied.json()["skipped"][0]["reason"] == "unknown_subject"
        assert _cj_count(app) == 1

        saved = super_client.get("/api/v1/cj?week_start=2026-10-05")
        assert saved.status_code == 200, saved.text
        match = [
            entry
            for entry in saved.json()["entries"]
            if entry["subject_id"] == "ap-calculus-11ac" and entry["day_index"] == 0
        ]
        assert match[0]["ic"] == "Limits"
        assert match[0]["hw"] == "FRQ"
        assert match[0]["announcement"] == "Quiz"
    app.state.engine.dispose()
