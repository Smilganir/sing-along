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
WATCH_HISTORY_JSON = "watch-history.json"
WATCH_HISTORY_HTML = "watch-history.html"
WATCH_HISTORY_NAMES = (WATCH_HISTORY_JSON, WATCH_HISTORY_HTML)
HTML_PLAYED_AT_RE = re.compile(
    r"^(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4}),\s+"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2}):(?P<second>\d{2})\s+(?P<ampm>AM|PM)"
)
HTML_MUSIC_BLOCK_RE = re.compile(
    r'<p class="mdl-typography--title">YouTube Music.*?</p></div>'
    r'<div class="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1">(.*?)</div>',
    re.DOTALL,
)
HTML_TITLE_LINK_RE = re.compile(
    r'href="(https://music\.youtube\.com/watch\?v=[^"]+)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
HTML_ARTIST_LINK_RE = re.compile(
    r'href="https://www\.youtube\.com/(?:channel|@)[^"]+"[^>]*>(.*?)</a>',
    re.DOTALL,
)


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
        pass

    cleaned = re.sub(r"\s+[A-Z]{2,5}$", "", value.strip())
    cleaned = cleaned.replace("\u202f", " ")
    match = HTML_PLAYED_AT_RE.match(cleaned)
    if not match:
        return None
    parsed = datetime.strptime(
        f"{match.group('month')} {match.group('day')}, {match.group('year')} "
        f"{match.group('hour')}:{match.group('minute')}:{match.group('second')} "
        f"{match.group('ampm')}",
        "%b %d, %Y %I:%M:%S %p",
    )
    return parsed.replace(tzinfo=None)


def thumbnail_for(video_id_value: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id_value}/hqdefault.jpg"


def find_watch_history(root: Path) -> Path:
    if root.is_file():
        if root.name in WATCH_HISTORY_NAMES:
            return root
        raise FileNotFoundError(
            f"Expected one of {', '.join(WATCH_HISTORY_NAMES)}, got {root.name}"
        )

    for name in WATCH_HISTORY_NAMES:
        matches = [
            path
            for path in root.rglob(name)
            if "history" in {part.lower() for part in path.parts}
        ]
        if not matches:
            matches = list(root.rglob(name))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Could not find {' or '.join(WATCH_HISTORY_NAMES)} under {root}"
    )


def extract_takeout_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir()

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(dest_dir)

    return find_watch_history(dest_dir)


def _aggregate_music_rows(rows: list[dict]) -> tuple[list[dict], int]:
    aggregated: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)

    for row in rows:
        vid = row["yt_video_id"]
        counts[vid] += 1

        if vid not in aggregated:
            aggregated[vid] = row.copy()
            aggregated[vid]["play_count"] = 0
        else:
            aggregated[vid]["title"] = row["title"]
            if row["artist"]:
                aggregated[vid]["artist"] = row["artist"]
            played_at = row["last_played_at"]
            if played_at and (
                aggregated[vid]["last_played_at"] is None
                or played_at > aggregated[vid]["last_played_at"]
            ):
                aggregated[vid]["last_played_at"] = played_at

    ranked = []
    for vid, count in counts.items():
        item = aggregated[vid].copy()
        item["play_count"] = count
        item["language"] = detect_language(item["title"], item["artist"])
        ranked.append(item)

    ranked.sort(key=lambda item: (-item["play_count"], item["title"].lower()))
    return ranked, sum(counts.values())


def _parse_takeout_json(history_path: Path) -> list[dict]:
    with history_path.open(encoding="utf-8") as handle:
        history = json.load(handle)

    rows: list[dict] = []
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

        rows.append(
            {
                "yt_video_id": vid,
                "title": title,
                "artist": artist,
                "last_played_at": parse_played_at(item.get("time")),
                "thumbnail_url": thumbnail_for(vid),
            }
        )
    return rows


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _parse_takeout_html(history_path: Path) -> list[dict]:
    html = history_path.read_text(encoding="utf-8")
    rows: list[dict] = []

    for match in HTML_MUSIC_BLOCK_RE.finditer(html):
        block = match.group(1)
        title_match = HTML_TITLE_LINK_RE.search(block)
        if not title_match:
            continue

        vid = video_id(title_match.group(1))
        if not vid:
            continue

        artist_match = HTML_ARTIST_LINK_RE.search(block)
        artist = clean_artist(_strip_html(artist_match.group(1))) if artist_match else ""

        lines = [
            _strip_html(part)
            for part in re.split(r"<br\s*/?>", block, flags=re.IGNORECASE)
            if _strip_html(part)
        ]
        played_at = parse_played_at(lines[-1]) if lines else None

        rows.append(
            {
                "yt_video_id": vid,
                "title": clean_title(_strip_html(title_match.group(2))),
                "artist": artist,
                "last_played_at": played_at,
                "thumbnail_url": thumbnail_for(vid),
            }
        )

    return rows


def parse_takeout_history(path: Path) -> tuple[list[dict], int]:
    history_path = find_watch_history(path)
    if history_path.name == WATCH_HISTORY_HTML:
        rows = _parse_takeout_html(history_path)
    else:
        rows = _parse_takeout_json(history_path)
    return _aggregate_music_rows(rows)


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
    run = SyncRun(source="takeout")
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
