import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import avatars
from errors import StorageError
from mail import peek_console_code
from main import create_app
from models import AuditEvent, Post
from validate import normalize_email


def _make_app(tmp_path, monkeypatch, name="scoop.db", admin_email=""):
    monkeypatch.setenv("SESSION_SECRET", "pytest-session-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / name}")
    monkeypatch.setenv("CORE_DATABASE_URL", f"sqlite:///{tmp_path / ('core_' + name)}")
    monkeypatch.setenv("FRONTEND_ORIGIN", "http://localhost:5173")
    monkeypatch.setenv("ADMIN_EMAIL", admin_email)
    monkeypatch.setenv("MAIL_BACKEND", "console")
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
        assert admin_client.get("/api/v1/cj/teachers").status_code == 403
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
        assigned_subject = all_subjects[0]["id"]
        other_subject = all_subjects[1]["id"]

        assigned = super_client.put(
            f"/api/v1/cj/teachers/{teacher_id}",
            json={"subject_ids": [assigned_subject]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["subject_ids"] == [assigned_subject]

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

        multiple_assignment = super_client.put(
            f"/api/v1/cj/teachers/{teacher_id}",
            json={"subject_ids": [assigned_subject, other_subject]},
        )
        assert multiple_assignment.status_code == 422

        entry = {
            "week_start": "2026-10-05",
            "day_index": 0,
            "subject_id": assigned_subject,
            "ic": "Role-scoped update",
            "hw": "Page 1",
            "announcement": "Bring a pencil",
        }
        assert student_client.put("/api/v1/cj", json=entry).status_code == 403
        teacher_saved = teacher_client.put("/api/v1/cj", json=entry)
        assert teacher_saved.status_code == 200, teacher_saved.text
        outside_saved = teacher_client.put(
            "/api/v1/cj", json={**entry, "subject_id": other_subject}
        )
        assert outside_saved.status_code == 200, outside_saved.text
        teacher_exam = teacher_client.put(
            "/api/v1/cj/exams",
            json={
                "week_start": "2026-10-05",
                "day_index": 2,
                "subject_id": assigned_subject,
                "title": "Teacher subject quiz",
                "time": "09:30",
                "location": "Room 101",
                "note": "",
            },
        )
        assert teacher_exam.status_code == 200, teacher_exam.text
        outside_exam = teacher_client.put(
            "/api/v1/cj/exams",
            json={
                "week_start": "2026-10-05",
                "day_index": 2,
                "subject_id": other_subject,
                "title": "Outside assignment",
                "time": "09:30",
                "location": "Room 101",
                "note": "",
            },
        )
        assert outside_exam.status_code == 200, outside_exam.text
        assert teacher_client.delete(
            f"/api/v1/cj/exams/{outside_exam.json()['id']}"
        ).status_code == 204

        super_saved = super_client.put(
            "/api/v1/cj", json={**entry, "subject_id": other_subject, "ic": "Super-admin update"}
        )
        assert super_saved.status_code == 200, super_saved.text
        exam_saved = super_client.put(
            "/api/v1/cj/exams",
            json={
                "week_start": "2026-10-05",
                "day_index": 2,
                "subject_id": other_subject,
                "title": "Super-admin exam",
                "time": "09:30",
                "location": "Room 101",
                "note": "Bring a calculator",
            },
        )
        assert exam_saved.status_code == 200, exam_saved.text
        refreshed_student = student_client.get("/api/v1/cj?week_start=2026-10-05")
        assert any(exam["subject_id"] == assigned_subject for exam in refreshed_student.json()["exams"])
        assert any(exam["subject_id"] == other_subject for exam in refreshed_student.json()["exams"])

        new_course = {
            "name": "AP Environmental Science",
            "short_name": "APES",
            "grade": 11,
            "class_section": "All",
            "default_period": 9,
            "teacher": "Demo Teacher",
            "room": "E401",
        }
        teacher_course = teacher_client.post("/api/v1/cj/subjects", json=new_course)
        assert teacher_course.status_code == 201, teacher_course.text
        assert teacher_course.json()["is_custom"] is True
        assert teacher_client.delete(
            f"/api/v1/cj/subjects/{teacher_course.json()['id']}"
        ).status_code == 403

        admin_course = {**new_course, "name": "Environmental Science Lab", "short_name": "ES Lab"}
        created_course = super_client.post("/api/v1/cj/subjects", json=admin_course)
        assert created_course.status_code == 201, created_course.text
        assert created_course.json()["is_custom"] is True
        after_course = student_client.get("/api/v1/cj?week_start=2026-10-05")
        assert any(subject["short_name"] == "APES" for subject in after_course.json()["subjects"])
        assert any(subject["short_name"] == "ES Lab" for subject in after_course.json()["subjects"])
        assert super_client.delete(
            f"/api/v1/cj/subjects/{created_course.json()['id']}"
        ).status_code == 204
        assert super_client.delete(f"/api/v1/cj/subjects/{assigned_subject}").status_code == 422
    app.state.engine.dispose()


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

        teachers = client.get("/api/v1/cj/teachers")
        assert teachers.status_code == 200, teachers.text
        assert student_id in {item["id"] for item in teachers.json()["items"]}

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
