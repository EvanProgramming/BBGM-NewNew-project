import html
import json
import logging
import random
import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from errors import ApiError
from models import Comment, ForumAgent, ForumAgentAction, NewsBlock, Post, PostLike, User, to_iso, utc_now
from store import add_like, create_comment, create_post_with_audit, like_counts_for_posts

logger = logging.getLogger("elegram.forum_agents")

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_LOG_LIMIT = 200
_THREAD_CAP = 2
_TITLE_LIMIT = 48
_POST_LIMIT = 160
_COMMENT_LIMIT = 120
_NEWS_POOL = 8
_RECENT_POSTS = 20
_HOT_POOL = 3
_FEED_TTL = timedelta(minutes=30)
_DEFAULT_FEEDS = (
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://feeds.bbci.co.uk/sport/rss.xml",
)
_HTML_TAG = re.compile(r"<[^>]+>")
_LOCK = threading.Lock()
_FEED_LOCK = threading.Lock()
_FEED_CACHE: dict = {"at": None, "key": "", "items": []}
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class AgentUnavailable(Exception):
    """The model did not return usable English text."""


def shanghai_day(moment: datetime | None = None) -> str:
    current = _as_utc(moment or utc_now())
    return current.astimezone(_SHANGHAI).date().isoformat()


def tick_agents(core: Session, content: Session, settings) -> bool:
    if not settings.deepseek_api_key:
        return False
    if not _LOCK.acquire(blocking=False):
        return False
    try:
        agents = list(core.scalars(select(ForumAgent).where(ForumAgent.enabled.is_(True))).all())
        acted = False
        now = utc_now()
        for agent in agents:
            if not _in_window(agent, now) or not _due(agent, now):
                continue
            try:
                act_once(core, content, settings, agent, force=False)
            except ApiError:
                logger.warning("Forum agent could not write")
                continue
            acted = True
        return acted
    finally:
        _LOCK.release()


def manual_act(core: Session, content: Session, settings, agent: ForumAgent, *, kind: str | None = None) -> ForumAgentAction:
    if not _LOCK.acquire(blocking=False):
        raise ApiError(409, "sync_in_progress", "A forum agent is already acting.")
    try:
        if kind == "post":
            return _force_post(core, content, settings, agent)
        if kind == "comment":
            return _force_comment(core, content, settings, agent)
        return act_once(core, content, settings, agent, force=True)
    finally:
        _LOCK.release()


def act_once(core: Session, content: Session, settings, agent: ForumAgent, *, force: bool) -> ForumAgentAction:
    user = core.get(User, agent.user_id)
    if user is None or user.muted:
        return _log(core, agent, "skip", "", True, "This account cannot post.")
    _refresh_counts(agent)
    if not force and (not _in_window(agent, utc_now()) or not _due(agent, utc_now())):
        return _log(core, agent, "skip", "", True, "Not time to act.")
    reply = _reply_target(content, agent.user_id)
    if reply is not None and agent.comments_today < agent.comments_per_day:
        post, comment = reply
        return _comment(core, content, settings, agent, user, post, comment.body)
    kind = _choose(content, agent)
    if kind == "post":
        return _post(core, content, settings, agent, user)
    if kind == "comment":
        post = _other_post(content, agent.user_id)
        if post is None:
            return _log(core, agent, "skip", "", True, "No post to comment on.")
        return _comment(core, content, settings, agent, user, post, "")
    if kind == "like":
        post = _likeable_post(content, agent.user_id)
        if post is None:
            return _log(core, agent, "skip", "", True, "No post to like.")
        add_like(content, user_id=agent.user_id, post_id=post.id)
        agent.likes_today += 1
        agent.last_acted_at = utc_now()
        return _log(core, agent, "like", post.id, True, "")
    return _log(core, agent, "skip", "", True, "Daily limit reached.")


def run_scheduled_agents(app) -> None:
    settings = app.state.settings
    if not settings.deepseek_api_key:
        return
    core = app.state.core_session_factory()
    content = app.state.content_session_factory()
    try:
        if tick_agents(core, content, settings):
            core.commit()
            content.commit()
        else:
            core.rollback()
            content.rollback()
    except Exception:
        core.rollback()
        content.rollback()
        logger.exception("Forum agent tick failed")
    finally:
        core.close()
        content.close()


def complete_json(settings, system: str, user: str) -> dict:
    if not settings.deepseek_api_key:
        raise AgentUnavailable()
    try:
        with httpx.Client(timeout=45) as client:
            response = client.post(
                _DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": settings.deepseek_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.75 if "Say it plainer." in user else 1.05,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AgentUnavailable() from exc
    if not isinstance(payload, dict):
        raise AgentUnavailable()
    return payload


def _force_post(core, content, settings, agent) -> ForumAgentAction:
    user = core.get(User, agent.user_id)
    if user is None or user.muted:
        return _log(core, agent, "skip", "", True, "This account cannot post.")
    _refresh_counts(agent)
    return _post(core, content, settings, agent, user)


def _force_comment(core, content, settings, agent) -> ForumAgentAction:
    user = core.get(User, agent.user_id)
    if user is None or user.muted:
        return _log(core, agent, "skip", "", True, "This account cannot post.")
    _refresh_counts(agent)
    reply = _reply_target(content, agent.user_id)
    if reply is not None:
        post, comment = reply
        return _comment(core, content, settings, agent, user, post, comment.body, ignore_cap=True)
    post = _other_post(content, agent.user_id, ignore_cap=True)
    if post is None:
        return _log(core, agent, "skip", "", True, "No post to comment on.")
    return _comment(core, content, settings, agent, user, post, "", ignore_cap=True)


def _post(core, content, settings, agent, user) -> ForumAgentAction:
    try:
        spark = _pick_spark(content, settings, agent.user_id)
        written = _write(
            settings,
            _post_brief(agent, spark),
            need_title=True,
            grounded_in=spark or "",
        )
        title = _clip(_english(written.get("title"), 120), _TITLE_LIMIT)
        body = _clip(_english(written.get("body"), 4000), _POST_LIMIT)
    except AgentUnavailable:
        raise ApiError(503, "service_unavailable", "Forum agents could not write.")
    post = create_post_with_audit(
        content, author_id=user.id, title=title, body=body, category="forum"
    )
    agent.posts_today += 1
    agent.last_acted_at = utc_now()
    return _log(core, agent, "post", post.id, True, "")


def _comment(core, content, settings, agent, user, post: Post, prompt: str, *, ignore_cap: bool = False) -> ForumAgentAction:
    if not ignore_cap and _comment_count(content, post.id, agent.user_id) >= _THREAD_CAP:
        return _log(core, agent, "skip", post.id, True, "Already replied on this post.")
    try:
        news = _news_line(content, settings)
        written = _write(
            settings,
            _comment_brief(agent, post, prompt, news),
            need_title=False,
            grounded_in=f"{prompt}\n{post.title}\n{post.body}\n{news}",
        )
        body = _clip(_english(written.get("body"), 4000), _COMMENT_LIMIT)
    except AgentUnavailable:
        raise ApiError(503, "service_unavailable", "Forum agents could not write.")
    create_comment(content, post_id=post.id, author_id=user.id, body=body, parent_id=None)
    agent.comments_today += 1
    agent.last_acted_at = utc_now()
    return _log(core, agent, "comment", post.id, True, "")


def _generate(settings, brief: str, *, need_title: bool) -> dict:
    written = complete_json(settings, _SYSTEM, brief)
    if not _payload_polished(written):
        return written
    try:
        again = complete_json(
            settings,
            _SYSTEM,
            brief + "\nSay it plainer. Fewer words. One detail. No intro.",
        )
    except AgentUnavailable:
        return written
    if _usable(again, need_title=need_title):
        return again
    return written


def _write(settings, brief: str, *, need_title: bool, grounded_in: str) -> dict:
    written = _generate(settings, brief, need_title=need_title)
    if not grounded_in.strip() or _grounded(_written_text(written), grounded_in):
        return written
    try:
        again = complete_json(
            settings,
            _SYSTEM,
            brief + "\nName a concrete thing from the source. The last try was too empty.",
        )
    except AgentUnavailable:
        return written
    if _usable(again, need_title=need_title):
        return again
    return written


def _written_text(payload: dict) -> str:
    return f"{payload.get('title') or ''} {payload.get('body') or ''}"


def _post_brief(agent, spark: str | None) -> str:
    brief = (
        f"Personality: {agent.personality}\nHobbies: {agent.hobbies}\nTone: {agent.tone}\n"
        f"Shape: {random.choice(_POST_MOVES)}\n"
    )
    if spark:
        brief += (
            f"Source: {spark}\n"
            "Name one concrete thing from the source: a person, place, number, or what happened. "
            "The title or body has to include that thing. Don't be vague. Don't summarize the whole story, "
            "don't copy a full sentence, and don't add facts that are not in the source. "
            "Don't mention the paper, name a website, or say you saw it online.\n"
        )
    else:
        brief += "One hobby detail: a game, a show, music, or something else they do. Skip school.\n"
    return (
        brief
        + "Title is a few words, like the start of a comment, not a headline. Body is one line.\n"
        + 'JSON: {"title":"...","body":"..."}'
    )


def _pick_spark(content: Session, settings, user_id: str) -> str | None:
    story = _story_line(content, settings, full=True)
    if story:
        return story
    hot = _hot_details(content, user_id)
    if hot:
        return random.choice(hot)
    return None


def _news_line(content: Session, settings) -> str:
    return _story_line(content, settings, full=False) or ""


def _story_line(content: Session, settings, *, full: bool) -> str | None:
    external = _external_headlines(settings)
    campus = _news_details(content, full=full)
    if external and campus:
        pool = external if random.random() < 0.7 else campus
        return random.choice(pool)
    if external:
        return random.choice(external)
    if campus:
        return random.choice(campus)
    return None


def _news_details(content: Session, *, full: bool) -> list[str]:
    rows = list(
        content.scalars(
            select(Post)
            .where(Post.category == "news", Post.status == "published")
            .order_by(Post.updated_at.desc())
            .limit(_NEWS_POOL)
        ).all()
    )
    details = []
    for post in rows:
        blocks = list(
            content.scalars(
                select(NewsBlock)
                .where(NewsBlock.post_id == post.id, NewsBlock.published_body.is_not(None))
                .order_by(NewsBlock.position.asc())
            ).all()
        )
        source = "\n".join(block.published_body for block in blocks if block.published_body)
        source = source or post.body or post.excerpt or ""
        line = _news_clip(source, full=full)
        if len(_content_words(line)) < 2:
            continue
        details.append(f"{post.title}: {line}" if post.title and line != post.title else line)
    return details


def _news_clip(text: str, *, full: bool) -> str:
    cleaned = " ".join(str(text or "").split())
    parts = [part.strip() for part in _SENTENCE.split(cleaned) if part.strip()]
    if not parts:
        return cleaned[:220]
    if not full:
        return max(parts, key=lambda part: len(_content_words(part)))[:220]
    chunk = []
    for part in parts:
        chunk.append(part)
        if len(chunk) == 3:
            break
    return " ".join(chunk)[:480]


def _feed_urls(settings) -> tuple[str, ...]:
    raw = (getattr(settings, "news_feed_urls", "") or "").strip()
    if not raw:
        return _DEFAULT_FEEDS
    urls = tuple(part.strip() for part in raw.split(",") if part.strip())
    return urls or _DEFAULT_FEEDS


def _external_headlines(settings) -> list[str]:
    urls = _feed_urls(settings)
    key = ",".join(urls)
    now = utc_now()
    with _FEED_LOCK:
        cached_at = _FEED_CACHE["at"]
        if (
            cached_at is not None
            and _FEED_CACHE["key"] == key
            and now - _as_utc(cached_at) < _FEED_TTL
        ):
            return list(_FEED_CACHE["items"])
    items = _fetch_headlines(urls)
    with _FEED_LOCK:
        _FEED_CACHE["at"] = now
        _FEED_CACHE["key"] = key
        _FEED_CACHE["items"] = items
    return list(items)


def _fetch_headlines(urls: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            for url in urls:
                if len(found) >= 8:
                    break
                try:
                    response = client.get(url, headers={"User-Agent": "ElegramForumAgent/1.0"})
                    response.raise_for_status()
                    found.extend(_parse_rss(response.text))
                except (httpx.HTTPError, ET.ParseError, ValueError):
                    continue
    except httpx.HTTPError:
        return found[:8]
    chosen: list[str] = []
    for item in found:
        if item not in chosen:
            chosen.append(item)
        if len(chosen) == 8:
            break
    return chosen


def _parse_rss(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    items: list[str] = []
    for item in root.iter("item"):
        title = _plain_feed_text(item.findtext("title") or "")
        description = _plain_feed_text(item.findtext("description") or "")
        if _CJK.search(title) or _CJK.search(description):
            continue
        line = _news_clip(description, full=False) if description else ""
        text = f"{title}: {line}" if title and line and line != title else title
        if len(_content_words(text)) < 2:
            continue
        items.append(text[:480])
        if len(items) == 4:
            break
    return items


def _plain_feed_text(value: str) -> str:
    text = _HTML_TAG.sub(" ", html.unescape(value or ""))
    return " ".join(text.split())


def _hot_details(content: Session, user_id: str) -> list[str]:
    ranked = _rank_by_heat(content, _recent_forum_posts(content, user_id))
    details = []
    for post in ranked[:_HOT_POOL]:
        line = _hook(post.body) or post.title
        if line:
            details.append(line)
    return details


def _recent_forum_posts(content: Session, user_id: str) -> list[Post]:
    return list(
        content.scalars(
            select(Post)
            .where(Post.category == "forum", Post.status == "published", Post.author_id != user_id)
            .order_by(Post.created_at.desc())
            .limit(_RECENT_POSTS)
        ).all()
    )


def _rank_by_heat(content: Session, posts: list[Post]) -> list[Post]:
    if not posts:
        return []
    ids = [post.id for post in posts]
    likes = like_counts_for_posts(content, ids)
    replies = _reply_counts(content, ids)
    return sorted(
        posts,
        key=lambda post: (likes.get(post.id, 0), replies.get(post.id, 0), _as_utc(post.created_at)),
        reverse=True,
    )


def _reply_counts(content: Session, post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    rows = content.execute(
        select(Comment.post_id, func.count())
        .where(Comment.post_id.in_(post_ids))
        .group_by(Comment.post_id)
    ).all()
    return {post_id: int(count) for post_id, count in rows}


def _comment_brief(agent, post: Post, prompt: str, news: str = "") -> str:
    if prompt.strip():
        context = (
            f"Their last line: {prompt.strip()[:280]}\n"
            f"Post title, ignore unless you need it: {post.title}\n"
            f"Shape: {random.choice(_REPLY_MOVES)}\n"
        )
    else:
        context = (
            f"Post title: {post.title}\n"
            f"React only to this line: {_hook(post.body) or post.title}\n"
            f"Shape: {random.choice(_COMMENT_MOVES)}\n"
        )
    if news:
        context += (
            f"News source: {news}\n"
            "Name one concrete thing. Use their line when it already has one. "
            "When their line is empty, use a person, place, number, or event from the news source.\n"
        )
    return (
        f"Personality: {agent.personality}\nHobbies: {agent.hobbies}\nTone: {agent.tone}\n"
        f"{context}"
        "Don't add facts that are not in the line or the news source. "
        "Don't mention the paper, name a website, or say you saw it online. "
        'JSON: {"body":"..."}'
    )


_STOP_WORDS = frozenset(
    """
    the a an of on in at to for and or but if so as it its is was were are be been being
    this that these those they them their there then than with from into over after before
    about just like very really not no yes you your we our he she his her had has have
    did do does done will would can could should off out too also more most some any all
    """.split()
)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", str(text or "").lower())
    return {word for word in words if len(word) >= 3 and word not in _STOP_WORDS}


def _grounded(text: str, source: str) -> bool:
    words = _content_words(source)
    if not words:
        return True
    return bool(words & _content_words(text))


def _hook(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    parts = [part.strip() for part in _SENTENCE.split(cleaned) if part.strip()]
    if len(parts) <= 1:
        return cleaned[:180]
    return random.choice(parts)[:180]


def _payload_polished(payload: dict) -> bool:
    title = payload.get("title")
    body = payload.get("body")
    if title is not None and _too_polished(title, title=True):
        return True
    return body is not None and _too_polished(body)


def _too_polished(value, *, title: bool = False) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    cleaned = " ".join(raw.lower().split())
    if any(phrase in cleaned for phrase in _AI_PHRASES):
        return True
    if cleaned.startswith(_AI_OPENERS):
        return True
    if "—" in raw or ";" in raw:
        return True
    words = cleaned.split()
    if title and (_headline(raw) or len(words) > 8):
        return True
    if not title and len(words) > 28:
        return True
    enders = len(re.findall(r"[.!?]", raw))
    return enders >= 2 and len(words) > 12


def _headline(title: str) -> bool:
    words = re.findall(r"[A-Za-z']+", title)
    if len(words) < 4:
        return False
    caps = sum(1 for word in words if word[:1].isupper())
    return caps >= len(words) - 1


def _usable(payload: dict, *, need_title: bool) -> bool:
    if not _plain_english(payload.get("body")):
        return False
    if need_title and not _plain_english(payload.get("title")):
        return False
    return True


def _plain_english(value) -> bool:
    text = str(value or "").strip()
    return bool(text) and _CJK.search(text) is None


def _choose(content: Session, agent: ForumAgent) -> str | None:
    options = []
    if agent.posts_today < agent.posts_per_day:
        options.append("post")
    if agent.comments_today < agent.comments_per_day and _other_post(content, agent.user_id) is not None:
        options.extend(["comment", "comment"])
    if agent.likes_today < agent.likes_per_day and _likeable_post(content, agent.user_id) is not None:
        options.extend(["like", "like"])
    if not options:
        return None
    return random.choice(options)


def _reply_target(content: Session, user_id: str):
    posts = list(
        content.scalars(
            select(Post).where(
                Post.author_id == user_id,
                Post.category == "forum",
                Post.status == "published",
            )
        ).all()
    )
    chosen = None
    chosen_at = None
    for post in posts:
        comments = list(
            content.scalars(
                select(Comment)
                .where(Comment.post_id == post.id, Comment.parent_id.is_(None))
                .order_by(Comment.created_at.asc())
            ).all()
        )
        others = [item for item in comments if item.author_id != user_id]
        if not others:
            continue
        latest = others[-1]
        mine = [item for item in comments if item.author_id == user_id]
        if mine and _as_utc(mine[-1].created_at) >= _as_utc(latest.created_at):
            continue
        latest_at = _as_utc(latest.created_at)
        if chosen is None or latest_at > chosen_at:
            chosen = (post, latest)
            chosen_at = latest_at
    return chosen


def _other_post(content: Session, user_id: str, *, ignore_cap: bool = False) -> Post | None:
    rows = _recent_forum_posts(content, user_id)
    if not ignore_cap:
        rows = [post for post in rows if _comment_count(content, post.id, user_id) < _THREAD_CAP]
    ranked = _rank_by_heat(content, rows)
    if not ranked:
        return None
    return random.choice(ranked[:_HOT_POOL])


def _likeable_post(content: Session, user_id: str) -> Post | None:
    rows = list(
        content.scalars(
            select(Post)
            .where(Post.category == "forum", Post.status == "published", Post.author_id != user_id)
            .order_by(Post.created_at.desc())
            .limit(_RECENT_POSTS)
        ).all()
    )
    liked = set(
        content.scalars(select(PostLike.post_id).where(PostLike.user_id == user_id)).all()
    )
    for post in rows:
        if post.id not in liked:
            return post
    return None


def _comment_count(content: Session, post_id: str, user_id: str) -> int:
    return int(
        content.scalar(
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.author_id == user_id)
        )
        or 0
    )


def _refresh_counts(agent: ForumAgent) -> None:
    today = shanghai_day()
    if agent.count_day != today:
        agent.count_day = today
        agent.posts_today = 0
        agent.comments_today = 0
        agent.likes_today = 0


def _in_window(agent: ForumAgent, moment: datetime) -> bool:
    local = _as_utc(moment).astimezone(_SHANGHAI)
    current = local.hour * 60 + local.minute
    return _minutes(agent.active_start) <= current < _minutes(agent.active_end)


def _due(agent: ForumAgent, moment: datetime) -> bool:
    if agent.last_acted_at is None:
        return True
    return _as_utc(moment) - _as_utc(agent.last_acted_at) >= timedelta(minutes=agent.min_interval_minutes)


def _minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _english(value, limit: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or _CJK.search(text):
        raise AgentUnavailable()
    return text


def _clip(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    piece = compact[:limit].rsplit(" ", 1)[0].strip()
    return piece or compact[:limit].strip()


def _log(core: Session, agent: ForumAgent, action: str, post_id: str, ok: bool, message: str) -> ForumAgentAction:
    row = ForumAgentAction(
        id=str(uuid4()),
        agent_id=agent.id,
        action=action,
        post_id=post_id or "",
        ok=ok,
        message=message[:200],
        created_at=utc_now(),
    )
    core.add(row)
    core.flush()
    stale = list(
        core.scalars(
            select(ForumAgentAction.id).order_by(ForumAgentAction.created_at.desc()).offset(_LOG_LIMIT)
        ).all()
    )
    if stale:
        core.execute(delete(ForumAgentAction).where(ForumAgentAction.id.in_(stale)))
    return row


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def valid_clock(value: str) -> bool:
    return bool(_CLOCK.fullmatch(value or ""))


def agent_payload(agent: ForumAgent, user: User) -> dict:
    return {
        "id": agent.id,
        "user_id": agent.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "enabled": bool(agent.enabled),
        "personality": agent.personality,
        "hobbies": agent.hobbies,
        "tone": agent.tone,
        "posts_per_day": agent.posts_per_day,
        "comments_per_day": agent.comments_per_day,
        "likes_per_day": agent.likes_per_day,
        "min_interval_minutes": agent.min_interval_minutes,
        "active_start": agent.active_start,
        "active_end": agent.active_end,
        "posts_today": agent.posts_today,
        "comments_today": agent.comments_today,
        "likes_today": agent.likes_today,
        "last_acted_at": to_iso(_as_utc(agent.last_acted_at)) if agent.last_acted_at else None,
    }


def action_payload(row: ForumAgentAction) -> dict:
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "action": row.action,
        "post_id": row.post_id or None,
        "ok": bool(row.ok),
        "message": row.message,
        "created_at": to_iso(_as_utc(row.created_at)),
    }


_POST_MOVES = (
    "One specific like or dislike. Name the thing. Stop.",
    "A petty complaint. Don't balance it with a compliment.",
    "One question you actually want answered. Not a discussion prompt.",
    "Something you keep replaying. Name it. Don't explain why it matters.",
)

_COMMENT_MOVES = (
    "React to that one line. A fragment is enough.",
    "Agree in a few words and add one small extra. Don't restate it.",
    "Disagree a little. One line. Don't argue both sides.",
    "You've done the same thing. Don't turn it into a story.",
    "Ask about that detail only. Don't ask what everyone thinks.",
    "Dry and flat. No exclamation mark.",
)

_REPLY_MOVES = (
    "Answer their last line. Don't recap the post.",
    "Agree and add one crumb. Don't repeat their sentence.",
    "Correct one thing, then stop.",
    "React to how they said it. Don't summarize.",
)

_AI_OPENERS = (
    "honestly,",
    "certainly,",
    "overall,",
    "furthermore",
    "additionally",
    "moreover",
    "in conclusion",
    "as someone",
    "i appreciate",
    "thanks for sharing",
    "great point",
    "great take",
    "well said",
    "let me know",
)

_AI_PHRASES = (
    "it's worth noting",
    "it is worth noting",
    "it's important to",
    "what do you think",
    "what do you guys",
    "what are your thoughts",
    "couldn't agree more",
    "could not agree more",
    "thoughtful take",
    "thanks for sharing",
    "as someone who",
    "on the other hand",
    "that being said",
    "having said that",
    "can't help but",
    "cannot help but",
    "at the end of the day",
    "food for thought",
    "a testament",
    "serves as a reminder",
    "speaks volumes",
    "in today's",
    "let me know",
    "great point",
    "great take",
    "well said",
    "resonates",
    "delve",
    "nuanced",
    "tapestry",
    "furthermore",
    "additionally",
    "moreover",
)

_SYSTEM = (
    "You are typing a comment, fast, the way people do in a comment section. English. JSON only. "
    "Short. Often under 15 words. A fragment is normal. Lowercase is fine. One punctuation mark at most. "
    "React to one detail and pick a side. Do not summarize, quote them back, or compliment the writing. "
    "Plain words. One casual word is enough. Do not stack slang, meme formats, or emoji. "
    "Do not mention videos, views, subscribers, the algorithm, or the name of a news site. "
    "Personality changes the attitude, not the length. Use their hobbies and the line in front of you. "
    "Roughness to aim for, without reusing the words: \"wait the second chorus\", \"nah the first season\". "
    "Never write: \"This is such a thoughtful take\" or \"I really appreciate how you broke this down.\" "
    "When a source is given, name a person, place, number, or event from it. A reaction with none of those is too empty. "
    "Do not invent classes, exams, teachers, or campus events that are not in the source. "
    "Games, shows, music, and hobbies are fine. Do not invent facts about real people. Do not say you are an AI."
)
