import re

import httpx

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://y.qq.com/",
}
_SEARCH_POOL = 30
_RESULT_LIMIT = 5
_SONG_MID = re.compile(r"^[0-9A-Za-z]{14}$")
_ALBUM_MID = re.compile(r"^[0-9A-Za-z]+$")


class QqUnavailable(Exception):
    """QQ Music could not be reached. No candidate was stored."""


def _map_song(song: dict) -> dict | None:
    song_id = str(song.get("songmid") or song.get("mid") or "")
    if not _SONG_MID.fullmatch(song_id):
        return None
    title = str(song.get("songname") or song.get("name") or "").strip()
    if not title:
        return None
    names = []
    singers = song.get("singer")
    if isinstance(singers, list):
        for artist in singers:
            name = str((artist or {}).get("name") or "").strip() if isinstance(artist, dict) else ""
            if name:
                names.append(name)
    elif isinstance(singers, str) and singers.strip():
        names.append(singers.strip())
    return {
        "song_id": song_id,
        "title": title[:120],
        "artists": ", ".join(names)[:200],
        "external_url": f"https://y.qq.com/n/ryqq/songDetail/{song_id}",
        "cover_url": _cover_url(song),
    }


def fetch_cover(album_mid: str) -> tuple[bytes, str]:
    if not _ALBUM_MID.fullmatch(album_mid):
        raise QqUnavailable()
    url = f"https://y.qq.com/music/photo_new/T002R300x300M000{album_mid}.jpg"
    try:
        response = httpx.get(
            url,
            headers={**_HEADERS, "Accept": "image/jpeg"},
            timeout=10,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise QqUnavailable() from exc
    media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if not media.startswith("image/") or not response.content:
        raise QqUnavailable()
    return response.content, media


def _cover_url(song: dict) -> str:
    album = song.get("album")
    mid = ""
    if isinstance(album, dict):
        mid = str(album.get("mid") or album.get("albummid") or "")
    if not mid:
        mid = str(song.get("albummid") or song.get("albumMid") or "")
    mid = mid.strip()
    if not _ALBUM_MID.fullmatch(mid):
        return ""
    return f"https://y.qq.com/music/photo_new/T002R300x300M000{mid}.jpg"


def _read_json(response: httpx.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise QqUnavailable()
    return payload


def top_matches(songs: list, limit: int = _RESULT_LIMIT) -> list[dict]:
    picked = []
    seen = set()
    for song in songs:
        row = _map_song(song or {})
        if row is None or row["song_id"] in seen:
            continue
        seen.add(row["song_id"])
        picked.append(row)
        if len(picked) == limit:
            break
    return picked


def search_songs(query: str) -> list[dict]:
    try:
        response = httpx.get(
            "https://c.y.qq.com/soso/fcgi-bin/search_for_qq_cp",
            params={
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "platform": "h5",
                "needNewCode": "1",
                "w": query,
                "t": "0",
                "n": str(_SEARCH_POOL),
                "p": "1",
                "remoteplace": "txt.mqq.all",
            },
            headers=_HEADERS,
            timeout=10,
        )
        payload = _read_json(response)
        if payload.get("code") not in (None, 0):
            raise QqUnavailable()
        songs = ((payload.get("data") or {}).get("song") or {}).get("list")
        if not isinstance(songs, list):
            raise QqUnavailable()
    except (httpx.HTTPError, ValueError) as exc:
        raise QqUnavailable() from exc
    return top_matches(songs[:_SEARCH_POOL])


def fetch_song(song_id: str) -> dict | None:
    if not _SONG_MID.fullmatch(song_id):
        return None
    try:
        response = httpx.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            headers={**_HEADERS, "Content-Type": "application/json"},
            json={
                "comm": {"ct": 24, "cv": 0},
                "songinfo": {
                    "method": "get_song_detail_yqq",
                    "module": "music.pf_song_detail_svr",
                    "param": {"song_mid": song_id},
                },
            },
            timeout=10,
        )
        payload = _read_json(response)
        songinfo = payload.get("songinfo") or {}
        if songinfo.get("code") not in (None, 0):
            raise QqUnavailable()
        track = (songinfo.get("data") or {}).get("track_info") or {}
    except (httpx.HTTPError, ValueError) as exc:
        raise QqUnavailable() from exc
    if not isinstance(track, dict) or not track:
        return None
    mapped = _map_song(track)
    if mapped is None or mapped["song_id"] != song_id:
        return None
    return mapped
