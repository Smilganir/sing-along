"""Sync recent YouTube Music listens via unofficial ytmusicapi (browser auth)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from ytmusicapi import YTMusic
from ytmusicapi.exceptions import YTMusicServerError

from config import YTMUSIC_AUTH_PATH, YTMUSIC_SNAPSHOT_PATH
from db.models import Song, SyncRun
from services.takeout_sync import clean_artist, clean_title, detect_language, thumbnail_for

SYNC_SOURCE = "ytmusic"

_TODAY_LABELS = frozenset({"today", "היום"})
_YESTERDAY_LABELS = frozenset({"yesterday", "אתמול"})


def auth_configured() -> bool:
    return YTMUSIC_AUTH_PATH.is_file()


def save_auth_config(auth: dict) -> None:
    required = {"Cookie", "Authorization"}
    missing = required - set(auth)
    if missing:
        raise ValueError(f"Auth JSON must include: {', '.join(sorted(missing))}")
    YTMUSIC_AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    YTMUSIC_AUTH_PATH.write_text(json.dumps(auth, indent=2), encoding="utf-8")


def _load_ytmusic() -> YTMusic:
    if not auth_configured():
        raise FileNotFoundError(
            f"YouTube Music auth not configured. Save browser credentials to {YTMUSIC_AUTH_PATH}"
        )
    return YTMusic(str(YTMUSIC_AUTH_PATH))


def _load_snapshot() -> list[str]:
    if not YTMUSIC_SNAPSHOT_PATH.is_file():
        return []
    try:
        data = json.loads(YTMUSIC_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        ids = data.get("ids")
        if isinstance(ids, list):
            return [str(item) for item in ids if item]
    if isinstance(data, list):
        return [str(item) for item in data if item]
    return []


def _save_snapshot(ids: list[str]) -> None:
    YTMUSIC_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    YTMUSIC_SNAPSHOT_PATH.write_text(
        json.dumps({"ids": ids, "version": 1}, indent=2),
        encoding="utf-8",
    )


def _play_deltas(current_ids: list[str], previous_ids: list[str]) -> dict[str, int]:
    if not previous_ids:
        deltas: dict[str, int] = {}
        for video_id in current_ids:
            deltas[video_id] = deltas.get(video_id, 0) + 1
        return deltas

    deltas: dict[str, int] = {}
    prev_idx = 0
    for video_id in current_ids:
        if prev_idx < len(previous_ids) and video_id == previous_ids[prev_idx]:
            prev_idx += 1
        else:
            deltas[video_id] = deltas.get(video_id, 0) + 1
    return deltas


def _parse_shelf_played(label: str | None, shelf_index: int, synced_at: datetime) -> datetime:
    normalized = (label or "").strip().lower()
    if normalized in _TODAY_LABELS:
        return synced_at
    if normalized in _YESTERDAY_LABELS:
        return synced_at - timedelta(days=1)
    if shelf_index > 0:
        return synced_at - timedelta(days=shelf_index)
    return synced_at


def _artist_name(item: dict) -> str:
    artists = item.get("artists") or []
    if not artists:
        return ""
    first = artists[0] if isinstance(artists[0], dict) else {}
    return clean_artist(str(first.get("name") or ""))


def _aggregate_history(
    items: list[dict], synced_at: datetime
) -> tuple[dict[str, dict], list[str]]:
    """Return metadata and ordered video ids from YouTube Music history."""
    label_to_index: dict[str | None, int] = {}
    aggregated: dict[str, dict] = {}
    ordered_ids: list[str] = []

    for item in items:
        video_id = item.get("videoId")
        if not video_id:
            continue
        video_id = str(video_id)
        ordered_ids.append(video_id)

        played_label = item.get("played")
        if played_label not in label_to_index:
            label_to_index[played_label] = len(label_to_index)

        if video_id in aggregated:
            continue

        title = clean_title(item.get("title"))
        artist = _artist_name(item)
        aggregated[video_id] = {
            "yt_video_id": video_id,
            "title": title,
            "artist": artist,
            "language": detect_language(title, artist),
            "last_played_at": _parse_shelf_played(
                played_label, label_to_index.get(played_label, 0), synced_at
            ),
            "thumbnail_url": thumbnail_for(video_id),
        }

    return aggregated, ordered_ids


def _compute_deltas(db: Session, ordered_ids: list[str], previous_ids: list[str]) -> dict[str, int]:
    if previous_ids:
        return _play_deltas(ordered_ids, previous_ids)

    visible = Counter(ordered_ids)
    existing = {
        row[0]
        for row in db.query(Song.yt_video_id).filter(Song.deleted_at.is_(None)).all()
    }
    return {video_id: visible[video_id] for video_id in visible if video_id not in existing}


def _last_successful_sync(db: Session) -> SyncRun | None:
    return (
        db.query(SyncRun)
        .filter(SyncRun.source == SYNC_SOURCE, SyncRun.error.is_(None))
        .order_by(SyncRun.finished_at.desc())
        .first()
    )


def fetch_history_items() -> list[dict]:
    ytmusic = _load_ytmusic()
    try:
        items = ytmusic.get_history()
    except YTMusicServerError as exc:
        raise RuntimeError(
            "YouTube Music history is unavailable. Enable watch history in your Google account."
        ) from exc

    if items:
        return items

    from ytmusicapi.navigation import nav

    response = ytmusic._send_request("browse", {"browseId": "FEmusic_history"})
    contents = nav(
        response,
        [
            "contents",
            "singleColumnBrowseResultsRenderer",
            "tabs",
            0,
            "tabRenderer",
            "content",
            "sectionListRenderer",
            "contents",
        ],
        True,
    )
    if contents:
        section = contents[0]
        inner = None
        if "itemSectionRenderer" in section:
            inner_contents = section["itemSectionRenderer"].get("contents") or []
            inner = inner_contents[0] if inner_contents else None
        if inner and "messageRenderer" in inner:
            message = nav(inner, ["messageRenderer", "text", "runs", 0, "text"], True)
            if message and "sign in" in message.lower():
                raise RuntimeError(
                    "YouTube Music auth expired or cookies are stale. "
                    "Refresh music.youtube.com, re-copy the Cookies tab, and update browser.json."
                )
            if message:
                raise RuntimeError(f"YouTube Music history blocked: {message}")

    return items


def upsert_ytmusic_plays(
    db: Session,
    aggregated: dict[str, dict],
    deltas: dict[str, int],
) -> tuple[int, int, int]:
    added = 0
    updated = 0
    play_events = sum(deltas.values())
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    touched_ids = set(aggregated) | set(deltas)
    for video_id in touched_ids:
        delta = deltas.get(video_id, 0)
        meta = aggregated.get(video_id)
        if meta is None and delta <= 0:
            continue

        song = db.query(Song).filter(Song.yt_video_id == video_id).one_or_none()
        if song is None:
            if not meta:
                continue
            song = Song(
                yt_video_id=video_id,
                title=meta["title"],
                artist=meta["artist"],
                language=meta["language"],
                play_count=max(delta, 1),
                last_played_at=meta["last_played_at"],
                thumbnail_url=meta["thumbnail_url"],
                duration_sec=None,
                source_status="imported",
                last_synced_at=now,
            )
            db.add(song)
            added += 1
            continue

        if delta > 0:
            song.play_count = (song.play_count or 0) + delta
            updated += 1
        if meta:
            if meta["title"]:
                song.title = meta["title"]
            if meta["artist"]:
                song.artist = meta["artist"]
            song.language = meta["language"]
            if meta["last_played_at"] and (
                song.last_played_at is None or meta["last_played_at"] > song.last_played_at
            ):
                song.last_played_at = meta["last_played_at"]
            song.thumbnail_url = meta["thumbnail_url"]
        song.last_synced_at = now

    return added, updated, play_events


def sync_ytmusic(db: Session) -> SyncRun:
    run = SyncRun(source=SYNC_SOURCE)
    db.add(run)
    db.commit()
    db.refresh(run)

    synced_at = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        items = fetch_history_items()
        if not items:
            run.history_items = 0
            run.songs_added = 0
            run.songs_updated = 0
            run.finished_at = synced_at
            db.commit()
            db.refresh(run)
            return run

        aggregated, ordered_ids = _aggregate_history(items, synced_at)
        previous_ids = _load_snapshot()
        deltas = _compute_deltas(db, ordered_ids, previous_ids)
        added, updated, play_events = upsert_ytmusic_plays(db, aggregated, deltas)

        _save_snapshot(ordered_ids)

        run.history_items = len(items)
        run.songs_added = added
        run.songs_updated = updated
        run.finished_at = synced_at
        db.commit()
        db.refresh(run)
        run.play_events = play_events  # type: ignore[attr-defined]
        return run
    except Exception as exc:
        run.error = str(exc)
        run.finished_at = synced_at
        db.commit()
        db.refresh(run)
        raise


def ytmusic_status(db: Session) -> dict:
    last_run = _last_successful_sync(db)
    return {
        "configured": auth_configured(),
        "last_sync": last_run.finished_at if last_run else None,
        "last_added": last_run.songs_added if last_run else 0,
        "last_updated": last_run.songs_updated if last_run else 0,
    }
