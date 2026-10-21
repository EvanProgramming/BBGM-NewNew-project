import hashlib
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import avatars
from errors import StorageError
from mail import peek_console_code
from main import create_app
from models import AuditEvent, Post, User, utc_now
from security import hash_password
from validate import normalize_email


def _make_app(tmp_path, monkeypatch, name="scoop.db", admin_email=""):
    monkeypatch.setenv("SESSION_SECRET", "pytest-session-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / name}")
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{tmp_path / ('core_' + name)}")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    monkeypatch.setenv("MAIL_BACKEND", "console")
    monkeypatch.setenv("CJ_JOURNAL_BASE_URL", "")
    monkeypatch.setenv("CJ_JOURNAL_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    return create_app()


def _publish_news(client, title, body, heading="Story"):
    created = client.post("/api/v1/news/drafts", json={"title": title})
    assert created.status_code == 201, created.text
    draft_id = created.json()["id"]
    added = client.post(
        f"/api/v1/news/drafts/{draft_id}/blocks",
        json={"heading": heading, "body": body},
    )
    assert added.status_code == 201, added.text
    block_id = added.json()["blocks"][0]["id"]
    submitted = client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{block_id}/submit")
    assert submitted.status_code == 200, submitted.text
    approved = client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{block_id}/approve")
    assert approved.status_code == 200, approved.text
    return draft_id


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


def test_single_sqlite_file_deletes_user_and_post(tmp_path, monkeypatch):
    db_path = tmp_path / "scoop.db"
    monkeypatch.setenv("SESSION_SECRET", "pytest-session-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("ADMIN_EMAIL", "ada.min@basischina.com")
    monkeypatch.setenv("MAIL_BACKEND", "console")
    monkeypatch.setenv("CJ_JOURNAL_BASE_URL", "")
    monkeypatch.setenv("CJ_JOURNAL_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    app = create_app()
    assert app.state.shared_database is True
    with TestClient(app) as client:
        admin = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert admin.status_code == 201, admin.text
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert student.status_code == 201, student.text
        student_id = student.json()["id"]
        created = client.post(
            "/api/v1/posts",
            json={"title": "Locker note", "body": "Left on the board.", "category": "forum"},
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]

        client.cookies.clear()
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        assert login.status_code == 200, login.text
        removed_post = client.delete(f"/api/v1/posts/{post_id}")
        assert removed_post.status_code == 204, removed_post.text
        assert client.get(f"/api/v1/posts/{post_id}").status_code == 404

        removed_user = client.delete(f"/api/v1/admin/users/{student_id}")
        assert removed_user.status_code == 204, removed_user.text
        client.cookies.clear()
        gone = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert gone.status_code == 401
    app.state.engine.dispose()


def test_missing_session_secret_fails_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scoop.db'}")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    try:
        create_app()
        raise AssertionError("expected startup to fail")
    except RuntimeError as exc:
        assert "SESSION_SECRET" in str(exc)


def test_news_submission_stays_private_until_design_publish(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, name="news_publish.db", admin_email="news.admin@basischina.com")
    with TestClient(app) as client:
        _register(client, "news.admin@basischina.com", "news-desk-41", "News Admin")
        created = client.post(
            "/api/v1/news/submissions",
            data={"title": "Scoop goes live", "body": "The original story body.", "topics": '["scoop"]'},
        )
        assert created.status_code == 201, created.text
        article_id = created.json()["id"]

        pending = client.post(f"/api/v1/news/submissions/{article_id}/submit", json={"mode": "original"})
        assert pending.status_code == 200, pending.text
        assert pending.json()["status"] == "pending"
        assert client.get("/api/v1/news/articles?topic=scoop").json()["total"] == 0

        published = client.post(
            f"/api/v1/news/submissions/{article_id}/publish",
            json={"mode": "original"},
        )
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "published"
        listing = client.get("/api/v1/news/articles?topic=scoop").json()
        assert listing["total"] == 1
        assert listing["items"][0]["id"] == article_id
        detail = client.get(f"/api/v1/news/articles/{article_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["body"] == "The original story body."


def test_editor_review_publishes_into_homepage_categories(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, name="news_review_home.db", admin_email="desk.admin@basischina.com")
    with TestClient(app) as client:
        _register(client, "desk.admin@basischina.com", "news-desk-41", "Desk Admin")
        editor = _register(client, "copy.editor@basischina.com", "news-desk-42", "Copy Editor")
        editor_id = editor.json()["id"]
        client.post(
            "/api/v1/auth/login",
            json={"email": "desk.admin@basischina.com", "password": "news-desk-41"},
        )
        granted = client.patch(f"/api/v1/admin/users/{editor_id}", json={"roles": ["editor"]})
        assert granted.status_code == 200, granted.text

        client.post(
            "/api/v1/auth/login",
            json={"email": "copy.editor@basischina.com", "password": "news-desk-42"},
        )
        created = client.post(
            "/api/v1/news/submissions",
            data={"title": "Dorm lights out", "body": "The original dorm story.", "topics": '["dorm", "sport"]'},
        )
        assert created.status_code == 201, created.text
        article_id = created.json()["id"]
        denied_design = client.post(f"/api/v1/news/submissions/{article_id}/format")
        assert denied_design.status_code == 403
        pending = client.post(f"/api/v1/news/submissions/{article_id}/submit", json={"mode": "original"})
        assert pending.status_code == 200, pending.text
        assert client.get("/api/v1/news/articles?topic=dorm").json()["total"] == 0
        assert client.get("/api/v1/news/articles?topic=sport").json()["total"] == 0

        client.post(
            "/api/v1/auth/login",
            json={"email": "desk.admin@basischina.com", "password": "news-desk-41"},
        )
        queue = client.get("/api/v1/news/review")
        assert queue.status_code == 200, queue.text
        assert [item["id"] for item in queue.json()["items"]] == [article_id]

        approved = client.post(f"/api/v1/news/submissions/{article_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "published"

        for topic in ("all", "dorm", "sport"):
            listing = client.get(f"/api/v1/news/articles?topic={topic}").json()
            assert listing["total"] == 1
            assert listing["items"][0]["id"] == article_id
            assert set(listing["items"][0]["news_categories"]) == {"dorm", "sport"}
        assert client.get("/api/v1/news/articles?topic=scoop").json()["total"] == 0
        detail = client.get(f"/api/v1/posts/{article_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["body"] == "The original dorm story."
        assert set(detail.json()["news_categories"]) == {"dorm", "sport"}


def test_admin_can_withdraw_published_news_from_the_front_page(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, name="news_withdraw.db", admin_email="desk.admin@basischina.com")
    with TestClient(app) as client:
        _register(client, "desk.admin@basischina.com", "news-desk-41", "Desk Admin")
        editor = _register(client, "copy.editor@basischina.com", "news-desk-42", "Copy Editor")
        editor_id = editor.json()["id"]
        client.post(
            "/api/v1/auth/login",
            json={"email": "desk.admin@basischina.com", "password": "news-desk-41"},
        )
        granted = client.patch(f"/api/v1/admin/users/{editor_id}", json={"roles": ["editor"]})
        assert granted.status_code == 200, granted.text

        client.post(
            "/api/v1/auth/login",
            json={"email": "copy.editor@basischina.com", "password": "news-desk-42"},
        )
        created = client.post(
            "/api/v1/news/submissions",
            data={"title": "Dorm lights out", "body": "The original dorm story.", "topics": '["dorm"]'},
        )
        assert created.status_code == 201, created.text
        article_id = created.json()["id"]
        denied = client.post(f"/api/v1/news/submissions/{article_id}/withdraw")
        assert denied.status_code == 403

        client.post(
            "/api/v1/auth/login",
            json={"email": "desk.admin@basischina.com", "password": "news-desk-41"},
        )
        moderator = _register(client, "page.admin@basischina.com", "news-desk-43", "Page Admin")
        moderator_id = moderator.json()["id"]
        client.post(
            "/api/v1/auth/login",
            json={"email": "desk.admin@basischina.com", "password": "news-desk-41"},
        )
        made_admin = client.patch(f"/api/v1/admin/users/{moderator_id}", json={"roles": ["admin"]})
        assert made_admin.status_code == 200, made_admin.text
        published = client.post(
            f"/api/v1/news/submissions/{article_id}/publish",
            json={"mode": "original"},
        )
        assert published.status_code == 200, published.text
        assert client.get("/api/v1/news/articles?topic=dorm").json()["total"] == 1

        client.post(
            "/api/v1/auth/login",
            json={"email": "page.admin@basischina.com", "password": "news-desk-43"},
        )
        too_soon = client.post(f"/api/v1/news/submissions/{article_id}/withdraw")
        assert too_soon.status_code == 200, too_soon.text
        assert too_soon.json()["status"] == "draft"
        assert too_soon.json()["body"] == "The original dorm story."
        assert client.get("/api/v1/news/articles?topic=dorm").json()["total"] == 0
        assert client.get("/api/v1/news/articles?topic=all").json()["total"] == 0
        assert client.get(f"/api/v1/posts/{article_id}").status_code == 404
        again = client.post(f"/api/v1/news/submissions/{article_id}/withdraw")
        assert again.status_code == 422
        assert again.json()["error"]["fields"][0]["field"] == "status"


def test_news_draft_can_append_and_remove_multiple_images(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, name="news_images.db", admin_email="images.admin@basischina.com")
    monkeypatch.setattr(avatars, "POST_IMAGE_DIR", tmp_path / "posts")
    with TestClient(app) as client:
        _register(client, "images.admin@basischina.com", "news-desk-42", "Images Admin")
        created = client.post(
            "/api/v1/news/submissions",
            data={"title": "Photo story", "body": "Several images belong here.", "topics": '["dorm"]'},
        )
        assert created.status_code == 201, created.text
        article_id = created.json()["id"]

        added = client.post(
            f"/api/v1/news/submissions/{article_id}/images",
            files=[
                ("images", ("one.jpg", b"image one", "image/jpeg")),
                ("images", ("two.png", b"image two", "image/png")),
            ],
        )
        assert added.status_code == 200, added.text
        assert len(added.json()["images"]) == 2

        appended = client.post(
            f"/api/v1/news/submissions/{article_id}/images",
            files=[
                ("images", ("three.jpg", b"image three", "image/jpeg")),
                ("images", ("four.jpg", b"image four", "image/jpeg")),
                ("images", ("five.jpg", b"image five", "image/jpeg")),
            ],
        )
        assert appended.status_code == 200, appended.text
        image_paths = appended.json()["images"]
        assert len(image_paths) == 5
        removed_file = avatars.POST_IMAGE_DIR / article_id / image_paths[1].rsplit("/", 1)[-1]
        assert removed_file.exists()

        removed = client.request(
            "DELETE",
            f"/api/v1/news/submissions/{article_id}/images",
            json={"image": image_paths[1]},
        )
        assert removed.status_code == 200, removed.text
        assert len(removed.json()["images"]) == 4
        assert image_paths[1] not in removed.json()["images"]
        assert not removed_file.exists()


def test_register_login_create_post_public_read_and_persist(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="jordan.hale@basischina.com")
    with TestClient(app) as client:
        register = _register(client, "Jordan.Hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert register.status_code == 201, register.text
        body = register.json()
        assert body["email"] == "jordan.hale@basischina.com"
        assert body["display_name"] == "Jordan Hale"
        assert body["roles"] == ["student", "super_admin"]
        assert body["muted"] is False
        assert body["terms_accepted_at"].endswith("Z")
        assert "password" not in body and "password_hash" not in body
        assert "scoop_session" in register.cookies

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["id"] == body["id"]

        forum = client.post(
            "/api/v1/posts",
            json={
                "title": "Who still has dryer quarters",
                "body": "The change machine is dark.",
                "category": "forum",
                "author_id": "should-be-ignored",
                "status": "draft",
            },
        )
        assert forum.status_code == 201, forum.text

        direct_news = client.post(
            "/api/v1/posts",
            json={
                "title": "East Hall laundry room will close Friday night",
                "body": "Facilities posted a handwritten note on the basement door.",
                "category": "news",
            },
        )
        assert direct_news.status_code == 403

        draft = client.post(
            "/api/v1/news/drafts",
            json={"title": "East Hall laundry room will close Friday night"},
        )
        assert draft.status_code == 201, draft.text
        draft_id = draft.json()["id"]
        held = client.post(
            f"/api/v1/news/drafts/{draft_id}/blocks",
            json={"heading": "Still in draft", "body": "This section stays off the public page."},
        )
        assert held.status_code == 201, held.text
        held_id = held.json()["blocks"][0]["id"]
        live = client.post(
            f"/api/v1/news/drafts/{draft_id}/blocks",
            json={
                "heading": "Friday night",
                "body": "Facilities posted a handwritten note on the basement door.",
            },
        )
        assert live.status_code == 201, live.text
        live_id = next(block["id"] for block in live.json()["blocks"] if block["heading"] == "Friday night")
        submitted = client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{live_id}/submit")
        assert submitted.status_code == 200, submitted.text
        approved = client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{live_id}/approve")
        assert approved.status_code == 200, approved.text
        assert held_id != live_id
        revised = client.patch(
            f"/api/v1/news/drafts/{draft_id}/blocks/{live_id}",
            json={"body": "The machines stay open after all."},
        )
        assert revised.status_code == 200, revised.text
        still_live = client.get(f"/api/v1/posts/{draft_id}")
        assert still_live.json()["blocks"][0]["body"].startswith("Facilities posted")
        assert client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{live_id}/submit").status_code == 200
        assert client.post(f"/api/v1/news/drafts/{draft_id}/blocks/{live_id}/approve").status_code == 200
        updated = client.get(f"/api/v1/posts/{draft_id}")
        assert updated.json()["blocks"][0]["body"] == "The machines stay open after all."
        assert "This section stays off the public page." not in updated.json()["body"]
        post = {"id": draft_id}

        sports = client.post(
            "/api/v1/posts",
            json={
                "title": "Intramural basketball finals — Saturday at the old gym",
                "body": "East Hall plays the faculty pick-up team for the dorm cup.",
                "category": "sports",
            },
        )
        assert sports.status_code == 422

        mine = client.get("/api/v1/me/posts")
        assert mine.status_code == 200
        assert mine.json()["total"] == 2
        assert {item["id"] for item in mine.json()["items"]} == {forum.json()["id"], draft_id}

        with app.state.session_factory() as session:
            audit_count = session.scalar(select(func.count()).select_from(AuditEvent))
            assert audit_count == 2

    with TestClient(app) as guest:
        listed = guest.get("/api/v1/posts")
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1
        assert listed.json()["items"][0]["title"] == "East Hall laundry room will close Friday night"
        assert listed.json()["items"][0]["category"] == "news"

        detail = guest.get(f"/api/v1/posts/{post['id']}")
        assert detail.status_code == 200
        assert detail.json()["blocks"][0]["body"] == "The machines stay open after all."
        assert len(detail.json()["blocks"]) == 1
        assert detail.json()["blocks"][0]["heading"] == "Friday night"
        assert "This section stays off the public page." not in detail.json()["body"]

        me = guest.get("/api/v1/me")
        assert me.status_code == 401
        assert me.json()["error"]["code"] == "unauthenticated"

    app.state.engine.dispose()
    reopened = _make_app(tmp_path, monkeypatch)
    with TestClient(reopened) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert login.status_code == 200
        listed = client.get("/api/v1/posts")
        assert listed.json()["total"] == 1
        detail = client.get(f"/api/v1/posts/{post['id']}")
        assert detail.status_code == 200
        assert detail.json()["title"] == "East Hall laundry room will close Friday night"
    reopened.state.engine.dispose()


def test_error_paths_do_not_write_posts(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="priya.nair@basischina.com")
    with TestClient(app) as client:
        _register(client, "priya.nair@basischina.com", "old-gym-17", "Priya Nair")

        bad_login = client.post(
            "/api/v1/auth/login",
            json={"email": "priya.nair@basischina.com", "password": "wrong-pass"},
        )
        assert bad_login.status_code == 401
        assert bad_login.json()["error"]["code"] == "invalid_credentials"

        missing = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@basischina.com", "password": "old-gym-17"},
        )
        assert missing.status_code == 401
        assert missing.json()["error"]["message"] == "Email or password is incorrect."

    with TestClient(app) as guest:
        unauth = guest.post(
            "/api/v1/posts",
            json={
                "title": "Should not publish",
                "body": "Visitor cannot post.",
                "category": "news",
            },
        )
        assert unauth.status_code == 401
        assert unauth.json()["error"]["code"] == "unauthenticated"

    with TestClient(app) as client:
        client.post(
            "/api/v1/auth/login",
            json={"email": "priya.nair@basischina.com", "password": "old-gym-17"},
        )

        empty_title = client.post(
            "/api/v1/posts",
            json={"title": "   ", "body": "Has a body", "category": "news"},
        )
        assert empty_title.status_code == 422
        assert empty_title.json()["error"]["code"] == "validation_error"

        bad_category = client.post(
            "/api/v1/posts",
            json={
                "title": "Hall gossip",
                "body": "Not a real column.",
                "category": "gossip",
            },
        )
        assert bad_category.status_code == 422

        listed = client.get("/api/v1/posts")
        assert listed.json()["total"] == 0
        with app.state.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Post)) == 0

        def boom(*_args, **_kwargs):
            raise StorageError("Could not save the post. Try again in a moment.")

        monkeypatch.setattr("routers.posts.create_post_with_audit", boom)
        failed = client.post(
            "/api/v1/posts",
            json={
                "title": "Intramural basketball finals — Saturday at the old gym",
                "body": "East Hall plays the faculty pick-up team for the dorm cup.",
                "category": "forum",
            },
        )
        assert failed.status_code == 503
        assert failed.json()["error"]["code"] == "storage_unavailable"
        listed = client.get("/api/v1/posts")
        assert listed.json()["total"] == 0
        assert listed.json()["items"] == []
    app.state.engine.dispose()


def test_cookie_required_only_on_private_routes(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="wei.chen@basischina.com")
    with TestClient(app) as client:
        _register(client, "wei.chen@basischina.com", "library-24", "Wei Chen")
        post_id = _publish_news(
            client,
            "Library 24-hour desks start the week before midterms",
            "The third-floor quiet wing will stay open overnight.",
        )

        logout = client.post("/api/v1/auth/logout")
        assert logout.status_code == 204
        assert client.get("/api/v1/me").status_code == 401

        listed = client.get("/api/v1/posts")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        detail = client.get(f"/api/v1/posts/{post_id}")
        assert detail.status_code == 200

        me = client.get("/api/v1/me")
        assert me.status_code == 401

        create = client.post(
            "/api/v1/posts",
            json={
                "title": "Another note",
                "body": "Needs a session.",
                "category": "news",
            },
        )
        assert create.status_code == 401

        page = client.get("/api/v1/posts?page=0")
        assert page.status_code == 400
        assert page.json()["error"]["code"] == "bad_request"

        category = client.get("/api/v1/posts?category=gossip")
        assert category.status_code == 422

        missing = client.get("/api/v1/posts/00000000-0000-4000-8000-000000000000")
        assert missing.status_code == 404

        not_uuid = client.get("/api/v1/posts/not-a-uuid")
        assert not_uuid.status_code == 400

        patch = client.patch(f"/api/v1/posts/{post_id}", json={"title": "Nope"})
        assert patch.status_code == 405

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
    app.state.engine.dispose()


def test_student_community_comments_promote_and_admin_roles(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert student.status_code == 201
        assert student.json()["roles"] == ["student"]

        blocked = client.post(
            "/api/v1/posts",
            json={
                "title": "Should stay off the paper",
                "body": "Students cannot write news.",
                "category": "news",
            },
        )
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "forbidden"

        community = client.post(
            "/api/v1/posts",
            json={
                "title": "Laundry chat in the stairwell",
                "body": "Who still has quarters for East Hall?",
                "category": "forum",
            },
        )
        assert community.status_code == 201, community.text
        post_id = community.json()["id"]
        assert community.json()["category"] == "forum"

        home = client.get("/api/v1/posts")
        assert home.status_code == 200
        assert home.json()["total"] == 0

        board = client.get("/api/v1/posts?category=forum")
        assert board.json()["total"] == 1
        assert board.json()["items"][0]["id"] == post_id

        guest = TestClient(app)
        listed = guest.get(f"/api/v1/posts/{post_id}/comments")
        assert listed.status_code == 200
        assert listed.json()["items"] == []
        unauth = guest.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "Saving a dryer for tonight."},
        )
        assert unauth.status_code == 401

        floor = client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "I have a roll in 312."},
        )
        assert floor.status_code == 201, floor.text
        assert floor.json()["floor"] == 1
        assert floor.json()["parent_id"] is None
        floor_id = floor.json()["id"]

        reply = client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "I will come by after dinner.", "parent_id": floor_id},
        )
        assert reply.status_code == 422
        assert reply.json()["error"]["fields"][0]["field"] == "parent_id"

        newspaper = guest.get(f"/api/v1/posts/{post_id}")
        news_id = None
        detail = guest.get("/api/v1/posts")
        assert detail.json()["total"] == 0

        comments = guest.get(f"/api/v1/posts/{post_id}/comments")
        assert comments.status_code == 200
        assert comments.json()["total"] == 1
        assert comments.json()["items"][0]["replies"] == []
        assert comments.json()["items"][0]["body"] == "I have a roll in 312."
        assert comments.json()["items"][0]["author"]["avatar"] == "preset:oak"

        board_after = guest.get("/api/v1/posts?category=forum")
        card = board_after.json()["items"][0]
        assert card["reply_count"] == 1
        assert len(card["reply_preview"]) == 1
        assert card["reply_preview"][0]["body"] == "I have a roll in 312."
        home_card = guest.get("/api/v1/posts").json()["items"]
        assert all(item["reply_count"] == 0 and item["reply_preview"] == [] for item in home_card)

        promote_denied = client.post(
            f"/api/v1/posts/{post_id}/promote",
            json={"category": "news"},
        )
        assert promote_denied.status_code == 405

        admin = _register(client, "Ada.Min@basischina.com", "desk-key-99", "Ada Min")
        assert admin.status_code == 201
        assert admin.json()["roles"] == ["student", "super_admin"]
        student_id = student.json()["id"]

        users = client.get("/api/v1/admin/users")
        assert users.status_code == 200
        assert users.json()["total"] == 2

        granted = client.patch(
            f"/api/v1/admin/users/{student_id}",
            json={"roles": ["editor"]},
        )
        assert granted.status_code == 200
        assert granted.json()["roles"] == ["editor"]

        client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        me = client.get("/api/v1/me")
        assert me.json()["roles"] == ["editor"]

        drafted = client.post(
            "/api/v1/news/drafts",
            json={"title": "East Hall is short on quarters"},
        )
        assert drafted.status_code == 201, drafted.text
        news_id = drafted.json()["id"]
        added = client.post(
            f"/api/v1/news/drafts/{news_id}/blocks",
            json={"heading": "Quarters", "body": "East Hall is short on quarters tonight."},
        )
        assert added.status_code == 201, added.text
        block_id = added.json()["blocks"][0]["id"]
        assert client.post(f"/api/v1/news/drafts/{news_id}/blocks/{block_id}/submit").status_code == 200
        editor_approve = client.post(f"/api/v1/news/drafts/{news_id}/blocks/{block_id}/approve")
        assert editor_approve.status_code == 403
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        approved = client.post(f"/api/v1/news/drafts/{news_id}/blocks/{block_id}/approve")
        assert approved.status_code == 200, approved.text
        assert news_id != post_id
        public = guest.get(f"/api/v1/posts/{news_id}")
        assert public.status_code == 200
        assert public.json()["category"] == "news"
        assert public.json()["blocks"][0]["heading"] == "Quarters"
        assert guest.get(f"/api/v1/posts/{post_id}").json()["title"] == "Laundry chat in the stairwell"
        assert guest.get("/api/v1/posts").json()["total"] == 1

        paper_comments = guest.get(f"/api/v1/posts/{news_id}/comments")
        assert paper_comments.status_code == 422

        client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        admin_as_editor = client.get("/api/v1/admin/users")
        assert admin_as_editor.status_code == 403

        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        revoked = client.patch(
            f"/api/v1/admin/users/{student_id}",
            json={"roles": ["student"]},
        )
        assert revoked.status_code == 200
        assert revoked.json()["roles"] == ["student"]
        kept_super = client.patch(
            f"/api/v1/admin/users/{admin.json()['id']}",
            json={"roles": ["editor"]},
        )
        assert kept_super.status_code == 200, kept_super.text
        assert kept_super.json()["roles"] == ["editor", "super_admin"]
    app.state.engine.dispose()


def test_avatar_preset_upload_and_reply_preview_cap(tmp_path, monkeypatch):
    import avatars

    monkeypatch.setattr(avatars, "AVATAR_DIR", tmp_path / "avatars")
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert created.json()["avatar"] == "preset:oak"

        preset = client.put("/api/v1/me/avatar", json={"preset": "gym"})
        assert preset.status_code == 200
        assert preset.json()["avatar"] == "preset:gym"

        bad_preset = client.put("/api/v1/me/avatar", json={"preset": "dragon"})
        assert bad_preset.status_code == 422

        upload = client.post(
            "/api/v1/me/avatar",
            files={"file": ("me.png", b"\x89PNG\r\n" + b"x" * 20, "image/png")},
        )
        assert upload.status_code == 200
        assert upload.json()["avatar"].startswith("/uploads/avatars/")

        huge = client.post(
            "/api/v1/me/avatar",
            files={"file": ("big.png", b"x" * 1_000_001, "image/png")},
        )
        assert huge.status_code == 422

        wrong = client.post(
            "/api/v1/me/avatar",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert wrong.status_code == 422

        post = client.post(
            "/api/v1/posts",
            json={
                "title": "Five floors in the laundry thread",
                "body": "Post the machine number if you grab one.",
                "category": "forum",
            },
        )
        post_id = post.json()["id"]
        for index in range(5):
            reply = client.post(
                f"/api/v1/posts/{post_id}/comments",
                json={"body": f"Floor {index + 1} is open."},
            )
            assert reply.status_code == 201

        board = client.get("/api/v1/posts?category=forum")
        card = board.json()["items"][0]
        assert card["reply_count"] == 5
        assert [item["body"] for item in card["reply_preview"]] == [
            "Floor 4 is open.",
            "Floor 5 is open.",
        ]
        assert card["author"]["avatar"].startswith("/uploads/avatars/")
        assert card["images"] == []
    app.state.engine.dispose()


def test_community_post_images_and_newspaper_rejected(tmp_path, monkeypatch):
    import avatars

    monkeypatch.setattr(avatars, "POST_IMAGE_DIR", tmp_path / "posts")
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert student.status_code == 201
        community = client.post(
            "/api/v1/posts",
            json={
                "title": "Photo of the broken dryer",
                "body": "The third machine is still leaking.",
                "category": "forum",
            },
        )
        post_id = community.json()["id"]
        assert community.json()["images"] == []

        first = client.post(
            f"/api/v1/posts/{post_id}/images",
            files={"file": ("leak.png", b"\x89PNG\r\n" + b"x" * 20, "image/png")},
        )
        assert first.status_code == 200, first.text
        assert len(first.json()["images"]) == 1
        assert first.json()["images"][0].startswith(f"/uploads/posts/{post_id}/")

        for index in range(3):
            extra = client.post(
                f"/api/v1/posts/{post_id}/images",
                files={"file": (f"extra-{index}.png", b"\x89PNG\r\n" + b"y" * 20, "image/png")},
            )
            assert extra.status_code == 200
        overflow = client.post(
            f"/api/v1/posts/{post_id}/images",
            files={"file": ("too-many.png", b"\x89PNG\r\n" + b"z" * 20, "image/png")},
        )
        assert overflow.status_code == 422

        board = client.get("/api/v1/posts?category=forum")
        assert len(board.json()["items"][0]["images"]) == 4
        home = client.get("/api/v1/posts")
        assert home.json()["items"] == []

        guest = TestClient(app)
        other = _register(guest, "priya.nair@basischina.com", "old-gym-17", "Priya Nair")
        assert other.status_code == 201
        stolen = guest.post(
            f"/api/v1/posts/{post_id}/images",
            files={"file": ("nope.png", b"\x89PNG\r\n" + b"x" * 20, "image/png")},
        )
        assert stolen.status_code == 403

        editor = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert editor.status_code == 201
        news_id = _publish_news(
            client,
            "Dryer replacement notice",
            "Facilities will swap the East Hall machines Friday.",
        )
        assert client.get(f"/api/v1/posts/{news_id}").json()["images"] == []
        blocked = client.post(
            f"/api/v1/posts/{news_id}/images",
            files={"file": ("cover.png", b"\x89PNG\r\n" + b"x" * 20, "image/png")},
        )
        assert blocked.status_code == 422
        listed = client.get("/api/v1/posts")
        assert listed.json()["items"][0]["images"] == []

        before = client.get("/api/v1/posts?category=forum").json()["total"]
        bad_multi = client.post(
            "/api/v1/posts",
            data={"title": "Should not land", "body": "Bad attachment.", "category": "forum"},
            files=[("images", ("notes.txt", b"hello", "text/plain"))],
        )
        assert bad_multi.status_code == 422
        assert client.get("/api/v1/posts?category=forum").json()["total"] == before

        paper_images = client.post(
            "/api/v1/posts",
            data={"title": "Paper with photo", "body": "Should fail.", "category": "news"},
            files=[("images", ("cover.png", b"\x89PNG\r\n" + b"x" * 20, "image/png"))],
        )
        assert paper_images.status_code == 422

        created = client.post(
            "/api/v1/posts",
            data={
                "title": "One-shot laundry photo",
                "body": "The leak from the third machine.",
                "category": "forum",
            },
            files=[("images", ("leak.png", b"\x89PNG\r\n" + b"x" * 20, "image/png"))],
        )
        assert created.status_code == 201, created.text
        assert created.json()["category"] == "forum"
        assert len(created.json()["images"]) == 1
    app.state.engine.dispose()


def test_forum_likes_idempotent_guest_and_newspaper_rejected(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="jordan.hale@basischina.com")
    with TestClient(app) as client:
        _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        forum = client.post(
            "/api/v1/posts",
            json={
                "title": "Who has dryer quarters?",
                "body": "The change machine is still dark.",
                "category": "forum",
            },
        )
        post_id = forum.json()["id"]
        assert forum.json()["like_count"] == 0
        assert forum.json()["liked"] is False

        first = client.post(f"/api/v1/posts/{post_id}/likes")
        assert first.status_code == 201, first.text
        assert first.json() == {"like_count": 1, "liked": True}

        again = client.post(f"/api/v1/posts/{post_id}/likes")
        assert again.status_code == 200
        assert again.json()["like_count"] == 1

        listed = client.get("/api/v1/posts?category=forum")
        card = listed.json()["items"][0]
        assert card["like_count"] == 1
        assert card["liked"] is True

        guest = TestClient(app)
        guest_list = guest.get("/api/v1/posts?category=forum")
        assert guest_list.json()["items"][0]["liked"] is False
        assert guest_list.json()["items"][0]["like_count"] == 1
        assert guest.post(f"/api/v1/posts/{post_id}/likes").status_code == 401

        removed = client.delete(f"/api/v1/posts/{post_id}/likes")
        assert removed.status_code == 200
        assert removed.json() == {"like_count": 0, "liked": False}
        assert client.delete(f"/api/v1/posts/{post_id}/likes").json()["like_count"] == 0

        news_id = _publish_news(
            client,
            "East Hall laundry: who still has quarters?",
            "The change machine is dark again.",
        )
        paper_like = client.post(f"/api/v1/posts/{news_id}/likes")
        assert paper_like.status_code == 422
        home = client.get("/api/v1/posts")
        assert home.json()["items"][0]["like_count"] == 0
        assert home.json()["items"][0]["liked"] is False
    app.state.engine.dispose()


def test_author_sees_and_deletes_only_their_forum_posts(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, name="forum_mine.db")
    with TestClient(app) as client:
        assert client.get("/api/v1/posts?category=forum&feed=mine").status_code == 401
        _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        own = client.post(
            "/api/v1/posts",
            json={"title": "My locker note", "body": "Left on the board.", "category": "forum"},
        )
        assert own.status_code == 201, own.text
        own_id = own.json()["id"]
        _register(client, "priya.nair@basischina.com", "east-hall-9", "Priya Nair")
        theirs = client.post(
            "/api/v1/posts",
            json={"title": "Priya's note", "body": "Not Jordan's.", "category": "forum"},
        )
        assert theirs.status_code == 201, theirs.text
        client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        mine = client.get("/api/v1/posts?category=forum&feed=mine")
        assert mine.status_code == 200, mine.text
        assert [item["title"] for item in mine.json()["items"]] == ["My locker note"]
        denied_news = client.delete(f"/api/v1/posts/{theirs.json()['id']}")
        assert denied_news.status_code == 403
        removed = client.delete(f"/api/v1/posts/{own_id}")
        assert removed.status_code == 204
        assert client.get(f"/api/v1/posts/{own_id}").status_code == 404
        assert client.get("/api/v1/posts?category=forum&feed=mine").json()["items"] == []
        notices = client.get("/api/v1/me/notices")
        assert notices.status_code == 200
        assert notices.json()["items"] == []
        assert client.get("/api/v1/posts?category=forum&feed=all").json()["total"] == 1
    app.state.engine.dispose()


def test_admin_delete_post_and_ban_account(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert student.status_code == 201
        assert student.json()["muted"] is False
        student_id = student.json()["id"]
        created = client.post(
            "/api/v1/posts",
            json={
                "title": "Who still has the dorm key",
                "body": "It was on the oak table.",
                "category": "forum",
            },
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        replied = client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "I saw it after dinner."},
        )
        assert replied.status_code == 201, replied.text

        other = _register(client, "priya.nair@basischina.com", "east-hall-9", "Priya Nair")
        assert other.status_code == 201
        denied = client.delete(f"/api/v1/posts/{post_id}")
        assert denied.status_code == 403
        assert client.get(f"/api/v1/posts/{post_id}").status_code == 200

        ban_denied = client.patch(
            f"/api/v1/admin/users/{student_id}",
            json={"muted": True},
        )
        assert ban_denied.status_code == 403

        _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        admin = client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        assert admin.status_code == 200, admin.text
        admin_id = admin.json()["id"]

        self_ban = client.patch(f"/api/v1/admin/users/{admin_id}", json={"muted": True})
        assert self_ban.status_code == 403

        removed = client.delete(f"/api/v1/posts/{post_id}")
        assert removed.status_code == 204
        assert client.get(f"/api/v1/posts/{post_id}").status_code == 404
        client.cookies.clear()
        client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        notices = client.get("/api/v1/me/notices")
        assert notices.status_code == 200
        assert any("Who still has the dorm key" in item["body"] for item in notices.json()["items"])
        client.cookies.clear()
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        listed = client.get("/api/v1/posts?category=forum")
        assert all(item["id"] != post_id for item in listed.json()["items"])

        kept = client.post(
            "/api/v1/posts",
            json={
                "title": "Ada keeps this note",
                "body": "Written before the ban test continues.",
                "category": "forum",
            },
        )
        # admin is editor-capable; the kept post is admin's. Student still has no second post.
        # Re-login as student and publish one that must survive a ban.
        client.cookies.clear()
        student_login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert student_login.status_code == 200
        survivor = client.post(
            "/api/v1/posts",
            json={
                "title": "Jordan's note stays up",
                "body": "Ban should not hide this.",
                "category": "forum",
            },
        )
        assert survivor.status_code == 201, survivor.text
        survivor_id = survivor.json()["id"]

        client.cookies.clear()
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        muted = client.patch(f"/api/v1/admin/users/{student_id}", json={"muted": True})
        assert muted.status_code == 200, muted.text
        assert muted.json()["muted"] is True

        client.cookies.clear()
        locked = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert locked.status_code == 200, locked.text
        muted_post = client.post(
            "/api/v1/posts",
            json={
                "title": "Should not publish while muted",
                "body": "Mute blocks new posts.",
                "category": "forum",
            },
        )
        assert muted_post.status_code == 403
        assert muted_post.json()["error"]["code"] == "account_muted"
        still_there = client.get(f"/api/v1/posts/{survivor_id}")
        assert still_there.status_code == 200
        assert still_there.json()["title"] == "Jordan's note stays up"

        client.cookies.clear()
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )
        unmuted = client.patch(f"/api/v1/admin/users/{student_id}", json={"muted": False})
        assert unmuted.status_code == 200
        assert unmuted.json()["muted"] is False
        deleted = client.delete(f"/api/v1/admin/users/{student_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/v1/posts/{survivor_id}").status_code == 404
        client.cookies.clear()
        gone = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert gone.status_code == 401
        assert kept.status_code == 201
    app.state.engine.dispose()


def test_register_requires_accept_terms(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    email = "jordan.hale@basischina.com"
    with TestClient(app) as client:
        sent = client.post("/api/v1/auth/email-codes", json={"email": email, "purpose": "register"})
        assert sent.status_code == 204, sent.text
        code = peek_console_code(normalize_email(email), "register")
        payload = {
            "email": email,
            "password": "east-hall-8",
            "display_name": "Jordan Hale",
            "code": code,
        }
        missing = client.post("/api/v1/auth/register", json=payload)
        assert missing.status_code == 422, missing.text
        assert any(item["field"] == "accept_terms" for item in missing.json()["error"]["fields"])

        rejected = client.post("/api/v1/auth/register", json={**payload, "accept_terms": False})
        assert rejected.status_code == 422, rejected.text
        assert rejected.json()["error"]["fields"][0]["field"] == "accept_terms"

        login = client.post("/api/v1/auth/login", json={"email": email, "password": "east-hall-8"})
        assert login.status_code == 401

        created = client.post("/api/v1/auth/register", json={**payload, "accept_terms": True})
        assert created.status_code == 201, created.text
        assert created.json()["terms_accepted_at"].endswith("Z")
    app.state.engine.dispose()


def test_school_email_codes_register_and_password_reset(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        outside = client.post(
            "/api/v1/auth/email-codes",
            json={"email": "visitor@gmail.com", "purpose": "register"},
        )
        assert outside.status_code == 422, outside.text
        assert outside.json()["error"]["fields"][0]["field"] == "email"
        assert peek_console_code("visitor@gmail.com", "register") is None

        outside_login = client.post(
            "/api/v1/auth/login",
            json={"email": "visitor@gmail.com", "password": "east-hall-8"},
        )
        assert outside_login.status_code == 422
        assert outside_login.json()["error"]["fields"][0]["field"] == "email"

        no_code = client.post(
            "/api/v1/auth/register",
            json={
                "email": "jordan.hale@basischina.com",
                "password": "east-hall-8",
                "display_name": "Jordan Hale",
                "code": "000000",
                "accept_terms": True,
            },
        )
        assert no_code.status_code == 422
        assert no_code.json()["error"]["fields"][0]["field"] == "code"

        sent = client.post(
            "/api/v1/auth/email-codes",
            json={"email": "jordan.hale@basischina.com", "purpose": "register"},
        )
        assert sent.status_code == 204, sent.text
        raw_code = peek_console_code("jordan.hale@basischina.com", "register")
        assert raw_code
        created = client.post(
            "/api/v1/auth/register",
            json={
                "email": "jordan.hale@basischina.com",
                "password": "east-hall-8",
                "display_name": "Jordan Hale",
                "code": f"{raw_code}.",
                "accept_terms": True,
            },
        )
        assert created.status_code == 201, created.text

        taken = client.post(
            "/api/v1/auth/email-codes",
            json={"email": "jordan.hale@basischina.com", "purpose": "register"},
        )
        assert taken.status_code == 409

        reset_send = client.post(
            "/api/v1/auth/email-codes",
            json={"email": "jordan.hale@basischina.com", "purpose": "reset"},
        )
        assert reset_send.status_code == 204, reset_send.text
        reset_code = peek_console_code("jordan.hale@basischina.com", "reset")
        assert reset_code

        unknown = client.post(
            "/api/v1/auth/email-codes",
            json={"email": "ghost@basischina.com", "purpose": "reset"},
        )
        assert unknown.status_code == 204
        assert peek_console_code("ghost@basischina.com", "reset") is None

        reset = client.post(
            "/api/v1/auth/password-reset",
            json={
                "email": "jordan.hale@basischina.com",
                "code": reset_code,
                "password": "new-hall-99",
            },
        )
        assert reset.status_code == 204, reset.text

        old_login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert old_login.status_code == 401
        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "new-hall-99"},
        )
        assert new_login.status_code == 200, new_login.text
    app.state.engine.dispose()


def test_change_password_keeps_session(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        created = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert created.status_code == 201, created.text

        guest = TestClient(app)
        assert guest.put(
            "/api/v1/me/password",
            json={"current_password": "east-hall-8", "password": "new-hall-99"},
        ).status_code == 401

        wrong = client.put(
            "/api/v1/me/password",
            json={"current_password": "wrong-pass", "password": "new-hall-99"},
        )
        assert wrong.status_code == 422
        assert wrong.json()["error"]["fields"][0]["field"] == "current_password"

        same = client.put(
            "/api/v1/me/password",
            json={"current_password": "east-hall-8", "password": "east-hall-8"},
        )
        assert same.status_code == 422

        changed = client.put(
            "/api/v1/me/password",
            json={"current_password": "east-hall-8", "password": "new-hall-99"},
        )
        assert changed.status_code == 204, changed.text
        assert client.get("/api/v1/me").status_code == 200
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "jordan.hale@basischina.com", "password": "new-hall-99"},
            ).status_code
            == 200
        )
    app.state.engine.dispose()


def test_news_block_position(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        created = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert created.status_code == 201, created.text
        drafted = client.post("/api/v1/news/drafts", json={"title": "Front page layout"})
        assert drafted.status_code == 201, drafted.text
        draft_id = drafted.json()["id"]
        placed = client.post(
            f"/api/v1/news/drafts/{draft_id}/blocks",
            json={"heading": "Late", "body": "The late slot.", "position": 5},
        )
        assert placed.status_code == 201, placed.text
        blocks = placed.json()["blocks"]
        assert len(blocks) == 1
        assert blocks[0]["position"] == 5
        again = client.post(
            f"/api/v1/news/drafts/{draft_id}/blocks",
            json={"heading": "Again", "body": "That slot is taken.", "position": 5},
        )
        assert again.status_code == 422
        assert again.json()["error"]["fields"][0]["field"] == "position"
    app.state.engine.dispose()


def test_cj_role_portals_and_subject_scoping(tmp_path, monkeypatch):
    super_email = "sasha.lin@basischina.com"
    app = _make_app(tmp_path, monkeypatch, admin_email=super_email)
    with (
        TestClient(app) as anonymous,
        TestClient(app) as super_client,
        TestClient(app) as student_client,
        TestClient(app) as teacher_client,
        TestClient(app) as admin_client,
    ):
        super_user = _register(super_client, super_email, "super-desk-41", "Sasha Lin")
        student_user = _register(student_client, "mia.chen@basischina.com", "student-hall-42", "Mia Chen")
        teacher_user = _register(teacher_client, "evan.wu@basischina.com", "teacher-lab-43", "Evan Wu")
        admin_user = _register(admin_client, "noah.zhou@basischina.com", "admin-office-44", "Noah Zhou")
        assert super_user.json()["roles"] == ["student", "super_admin"]
        assert student_user.json()["roles"] == ["student"]

        teacher_id = teacher_user.json()["id"]
        admin_id = admin_user.json()["id"]
        promoted_teacher = super_client.patch(
            f"/api/v1/admin/users/{teacher_id}", json={"roles": ["teacher"]}
        )
        promoted_admin = super_client.patch(
            f"/api/v1/admin/users/{admin_id}", json={"roles": ["admin"]}
        )
        assert promoted_teacher.status_code == 200, promoted_teacher.text
        assert promoted_teacher.json()["roles"] == ["teacher"]
        assert promoted_admin.status_code == 200, promoted_admin.text

        for client, email, password, expected_role in (
            (student_client, "mia.chen@basischina.com", "student-hall-42", "student"),
            (teacher_client, "evan.wu@basischina.com", "teacher-lab-43", "teacher"),
            (admin_client, "noah.zhou@basischina.com", "admin-office-44", "admin"),
        ):
            assert client.post("/api/v1/auth/logout").status_code == 204
            login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200, login.text
            assert login.json()["roles"] == [expected_role]

        assert anonymous.get("/api/v1/cj?week_start=2026-10-05").status_code == 401
        assert admin_client.get("/api/v1/cj?week_start=2026-10-05").status_code == 403
        assert admin_client.get("/api/v1/cj/teachers").status_code == 404
        assert anonymous.put(
            "/api/v1/cj",
            headers={"X-CJ-Admin-Code": "CJ-DEMO"},
            json={"week_start": "2026-10-05"},
        ).status_code == 401

        all_cj = super_client.get("/api/v1/cj?week_start=2026-10-05")
        assert all_cj.status_code == 200, all_cj.text
        all_subjects = all_cj.json()["subjects"]
        assert len(all_subjects) == 28
        assert {subject["grade"] for subject in all_subjects} == {11}
        assert {subject["class_section"] for subject in all_subjects} == {"Ac", "Mc", "All"}
        assert any(subject["default_period"] == 11 for subject in all_subjects)
        assert all("teacher" in subject and "room" in subject for subject in all_subjects)
        subject_id = all_subjects[0]["id"]

        student_view = student_client.get("/api/v1/cj?week_start=2026-10-05")
        teacher_view = teacher_client.get("/api/v1/cj?week_start=2026-10-05")
        assert student_view.status_code == 200, student_view.text
        assert teacher_view.status_code == 200, teacher_view.text
        assert len(student_view.json()["subjects"]) == len(all_subjects)
        assert [subject["id"] for subject in teacher_view.json()["subjects"]] == [
            subject["id"] for subject in all_subjects
        ]
        assert teacher_view.json()["entries"] == student_view.json()["entries"]
        assert teacher_view.json()["exams"] == student_view.json()["exams"]

        entry = {
            "week_start": "2026-10-05",
            "day_index": 0,
            "subject_id": subject_id,
            "ic": "Role-scoped update",
            "hw": "Page 1",
            "announcement": "Bring a pencil",
        }
        assert student_client.put("/api/v1/cj", json=entry).status_code == 403
        assert teacher_client.put("/api/v1/cj", json=entry).status_code == 403
        assert teacher_client.put(
            "/api/v1/cj/exams",
            json={
                "week_start": "2026-10-05",
                "day_index": 2,
                "subject_id": subject_id,
                "title": "Teacher subject quiz",
                "time": "09:30",
                "location": "Room 101",
                "note": "",
            },
        ).status_code == 403
        assert teacher_client.post("/api/v1/cj/sync").status_code == 403

        super_saved = super_client.put("/api/v1/cj", json=entry)
        assert super_saved.status_code == 200, super_saved.text
        exam_saved = super_client.put(
            "/api/v1/cj/exams",
            json={
                "week_start": "2026-10-05",
                "day_index": 2,
                "subject_id": subject_id,
                "title": "Super-admin exam",
                "time": "09:30",
                "location": "Room 101",
                "note": "Bring a calculator",
            },
        )
        assert exam_saved.status_code == 200, exam_saved.text
        assert teacher_client.delete(
            f"/api/v1/cj/exams/{exam_saved.json()['id']}"
        ).status_code == 403
        refreshed_student = student_client.get("/api/v1/cj?week_start=2026-10-05")
        assert any(exam["subject_id"] == subject_id for exam in refreshed_student.json()["exams"])

        new_course = {
            "name": "Environmental Science Lab",
            "short_name": "ES Lab",
            "grade": 11,
            "class_section": "All",
            "default_period": 9,
            "teacher": "Demo Teacher",
            "room": "E401",
        }
        assert teacher_client.post("/api/v1/cj/subjects", json=new_course).status_code == 403
        created_course = super_client.post("/api/v1/cj/subjects", json=new_course)
        assert created_course.status_code == 201, created_course.text
        assert created_course.json()["is_custom"] is True
        after_course = student_client.get("/api/v1/cj?week_start=2026-10-05")
        assert any(subject["short_name"] == "ES Lab" for subject in after_course.json()["subjects"])
        assert super_client.delete(
            f"/api/v1/cj/subjects/{created_course.json()['id']}"
        ).status_code == 204
        assert super_client.delete(f"/api/v1/cj/subjects/{subject_id}").status_code == 422
    app.state.engine.dispose()


def test_cj_journal_sync_cleans_and_stores(tmp_path, monkeypatch):
    from dataclasses import replace
    from datetime import date

    import cj_sync
    from errors import ApiError

    app = _make_app(tmp_path, monkeypatch, name="cj_sync.db", admin_email="sasha.lin@basischina.com")
    monkeypatch.setattr(cj_sync, "shanghai_today", lambda: date(2026, 10, 15))
    assert cj_sync.match_journal_course("11Mc AP Language & Composition") == "ap-lang-11mc"
    assert cj_sync.match_journal_course("Chinese 11Ac") == "chinese-11ac"
    assert cj_sync.match_journal_course("11Ac AP Language & Composition") == "ap-lang-11ac"
    assert cj_sync.match_journal_course("11Mc AP Calculus AB") == "ap-calculus-11mc"
    assert cj_sync.match_journal_course("Chinese 11Mc") == "chinese-11mc"
    assert cj_sync.match_journal_course("AP Physics 1 G11") == "ap-physics"
    assert cj_sync.match_journal_course("11 Ac AP Calculus AB") == "ap-calculus-11ac"
    assert cj_sync.match_journal_course("AP Stats") == "ap-stats"
    assert cj_sync.match_journal_course("AP Microeconomics", "Andrew Mark Peterson") == "ap-micro-macro"
    course = {
        "code": "CALC",
        "name": "11 Ac AP Calculus AB",
        "teacher": "Kyle Sheldon Manzoni",
        "classroom": "E522",
        "environment": "BBGM",
        "period": "Period 10",
        "daily_content": [
            {"date": "2026-10-12", "ic": "Limits", "hw": "FRQ", "an": "Quiz"},
        ],
    }
    payloads = {"items": [course]}
    calls = {"fetch": 0}

    def fake_fetch(base, key, start, end):
        calls["fetch"] += 1
        assert base == "https://staging.myclassroomjournal.com"
        assert key == "test-journal-key"
        assert (start, end) == ("2026-10-12", "2026-10-23")
        return payloads["items"]

    def fake_clean(api_key, model, items):
        assert api_key == "test-deepseek-key"
        assert model == "deepseek-chat"
        assert items == [
            {"id": "bbgm-calc|2026-10-12", "ic": "Limits", "hw": "FRQ", "an": "Quiz"}
        ]
        return [{**item, "ic": f"{item['ic']} review"} for item in items]

    monkeypatch.setattr(cj_sync, "fetch_journal", fake_fetch)
    monkeypatch.setattr(cj_sync, "clean_daily_fields", fake_clean)

    with (
        TestClient(app) as super_client,
        TestClient(app) as teacher_client,
        TestClient(app) as student_client,
    ):
        _register(super_client, "sasha.lin@basischina.com", "super-desk-41", "Sasha Lin")
        _register(student_client, "mia.chen@basischina.com", "student-hall-42", "Mia Chen")
        teacher = _register(teacher_client, "evan.wu@basischina.com", "teacher-lab-43", "Evan Wu")
        promoted = super_client.patch(
            f"/api/v1/admin/users/{teacher.json()['id']}",
            json={"roles": ["teacher"]},
        )
        assert promoted.status_code == 200, promoted.text
        assert teacher_client.post("/api/v1/auth/logout").status_code == 204
        teacher_login = teacher_client.post(
            "/api/v1/auth/login",
            json={"email": "evan.wu@basischina.com", "password": "teacher-lab-43"},
        )
        assert teacher_login.status_code == 200, teacher_login.text

        missing = super_client.post("/api/v1/cj/sync")
        assert missing.status_code == 503, missing.text
        assert missing.json()["error"]["code"] == "service_unavailable"
        recorded = super_client.get("/api/v1/cj/sync")
        assert recorded.status_code == 200, recorded.text
        assert recorded.json()["status"] == "error"
        assert recorded.json()["courses"] == 0
        assert teacher_client.post("/api/v1/cj/sync").status_code == 403
        assert student_client.get("/api/v1/cj/sync").status_code == 403

        app.state.settings = replace(
            app.state.settings,
            cj_journal_base_url="https://staging.myclassroomjournal.com",
            cj_journal_api_key="test-journal-key",
            deepseek_api_key="test-deepseek-key",
            deepseek_model="deepseek-chat",
        )
        cj_sync.sync_lock.acquire()
        try:
            busy = super_client.post("/api/v1/cj/sync")
        finally:
            cj_sync.sync_lock.release()
        assert busy.status_code == 409, busy.text
        assert busy.json()["error"]["code"] == "sync_in_progress"
        assert calls["fetch"] == 0

        def fail_clean(_api_key, _model, _items):
            raise ApiError(503, "service_unavailable", "DeepSeek could not clean the journal text.")

        monkeypatch.setattr(cj_sync, "clean_daily_fields", fail_clean)
        failed = super_client.post("/api/v1/cj/sync")
        assert failed.status_code == 503, failed.text
        untouched = student_client.get("/api/v1/cj?week_start=2026-10-12")
        assert untouched.status_code == 200, untouched.text
        assert any(subject["id"] == "ap-calculus-11ac" for subject in untouched.json()["subjects"])
        assert untouched.json()["entries"] == []

        monkeypatch.setattr(cj_sync, "clean_daily_fields", fake_clean)
        saved = super_client.post("/api/v1/cj/sync")
        assert saved.status_code == 200, saved.text
        assert saved.json()["status"] == "ok"
        assert saved.json()["from"] == "2026-10-12"
        assert saved.json()["to"] == "2026-10-23"
        assert saved.json()["courses"] == 1
        assert saved.json()["entries"] == 1
        viewed = student_client.get("/api/v1/cj?week_start=2026-10-12")
        assert viewed.status_code == 200, viewed.text
        calculus = next(subject for subject in viewed.json()["subjects"] if subject["id"] == "ap-calculus-11ac")
        assert all(subject["id"] != "bbgm-calc" for subject in viewed.json()["subjects"])
        assert calculus["teacher"] == "Kyle Sheldon Manzoni"
        assert calculus["room"] == "E522"
        assert calculus["default_period"] == 10
        entry = next(item for item in viewed.json()["entries"] if item["subject_id"] == "ap-calculus-11ac")
        assert entry["ic"] == "Limits review"
        assert entry["hw"] == "FRQ"
        assert entry["announcement"] == "Quiz"
        assert entry["day_index"] == 0
        assert entry["period"] == 10

        payloads["items"] = [{**course, "daily_content": []}]
        cleared = super_client.post("/api/v1/cj/sync")
        assert cleared.status_code == 200, cleared.text
        after = student_client.get("/api/v1/cj?week_start=2026-10-12")
        cleared_entry = next(item for item in after.json()["entries"] if item["subject_id"] == "ap-calculus-11ac")
        assert cleared_entry["ic"] == ""
        assert cleared_entry["hw"] == ""
        assert cleared_entry["announcement"] == ""
        latest = super_client.get("/api/v1/cj/sync")
        assert latest.json()["status"] == "ok"
        assert latest.json()["courses"] == 1
    app.state.engine.dispose()
    app.state.core_engine.dispose()


def test_cj_photo_files_homework(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="sasha.lin@basischina.com")

    def fake_reading(_key, _image, _content_type, subjects):
        match = next(item for item in subjects if item["id"] == "ap-calculus-11ac")
        return {
            "subject_id": match["id"],
            "ic": "Limits review",
            "hw": "Complete FRQ Set 2",
            "announcement": "",
            "transcribed": "Complete FRQ",
            "inferred": "Set 2",
        }

    monkeypatch.setattr("routers.cj.recognize_homework", fake_reading)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with TestClient(app) as client, TestClient(app) as student:
        created = _register(client, "sasha.lin@basischina.com", "super-desk-41", "Sasha Lin")
        assert created.status_code == 201, created.text
        _register(student, "mia.chen@basischina.com", "student-hall-42", "Mia Chen")
        denied = student.post(
            "/api/v1/cj/recognize",
            data={"week_start": "2026-10-05", "day_index": "0"},
            files={"image": ("hw.png", png, "image/png")},
        )
        assert denied.status_code == 403
        filed = client.post(
            "/api/v1/cj/recognize",
            data={"week_start": "2026-10-05", "day_index": "0"},
            files={"image": ("hw.png", png, "image/png")},
        )
        assert filed.status_code == 200, filed.text
        body = filed.json()
        assert body["subject_id"] == "ap-calculus-11ac"
        assert body["hw"] == "Complete FRQ Set 2"
        assert body["inferred"] == "Set 2"
        listed = client.get("/api/v1/cj?week_start=2026-10-05")
        saved = next(item for item in listed.json()["entries"] if item["id"] == body["id"])
        assert saved["hw"] == "Complete FRQ Set 2"
        assert saved["day_index"] == 0
    app.state.engine.dispose()


def test_forum_feeds_rank_by_likes_or_time(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        registered = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert registered.status_code == 201, registered.text
        ids = []
        for index in range(11):
            created = client.post(
                "/api/v1/posts",
                json={"title": f"Forum note {index}", "body": "Still on the board.", "category": "forum"},
            )
            assert created.status_code == 201, created.text
            ids.append(created.json()["id"])
        opened = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with Session(app.state.engine) as db:
            for index, post_id in enumerate(ids):
                db.get(Post, post_id).created_at = opened + timedelta(seconds=index)
            db.commit()
        liked = client.post(f"/api/v1/posts/{ids[0]}/likes")
        assert liked.status_code == 201, liked.text
        for body_text in ("First note.", "Second note."):
            commented = client.post(f"/api/v1/posts/{ids[5]}/comments", json={"body": body_text})
            assert commented.status_code == 201, commented.text
        one_comment = client.post(f"/api/v1/posts/{ids[10]}/comments", json={"body": "One note."})
        assert one_comment.status_code == 201, one_comment.text

        recommended = client.get("/api/v1/posts?category=forum&feed=recommended&page_size=50")
        assert recommended.status_code == 200, recommended.text
        body = recommended.json()
        assert body["total"] == 10
        assert len(body["items"]) == 10
        assert body["page_size"] == 10
        assert [item["id"] for item in body["items"][:3]] == [ids[5], ids[0], ids[10]]
        assert body["items"][0]["reply_count"] == 2
        assert body["items"][1]["like_count"] == 1
        assert ids[1] not in {item["id"] for item in body["items"]}

        default = client.get("/api/v1/posts?category=forum")
        assert default.json()["items"][0]["id"] == ids[5]

        latest = client.get("/api/v1/posts?category=forum&feed=latest")
        assert latest.json()["total"] == 10
        assert len(latest.json()["items"]) == 10
        assert latest.json()["items"][0]["id"] == ids[10]

        everything = client.get("/api/v1/posts?category=forum&feed=all")
        assert everything.json()["total"] == 11
        assert everything.json()["items"][0]["id"] == ids[10]

        deeper = client.get("/api/v1/posts?category=forum&feed=recommended&page=2")
        assert deeper.status_code == 422
        assert any(field["field"] == "page" for field in deeper.json()["error"]["fields"])

        mixed = client.get("/api/v1/posts?category=news&feed=recommended")
        assert mixed.status_code == 422
        assert any(field["field"] == "feed" for field in mixed.json()["error"]["fields"])
    app.state.engine.dispose()


def test_forum_keyword_reorders_for_that_request(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        registered = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert registered.status_code == 201
        specs = [
            ("Alpha notes", "nothing special"),
            ("Pinned plain", "still plain"),
            ("Also plain", "still plain"),
        ]
        created = []
        for title, body in specs:
            post = client.post(
                "/api/v1/posts",
                json={"title": title, "body": body, "category": "forum"},
            )
            assert post.status_code == 201, post.text
            created.append(post.json()["id"])
        opened = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with Session(app.state.engine) as db:
            for index, post_id in enumerate(created):
                db.get(Post, post_id).created_at = opened + timedelta(seconds=index)
            db.commit()
        pinned = client.post(f"/api/v1/posts/{created[1]}/pin", json={"pinned": True})
        assert pinned.status_code == 200, pinned.text

        plain = client.get("/api/v1/posts", params={"category": "forum", "feed": "all"})
        assert [item["id"] for item in plain.json()["items"]] == [created[1], created[2], created[0]]

        ranked = client.get("/api/v1/posts", params={"category": "forum", "feed": "all", "q": "ALPHA"})
        assert ranked.status_code == 200, ranked.text
        assert ranked.json()["total"] == 3
        assert [item["id"] for item in ranked.json()["items"]] == [created[0], created[1], created[2]]

        by_body = client.get("/api/v1/posts", params={"category": "forum", "feed": "all", "q": "special"})
        assert by_body.json()["items"][0]["id"] == created[0]

        guest = TestClient(app)
        untouched = guest.get("/api/v1/posts", params={"category": "forum", "feed": "all"})
        assert [item["id"] for item in untouched.json()["items"]] == [created[1], created[2], created[0]]

        blank = client.get("/api/v1/posts", params={"category": "forum", "feed": "all", "q": "   "})
        assert [item["id"] for item in blank.json()["items"]] == [created[1], created[2], created[0]]

        literal = client.post(
            "/api/v1/posts",
            json={"title": "100% sure", "body": "yes", "category": "forum"},
        )
        decoy = client.post(
            "/api/v1/posts",
            json={"title": "1000 sure", "body": "no", "category": "forum"},
        )
        assert literal.status_code == 201 and decoy.status_code == 201
        found = client.get("/api/v1/posts", params={"category": "forum", "feed": "all", "q": "100%"})
        found_ids = [item["id"] for item in found.json()["items"]]
        assert found_ids[0] == literal.json()["id"]
        assert decoy.json()["id"] in found_ids[1:]

        too_long = client.get("/api/v1/posts", params={"category": "forum", "q": "a" * 81})
        assert too_long.status_code == 422
        assert any(field["field"] == "q" for field in too_long.json()["error"]["fields"])

        wrong = client.get("/api/v1/posts", params={"category": "news", "q": "alpha"})
        assert wrong.status_code == 422
        assert any(field["field"] == "q" for field in wrong.json()["error"]["fields"])

        crowd = []
        for index in range(11):
            post = client.post(
                "/api/v1/posts",
                json={"title": f"Crowd {index}", "body": "ordinary", "category": "forum"},
            )
            assert post.status_code == 201, post.text
            crowd.append(post.json()["id"])
        with Session(app.state.engine) as db:
            db.get(Post, crowd[0]).body = "ordinary zeppelin"
            base = datetime(2026, 11, 1, tzinfo=timezone.utc)
            for index, post_id in enumerate(crowd):
                db.get(Post, post_id).created_at = base + timedelta(seconds=index)
            db.commit()

        before = client.get("/api/v1/posts", params={"category": "forum", "feed": "recommended"})
        assert crowd[0] not in {item["id"] for item in before.json()["items"]}
        after = client.get("/api/v1/posts", params={"category": "forum", "feed": "recommended", "q": "zeppelin"})
        assert after.json()["total"] == 10
        assert after.json()["items"][0]["id"] == crowd[0]
    app.state.engine.dispose()


def test_author_withdraws_own_comment(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as author, TestClient(app) as other:
        registered = _register(author, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert registered.status_code == 201
        post = author.post(
            "/api/v1/posts",
            json={"title": "Laundry chat", "body": "Who still has quarters?", "category": "forum"},
        )
        assert post.status_code == 201, post.text
        post_id = post.json()["id"]
        first = author.post(f"/api/v1/posts/{post_id}/comments", json={"body": "I have a roll."})
        second = author.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Come by 312."})
        assert first.status_code == 201 and second.status_code == 201
        comment_id = first.json()["id"]

        guest = TestClient(app)
        unauth = guest.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert unauth.status_code == 401

        stranger = _register(other, "priya.nair@basischina.com", "west-hall-8", "Priya Nair")
        assert stranger.status_code == 201
        denied = other.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert denied.status_code == 403
        still = guest.get(f"/api/v1/posts/{post_id}/comments")
        assert still.json()["total"] == 2

        withdrawn = author.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert withdrawn.status_code == 204, withdrawn.text
        assert withdrawn.content == b""
        left = guest.get(f"/api/v1/posts/{post_id}/comments")
        assert left.json()["total"] == 1
        assert left.json()["items"][0]["body"] == "Come by 312."
        card = guest.get("/api/v1/posts", params={"category": "forum"}).json()["items"][0]
        assert card["reply_count"] == 1
        assert [item["body"] for item in card["reply_preview"]] == ["Come by 312."]

        missing = author.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert missing.status_code == 404
        patched = author.patch(f"/api/v1/posts/{post_id}/comments/{second.json()['id']}", json={"body": "no"})
        assert patched.status_code == 405
    app.state.engine.dispose()


def test_admin_deletes_another_users_comment(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert student.status_code == 201
        created = client.post(
            "/api/v1/posts",
            json={"title": "Who still has the dorm key", "body": "It was on the oak table.", "category": "forum"},
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        replied = client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "I saw it after dinner."},
        )
        assert replied.status_code == 201, replied.text
        comment_id = replied.json()["id"]

        other = _register(client, "priya.nair@basischina.com", "east-hall-9", "Priya Nair")
        assert other.status_code == 201
        denied = client.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert denied.status_code == 403
        assert client.get(f"/api/v1/posts/{post_id}/comments").json()["total"] == 1

        admin = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert admin.status_code == 201
        assert "super_admin" in admin.json()["roles"]
        removed = client.delete(f"/api/v1/posts/{post_id}/comments/{comment_id}")
        assert removed.status_code == 204, removed.text
        assert client.get(f"/api/v1/posts/{post_id}").status_code == 200
        assert client.get(f"/api/v1/posts/{post_id}/comments").json()["total"] == 0
        card = client.get("/api/v1/posts", params={"category": "forum"}).json()["items"][0]
        assert card["reply_count"] == 0

        client.cookies.clear()
        logged_in = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert logged_in.status_code == 200
        notices = client.get("/api/v1/me/notices")
        assert notices.status_code == 200
        assert any("Who still has the dorm key" in item["body"] for item in notices.json()["items"])
    app.state.engine.dispose()


def test_roles_stack_and_super_admin_stays(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        admin = _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert admin.status_code == 201
        student = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        student_id = student.json()["id"]
        client.cookies.clear()
        client.post(
            "/api/v1/auth/login",
            json={"email": "ada.min@basischina.com", "password": "desk-key-99"},
        )

        stacked = client.patch(
            f"/api/v1/admin/users/{student_id}",
            json={"roles": ["teacher", "editor"]},
        )
        assert stacked.status_code == 200, stacked.text
        assert stacked.json()["roles"] == ["teacher", "editor"]

        empty = client.patch(f"/api/v1/admin/users/{student_id}", json={"roles": []})
        assert empty.status_code == 422
        assert empty.json()["error"]["fields"][0]["field"] == "roles"

        granted = client.patch(
            f"/api/v1/admin/users/{student_id}",
            json={"roles": ["teacher", "super_admin"]},
        )
        assert granted.status_code == 422

        self_roles = client.patch(
            f"/api/v1/admin/users/{admin.json()['id']}",
            json={"roles": []},
        )
        assert self_roles.status_code == 200, self_roles.text
        assert self_roles.json()["roles"] == ["super_admin"]

        mute_self = client.patch(
            f"/api/v1/admin/users/{admin.json()['id']}",
            json={"muted": True},
        )
        assert mute_self.status_code == 403
    app.state.engine.dispose()


def test_super_admin_pins_published_post_to_the_front(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as admin, TestClient(app) as student:
        registered = _register(admin, "ada.min@basischina.com", "desk-key-99", "Ada Min")
        assert registered.status_code == 201
        assert "super_admin" in registered.json()["roles"]
        older = admin.post(
            "/api/v1/posts",
            json={"title": "Older note", "body": "First.", "category": "forum"},
        )
        time.sleep(1.1)
        newer = admin.post(
            "/api/v1/posts",
            json={"title": "Newer note", "body": "Second.", "category": "forum"},
        )
        assert older.status_code == 201 and newer.status_code == 201
        assert older.json()["pinned"] is False
        pinned = admin.post(f"/api/v1/posts/{older.json()['id']}/pin", json={"pinned": True})
        assert pinned.status_code == 200, pinned.text
        assert pinned.json()["pinned"] is True
        listing = admin.get("/api/v1/posts?category=forum&feed=latest")
        assert listing.status_code == 200, listing.text
        assert listing.json()["items"][0]["id"] == older.json()["id"]
        pupil = _register(student, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert pupil.status_code == 201
        denied = student.post(f"/api/v1/posts/{older.json()['id']}/pin", json={"pinned": False})
        assert denied.status_code == 403
        cleared = admin.post(f"/api/v1/posts/{older.json()['id']}/pin", json={"pinned": False})
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["pinned"] is False
        restored = admin.get("/api/v1/posts?category=forum&feed=latest")
        assert restored.json()["items"][0]["id"] == newer.json()["id"]
        draft = admin.post("/api/v1/news/drafts", json={"title": "Not live"})
        assert draft.status_code == 201, draft.text
        blocked = admin.post(f"/api/v1/posts/{draft.json()['id']}/pin", json={"pinned": True})
        assert blocked.status_code == 422
        assert blocked.json()["error"]["fields"][0]["field"] == "pinned"
    app.state.engine.dispose()


def test_forum_activity_badge_tracks_other_people_only(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as author, TestClient(app) as other:
        assert _register(author, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale").status_code == 201
        assert _register(other, "priya.nair@basischina.com", "west-hall-8", "Priya Nair").status_code == 201
        assert author.get("/api/v1/me/forum-activity").json() == {"unread": 0}
        assert TestClient(app).get("/api/v1/me/forum-activity").status_code == 401

        created = author.post(
            "/api/v1/posts",
            json={"title": "Locker note", "body": "Left on the board.", "category": "forum"},
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        assert author.post(f"/api/v1/posts/{post_id}/likes").status_code == 201
        assert author.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "Adding this myself."},
        ).status_code == 201
        assert author.get("/api/v1/me/forum-activity").json()["unread"] == 0

        assert other.post(f"/api/v1/posts/{post_id}/likes").status_code == 201
        assert author.get("/api/v1/me/forum-activity").json() == {"unread": 1}
        assert other.get("/api/v1/me/forum-activity").json()["unread"] == 0

        read = author.post("/api/v1/me/forum-activity/read")
        assert read.status_code == 204
        assert author.get("/api/v1/me/forum-activity").json()["unread"] == 0

        time.sleep(1.1)
        commented = other.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"body": "Saw this on the board."},
        )
        assert commented.status_code == 201, commented.text
        assert author.get("/api/v1/me/forum-activity").json()["unread"] == 1
        assert author.post("/api/v1/me/forum-activity/read").status_code == 204

        time.sleep(1.1)
        assert other.delete(f"/api/v1/posts/{post_id}/likes").status_code == 200
        assert other.post(f"/api/v1/posts/{post_id}/likes").status_code == 201
        assert author.get("/api/v1/me/forum-activity").json()["unread"] == 1
        assert other.delete(f"/api/v1/posts/{post_id}/likes").status_code == 200
        assert author.get("/api/v1/me/forum-activity").json()["unread"] == 0
    app.state.engine.dispose()


def _legacy_hash(password: str, iterations: int = 100_000) -> str:
    salt = "0123456789abcdef0123456789abcdef"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def test_password_hashes_use_owasp_iterations_and_upgrade_on_login(tmp_path, monkeypatch):
    # Same password hashed twice must use different salts.
    assert hash_password("same-password") != hash_password("same-password")

    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        registered = _register(client, "jordan.hale@basischina.com", "east-hall-8", "Jordan Hale")
        assert registered.status_code == 201, registered.text
        user_id = registered.json()["id"]

        with Session(app.state.core_engine) as db:
            user = db.get(User, user_id)
            assert user.password_hash.startswith("pbkdf2_sha256$600000$")
            fresh_hash = user.password_hash
            user.password_hash = _legacy_hash("east-hall-8", 100_000)
            db.commit()

        wrong = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "wrong-pass"},
        )
        assert wrong.status_code == 401

        # A legacy 100k hash still logs in, then is transparently upgraded.
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "jordan.hale@basischina.com", "password": "east-hall-8"},
        )
        assert login.status_code == 200, login.text
        with Session(app.state.core_engine) as db:
            user = db.get(User, user_id)
            assert user.password_hash.startswith("pbkdf2_sha256$600000$")
            assert user.password_hash != fresh_hash
    app.state.engine.dispose()


def _login(client, email, password):
    client.cookies.clear()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def _notice_bodies(client):
    listed = client.get("/api/v1/me/notices")
    assert listed.status_code == 200, listed.text
    return [item["body"] for item in listed.json()["items"]]


def test_drift_bottles_are_anonymous_and_private(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch, admin_email="ada.min@basischina.com")
    with TestClient(app) as client:
        assert _register(client, "ada.min@basischina.com", "desk-key-99", "Ada Min").status_code == 201
        assert _register(client, "amy.throw@basischina.com", "east-hall-8", "Amy Thrower").status_code == 201
        assert _register(client, "ben.pick@basischina.com", "west-hall-8", "Ben Picker").status_code == 201
        cara = _register(client, "cara.pick@basischina.com", "north-hall-8", "Cara Second")
        assert cara.status_code == 201
        cara_id = cara.json()["id"]
        assert _register(client, "dee.outsider@basischina.com", "south-hall-8", "Dee Outsider").status_code == 201

        client.cookies.clear()
        assert client.post("/api/v1/bottles", json={"body": "nobody home"}).status_code == 401
        assert client.get("/api/v1/bottles/mine").status_code == 401
        assert client.get("/api/v1/me/bottle-activity").status_code == 401

        _login(client, "amy.throw@basischina.com", "east-hall-8")
        blank = client.post("/api/v1/bottles", json={"body": "   "})
        assert blank.status_code == 422
        assert blank.json()["error"]["fields"][0]["field"] == "body"
        too_long = client.post("/api/v1/bottles", json={"body": "a" * 501})
        assert too_long.status_code == 422
        first = client.post("/api/v1/bottles", json={"body": "first bottle on the water"})
        assert first.status_code == 201, first.text
        first_id = first.json()["id"]
        assert "display_name" not in first.text
        assert "author_id" not in first.text
        own = client.post("/api/v1/bottles/pick")
        assert own.status_code == 200, own.text
        assert own.json()["pick"] is None
        mine = client.get("/api/v1/bottles/mine")
        assert mine.status_code == 200, mine.text
        assert mine.json()["thrown"][0]["pick_id"] is None
        assert mine.json()["thrown"][0]["excerpt"] == "first bottle on the water"

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        ben_pick = client.post("/api/v1/bottles/pick")
        assert ben_pick.status_code == 200, ben_pick.text
        ben_thread = ben_pick.json()["pick"]
        assert ben_thread["bottle_id"] == first_id
        assert ben_thread["bottle_body"] == "first bottle on the water"
        assert ben_thread["role"] == "picker"
        for secret in ("Amy Thrower", "Ben Picker", "Cara Second", "amy.throw@", "display_name", "author_id", "picker_id"):
            assert secret not in ben_pick.text

        _login(client, "cara.pick@basischina.com", "north-hall-8")
        cara_pick = client.post("/api/v1/bottles/pick")
        assert cara_pick.status_code == 200, cara_pick.text
        cara_thread = cara_pick.json()["pick"]
        assert cara_thread["bottle_id"] == first_id
        assert cara_thread["id"] != ben_thread["id"]
        assert "Amy Thrower" not in cara_pick.text

        _login(client, "dee.outsider@basischina.com", "south-hall-8")
        assert client.get(f"/api/v1/bottles/picks/{ben_thread['id']}").status_code == 403
        assert client.get("/api/v1/bottles/reports").status_code == 403

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        ben_reply = client.post(
            f"/api/v1/bottles/picks/{ben_thread['id']}/messages",
            json={"body": "secret-from-ben"},
        )
        assert ben_reply.status_code == 201, ben_reply.text
        ben_message_id = ben_reply.json()["id"]
        assert ben_reply.json()["mine"] is True
        assert ben_reply.json()["from"] == "picker"
        assert "author_id" not in ben_reply.text

        _login(client, "cara.pick@basischina.com", "north-hall-8")
        cara_view = client.get(f"/api/v1/bottles/picks/{cara_thread['id']}")
        assert cara_view.status_code == 200, cara_view.text
        assert "secret-from-ben" not in cara_view.text
        assert "display_name" not in cara_view.text
        cara_reply = client.post(
            f"/api/v1/bottles/picks/{cara_thread['id']}/messages",
            json={"body": "secret-from-cara"},
        )
        assert cara_reply.status_code == 201, cara_reply.text
        cara_message_id = cara_reply.json()["id"]

        _login(client, "amy.throw@basischina.com", "east-hall-8")
        amy_ben = client.get(f"/api/v1/bottles/picks/{ben_thread['id']}")
        amy_cara = client.get(f"/api/v1/bottles/picks/{cara_thread['id']}")
        assert "secret-from-ben" in amy_ben.text
        assert "secret-from-cara" not in amy_ben.text
        assert "secret-from-cara" in amy_cara.text
        assert "secret-from-ben" not in amy_cara.text
        assert "display_name" not in amy_ben.text
        assert "Ben Picker" not in amy_ben.text
        assert client.get("/api/v1/me/bottle-activity").json()["unread"] == 1
        assert client.post(f"/api/v1/bottles/picks/{ben_thread['id']}/read").status_code == 204
        assert client.get("/api/v1/me/bottle-activity").json()["unread"] == 1
        assert client.post(f"/api/v1/bottles/picks/{cara_thread['id']}/read").status_code == 204
        assert client.get("/api/v1/me/bottle-activity").json()["unread"] == 0

        second = client.post("/api/v1/bottles", json={"body": "second bottle"})
        third = client.post("/api/v1/bottles", json={"body": "third bottle"})
        assert second.status_code == 201
        assert third.status_code == 201
        fourth = client.post("/api/v1/bottles", json={"body": "fourth bottle"})
        assert fourth.status_code == 403
        assert fourth.json()["error"]["code"] == "forbidden"
        assert client.get("/api/v1/bottles/mine").json()["thrown"]
        still_three = [
            item["bottle_id"]
            for item in client.get("/api/v1/bottles/mine").json()["thrown"]
        ]
        assert set(still_three) == {first_id, second.json()["id"], third.json()["id"]}

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        again = client.post("/api/v1/bottles/pick")
        last = client.post("/api/v1/bottles/pick")
        assert {again.json()["pick"]["bottle_body"], last.json()["pick"]["bottle_body"]} == {
            "second bottle",
            "third bottle",
        }
        assert client.post("/api/v1/bottles/pick").json()["pick"] is None
        ben_bottle = client.post("/api/v1/bottles", json={"body": "ben only bottle"})
        assert ben_bottle.status_code == 201, ben_bottle.text
        assert client.post("/api/v1/bottles/pick").json()["pick"] is None
        before_withdraw = _notice_bodies(client)
        withdrawn = client.delete(
            f"/api/v1/bottles/picks/{ben_thread['id']}/messages/{ben_message_id}"
        )
        assert withdrawn.status_code == 204, withdrawn.text
        assert _notice_bodies(client) == before_withdraw

        _login(client, "amy.throw@basischina.com", "east-hall-8")
        after_withdraw = client.get(f"/api/v1/bottles/picks/{ben_thread['id']}")
        assert "secret-from-ben" not in after_withdraw.text
        assert client.get("/api/v1/bottles/reports").status_code == 403
        assert client.post(f"/api/v1/bottles/picks/{cara_thread['id']}/report").status_code == 204

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        assert client.post(f"/api/v1/bottles/picks/{ben_thread['id']}/report").status_code == 204
        assert client.post(f"/api/v1/bottles/picks/{ben_thread['id']}/report").status_code == 204

        _login(client, "ada.min@basischina.com", "desk-key-99")
        reports = client.get("/api/v1/bottles/reports")
        assert reports.status_code == 200, reports.text
        reported_picks = {item["pick_id"] for item in reports.json()["items"]}
        assert ben_thread["id"] in reported_picks
        assert cara_thread["id"] in reported_picks
        opened = client.get(f"/api/v1/bottles/picks/{ben_thread['id']}")
        assert opened.status_code == 200, opened.text
        assert opened.json()["thrower"]["email"] == "amy.throw@basischina.com"
        assert opened.json()["picker"]["email"] == "ben.pick@basischina.com"
        assert opened.json()["thrower"]["display_name"] == "Amy Thrower"
        removed_reply = client.delete(
            f"/api/v1/bottles/picks/{cara_thread['id']}/messages/{cara_message_id}"
        )
        assert removed_reply.status_code == 204, removed_reply.text
        removed_bottle = client.delete(f"/api/v1/bottles/{first_id}")
        assert removed_bottle.status_code == 204, removed_bottle.text

        _login(client, "cara.pick@basischina.com", "north-hall-8")
        cara_notices = _notice_bodies(client)
        assert "Your reply in a drift bottle was removed." in cara_notices
        assert all("Ada" not in body and "Amy" not in body and "Ben" not in body for body in cara_notices)
        assert client.get(f"/api/v1/bottles/picks/{cara_thread['id']}").status_code == 404

        _login(client, "amy.throw@basischina.com", "east-hall-8")
        amy_notices = _notice_bodies(client)
        assert "Your drift bottle was removed." in amy_notices
        assert client.get(f"/api/v1/bottles/picks/{ben_thread['id']}").status_code == 404
        before_own_delete = _notice_bodies(client)
        assert client.delete(f"/api/v1/bottles/{second.json()['id']}").status_code == 204
        assert client.delete(f"/api/v1/bottles/{third.json()['id']}").status_code == 204
        assert _notice_bodies(client) == before_own_delete

        _login(client, "cara.pick@basischina.com", "north-hall-8")
        picked_ben = client.post("/api/v1/bottles/pick")
        assert picked_ben.status_code == 200, picked_ben.text
        assert picked_ben.json()["pick"]["bottle_body"] == "ben only bottle"
        ben_only_pick = picked_ben.json()["pick"]["id"]

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        later = client.post(
            f"/api/v1/bottles/picks/{ben_only_pick}/messages",
            json={"body": "ben-later"},
        )
        assert later.status_code == 201, later.text

        _login(client, "ada.min@basischina.com", "desk-key-99")
        users = client.get("/api/v1/admin/users?page_size=50")
        assert users.status_code == 200, users.text
        ben_id = next(item["id"] for item in users.json()["items"] if item["email"] == "ben.pick@basischina.com")
        muted = client.patch(f"/api/v1/admin/users/{ben_id}", json={"muted": True})
        assert muted.status_code == 200, muted.text

        _login(client, "ben.pick@basischina.com", "west-hall-8")
        muted_throw = client.post("/api/v1/bottles", json={"body": "should fail"})
        muted_pick = client.post("/api/v1/bottles/pick")
        assert muted_throw.status_code == 403
        assert muted_throw.json()["error"]["code"] == "account_muted"
        assert muted_pick.status_code == 403
        assert muted_pick.json()["error"]["code"] == "account_muted"
        assert client.get("/api/v1/bottles/mine").status_code == 200
        assert client.get(f"/api/v1/bottles/picks/{ben_only_pick}").status_code == 200
        assert client.delete(
            f"/api/v1/bottles/picks/{ben_only_pick}/messages/{later.json()['id']}"
        ).status_code == 204
        assert client.delete(f"/api/v1/bottles/{ben_bottle.json()['id']}").status_code == 204

        _login(client, "cara.pick@basischina.com", "north-hall-8")
        gone = client.post("/api/v1/bottles", json={"body": "gone-with-cara"})
        assert gone.status_code == 201, gone.text

        _login(client, "dee.outsider@basischina.com", "south-hall-8")
        found = client.post("/api/v1/bottles/pick")
        assert found.json()["pick"]["bottle_body"] == "gone-with-cara"
        gone_pick = found.json()["pick"]["id"]

        _login(client, "ada.min@basischina.com", "desk-key-99")
        assert client.delete(f"/api/v1/admin/users/{cara_id}").status_code == 204

        _login(client, "dee.outsider@basischina.com", "south-hall-8")
        assert client.get(f"/api/v1/bottles/picks/{gone_pick}").status_code == 404
        assert client.post("/api/v1/bottles/pick").json()["pick"] is None
        client.cookies.clear()
        assert client.post(
            "/api/v1/auth/login",
            json={"email": "cara.pick@basischina.com", "password": "north-hall-8"},
        ).status_code == 401
    app.state.engine.dispose()


def test_play_login_illegal_move_and_shared_room(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    with TestClient(app) as ada, TestClient(app) as ben:
        assert ada.post("/api/v1/games/gomoku/play", json={"moves": [], "side": "black"}).status_code == 401
        assert ada.post("/api/v1/games/chess/play", json={}).status_code == 401
        assert ada.post("/api/v1/games/gomoku/rooms", json={}).status_code == 401
        assert ada.post("/api/v1/games/chess/rooms", json={}).status_code == 401

        assert _register(ada, "ada.play@basischina.com", "desk-key-99", "Ada Min").status_code == 201
        illegal = ada.post(
            "/api/v1/games/gomoku/play",
            json={
                "moves": [{"row": 7, "col": 7, "player": "white"}],
                "difficulty": "easy",
                "side": "black",
            },
        )
        assert illegal.status_code == 200, illegal.text
        rejected = illegal.json()
        assert rejected["status"] == "error"
        assert rejected["engine_move"] is None
        assert rejected["moves"] == [{"row": 7, "col": 7, "player": "white"}]

        monkeypatch.setattr(
            "games.ai.call_chess_api",
            lambda fen, depth=None, max_thinking_time=50, variants=1: {"move": "e7e5", "eval": 0.2},
        )
        played = ada.post(
            "/api/v1/games/chess/play",
            json={"uci": "e2e4", "difficulty": "hard", "side": "white"},
        )
        assert played.status_code == 200, played.text
        position = played.json()
        assert position["status"] == "success"
        assert position["user_uci"] == "e2e4"
        assert position["engine_uci"] == "e7e5"
        assert "4P3" in position["fen"]
        assert "4p3" in position["fen"]

        created = ada.post("/api/v1/games/gomoku/rooms", json={"seat": "black", "clock": False})
        assert created.status_code == 200, created.text
        room = created.json()
        assert room["status"] == "success"
        assert room["black_name"] == "Ada Min"
        code = room["code"]
        token_a = room["token"]

        assert _register(ben, "ben.play@basischina.com", "west-hall-8", "Ben Lu").status_code == 201
        joined = ben.post(f"/api/v1/games/gomoku/rooms/{code}/join", json={})
        assert joined.status_code == 200, joined.text
        seat = joined.json()
        assert seat["status"] == "success"
        assert seat["seat"] == "white"
        assert seat["white_name"] == "Ben Lu"
        assert seat["black_name"] == "Ada Min"

        with ada.websocket_connect(
            f"/api/v1/games/gomoku/rooms/{code}/ws?token={token_a}"
        ) as ws_a:
            assert ws_a.receive_json()["turn"] == "black"
            with ben.websocket_connect(
                f"/api/v1/games/gomoku/rooms/{code}/ws?token={seat['token']}"
            ) as ws_b:
                assert ws_a.receive_json()["white_ready"] is True
                opened = ws_b.receive_json()
                assert opened["moves"] == []
                assert opened["turn"] == "black"
                ws_b.send_json({"type": "move", "row": 7, "col": 7})
                denied = ws_b.receive_json()
                assert denied["status"] == "error"
                ws_a.send_json({"type": "move", "row": 7, "col": 7})
                synced = ws_b.receive_json()
                assert synced["moves"] == [{"row": 7, "col": 7, "player": "black"}]
                assert synced["turn"] == "white"
    app.state.engine.dispose()
