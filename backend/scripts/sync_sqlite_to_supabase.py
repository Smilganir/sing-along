"""One-way sync: copy all local SQLite rows into Supabase (matched by song id)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from config import BASE_DIR, _normalize_db_url
from db.models import Favorite, RoomState, Song

SQLITE_URL = os.getenv(
    "SQLITE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'singalong.db'}",
)
POSTGRES_URL = _normalize_db_url(os.environ["DATABASE_URL"])
BATCH_SIZE = 100

SONG_FIELDS = (
    "yt_video_id",
    "title",
    "artist",
    "language",
    "play_count",
    "last_played_at",
    "thumbnail_url",
    "duration_sec",
    "source_status",
    "last_synced_at",
    "plain_lyrics",
    "synced_lyrics",
    "chordpro_full",
    "chordpro_easy",
    "easy_note_he",
    "easy_note_en",
    "enrich_error",
    "chord_source",
    "source_url",
    "enriched_at",
    "enrich_attempts",
    "enrich_history",
    "deleted_at",
)


def _copy_song_fields(src: Song, dst: Song) -> None:
    for field in SONG_FIELDS:
        setattr(dst, field, getattr(src, field))


def sync_songs(sqlite_db: Session, pg_db: Session) -> tuple[int, int, int]:
    src_rows = sqlite_db.query(Song).order_by(Song.id).all()
    updated = 0
    missing = 0
    skipped = 0

    for start in range(0, len(src_rows), BATCH_SIZE):
        batch = src_rows[start : start + BATCH_SIZE]
        ids = [row.id for row in batch]
        dst_by_id = {
            row.id: row for row in pg_db.query(Song).filter(Song.id.in_(ids)).all()
        }
        for src in batch:
            dst = dst_by_id.get(src.id)
            if not dst:
                missing += 1
                continue
            if src.yt_video_id != dst.yt_video_id:
                skipped += 1
                continue
            _copy_song_fields(src, dst)
            updated += 1
        pg_db.commit()
        print(f"  songs {min(start + BATCH_SIZE, len(src_rows))}/{len(src_rows)}", flush=True)

    return updated, missing, skipped


def sync_room(sqlite_db: Session, pg_db: Session) -> None:
    src = sqlite_db.get(RoomState, 1)
    if not src:
        return
    dst = pg_db.get(RoomState, 1)
    if dst is None:
        dst = RoomState(id=1)
        pg_db.add(dst)
    dst.song_id = src.song_id
    dst.scroll_anchor = src.scroll_anchor
    dst.updated_at = src.updated_at
    pg_db.commit()


def sync_favorites(sqlite_db: Session, pg_db: Session) -> int:
    src_rows = sqlite_db.query(Favorite).all()
    if not src_rows:
        return 0
    pg_db.query(Favorite).delete()
    for row in src_rows:
        pg_db.merge(Favorite(song_id=row.song_id, added_at=row.added_at))
    pg_db.commit()
    return len(src_rows)


def main() -> None:
    if POSTGRES_URL.startswith("sqlite"):
        print("Set DATABASE_URL to your Supabase Postgres URI.", file=sys.stderr)
        raise SystemExit(1)

    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    pg_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    sqlite_db = sessionmaker(bind=sqlite_engine)()
    pg_db = sessionmaker(bind=pg_engine)()

    try:
        count = sqlite_db.scalar(select(Song.id).limit(1))
        if count is None:
            print("Local SQLite has no songs.", file=sys.stderr)
            raise SystemExit(1)

        print("Syncing songs SQLite -> Supabase ...", flush=True)
        updated, missing, skipped = sync_songs(sqlite_db, pg_db)
        print(f"Songs: {updated} updated, {missing} missing in Supabase, {skipped} id/video mismatch", flush=True)

        sync_room(sqlite_db, pg_db)
        print("Room state synced.", flush=True)

        fav_count = sync_favorites(sqlite_db, pg_db)
        print(f"Favorites synced ({fav_count}).", flush=True)
    finally:
        sqlite_db.close()
        pg_db.close()


if __name__ == "__main__":
    main()
