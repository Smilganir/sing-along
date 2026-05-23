"""Copy enriched song data from remote Postgres (Supabase) to local SQLite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from config import BASE_DIR, _normalize_db_url
from db.models import Song

SQLITE_URL = os.getenv(
    "SQLITE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'singalong.db'}",
)
POSTGRES_URL = _normalize_db_url(os.environ["DATABASE_URL"])
BATCH_SIZE = 50

ENRICHMENT_FIELDS = (
    "source_status",
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
)

COPYABLE_FIELDS = (
    "title",
    "artist",
    "language",
    "play_count",
    "last_played_at",
    "thumbnail_url",
    "duration_sec",
    *ENRICHMENT_FIELDS,
)


def main() -> None:
    if POSTGRES_URL.startswith("sqlite"):
        print("Set DATABASE_URL to your Supabase Postgres URI.", file=sys.stderr)
        raise SystemExit(1)

    sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    pg_engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)

    sqlite_db = SqliteSession()
    pg_db = PgSession()

    try:
        pg_ids = [
            row[0]
            for row in pg_db.execute(
                select(Song.id).where(
                    Song.deleted_at.is_(None),
                    (Song.chordpro_full.isnot(None))
                    | (Song.plain_lyrics.isnot(None))
                    | Song.source_status.in_(("ready", "needs_chords", "needs_review", "failed")),
                )
            ).all()
        ]
        print(f"Found {len(pg_ids)} enriched songs in Supabase", flush=True)

        updated = 0
        inserted = 0
        missing = 0
        for start in range(0, len(pg_ids), BATCH_SIZE):
            batch_ids = pg_ids[start : start + BATCH_SIZE]
            src_rows = pg_db.query(Song).filter(Song.id.in_(batch_ids)).all()
            video_ids = [s.yt_video_id for s in src_rows]
            dst_by_video = {
                s.yt_video_id: s
                for s in sqlite_db.query(Song).filter(Song.yt_video_id.in_(video_ids)).all()
            }
            for src in src_rows:
                dst = dst_by_video.get(src.yt_video_id)
                if not dst:
                    missing += 1
                    new_song = Song(
                        yt_video_id=src.yt_video_id,
                        last_synced_at=src.last_synced_at,
                    )
                    for field in COPYABLE_FIELDS:
                        setattr(new_song, field, getattr(src, field))
                    sqlite_db.add(new_song)
                    inserted += 1
                    continue
                dst.deleted_at = None
                for field in ENRICHMENT_FIELDS:
                    setattr(dst, field, getattr(src, field))
                updated += 1
            sqlite_db.commit()
            print(f"  ... {min(start + BATCH_SIZE, len(pg_ids))}/{len(pg_ids)} processed", flush=True)

        print(f"Done: {updated} updated, {inserted} inserted, {missing - inserted} not copied", flush=True)
    finally:
        sqlite_db.close()
        pg_db.close()


if __name__ == "__main__":
    main()
