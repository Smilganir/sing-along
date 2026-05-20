import json
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from db.models import Song, SyncRun

HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
WATCH_HISTORY_NAME = "watch-history.json"


def detect_language(title: str, artist: str = "") -> str:
    return "he" if HEBREW_RE.search(f"{title} {artist}") else "en"


def video_id(url: str | None) -> str | None:
    if not url or "v=" not in url:
        return None
    return url.split("v=")[-1].split("&")[0]


def clean_title(title: str | None) -> str:
    if not title:
        return "Unknown"
    cleaned = title
    for prefix in ("Watched ", "Listened to "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.strip()


def clean_artist(name: str) -> str:
    if name.endswith(" - Topic"):
        return name[: -len(" - Topic")]
    return name


def parse_played_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None)
    except ValueError:
        return None


def thumbnail_for(video_id_value: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id_value}/hqdefault.jpg"


def find_watch_history(root: Path) -> Path:
    if root.is_file():
        if root.name == WATCH_HISTORY_NAME:
            return root
        raise FileNotFoundError(f"Expected {WATCH_HISTORY_NAME}, got {root.name}")

    matches = [
        path
        for path in root.rglob(WATCH_HISTORY_NAME)
        if "history" in {part.lower() for part in path.parts}
    ]
    if not matches:
        matches = list(root.rglob(WATCH_HISTORY_NAME))
    if not matches:
        raise FileNotFoundError(f"Could not find {WATCH_HISTORY_NAME} under {root}")
    return matches[0]


def extract_takeout_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir()

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(dest_dir)

    return find_watch_history(dest_dir)


def parse_takeout_history(path: Path) -> tuple[list[dict], int]:
    history_path = find_watch_history(path)
    with history_path.open(encoding="utf-8") as handle:
        history = json.load(handle)

    aggregated: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)

    for item in history:
        header = item.get("header", "")
        url = item.get("titleUrl", "")
        is_music = header == "YouTube Music" or "music.youtube.com" in (url or "")
        if not is_music:
            continue

        vid = video_id(url)
        if not vid:
            continue

        title = clean_title(item.get("title"))
        artist = ""
        subtitles = item.get("subtitles") or []
        if subtitles:
            artist = clean_artist(subtitles[0].get("name", ""))

        played_at = parse_played_at(item.get("time"))
        counts[vid] += 1

        if vid not in aggregated:
            aggregated[vid] = {
                "yt_video_id": vid,
                "title": title,
                "artist": artist,
                "play_count": 0,
                "last_played_at": played_at,
                "thumbnail_url": thumbnail_for(vid),
            }
        else:
            aggregated[vid]["title"] = title
            if artist:
                aggregated[vid]["artist"] = artist
            if played_at and (
                aggregated[vid]["last_played_at"] is None
                or played_at > aggregated[vid]["last_played_at"]
            ):
                aggregated[vid]["last_played_at"] = played_at

    ranked = []
    for vid, count in counts.items():
        row = aggregated[vid].copy()
        row["play_count"] = count
        row["language"] = detect_language(row["title"], row["artist"])
        ranked.append(row)

    ranked.sort(key=lambda item: (-item["play_count"], item["title"].lower()))
    music_entries = sum(counts.values())
    return ranked, music_entries


def upsert_songs(db: Session, ranked: list[dict]) -> tuple[int, int]:
    added = 0
    updated = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for data in ranked:
        song = (
            db.query(Song).filter(Song.yt_video_id == data["yt_video_id"]).one_or_none()
        )
        if song is None:
            song = Song(
                yt_video_id=data["yt_video_id"],
                title=data["title"],
                artist=data["artist"],
                language=data["language"],
                play_count=data["play_count"],
                last_played_at=data["last_played_at"],
                thumbnail_url=data["thumbnail_url"],
                duration_sec=None,
                source_status="imported",
                last_synced_at=now,
            )
            db.add(song)
            added += 1
        else:
            song.title = data["title"]
            song.artist = data["artist"]
            song.language = data["language"]
            song.play_count = data["play_count"]
            song.last_played_at = data["last_played_at"]
            song.thumbnail_url = data["thumbnail_url"]
            song.last_synced_at = now
            updated += 1

    return added, updated


def import_takeout(db: Session, source: Path) -> SyncRun:
    run = SyncRun()
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        ranked, music_entries = parse_takeout_history(source)
        added, updated = upsert_songs(db, ranked)

        run.history_items = music_entries
        run.songs_added = added
        run.songs_updated = updated
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run.error = str(exc)
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(run)
        raise
