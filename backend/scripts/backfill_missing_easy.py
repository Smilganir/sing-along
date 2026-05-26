"""Backfill chordpro_easy for songs that are missing an easy version."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import SessionLocal, init_db
from services.enrichment import backfill_missing_easy_sheets


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing easy chord sheets")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    parser.add_argument("--limit", type=int, default=None, help="Max songs to scan")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        stats = backfill_missing_easy_sheets(db, dry_run=args.dry_run, limit=args.limit)
    finally:
        db.close()

    mode = "Dry run" if args.dry_run else "Backfill"
    print(
        f"{mode} done: scanned={stats.scanned} updated={stats.updated} "
        f"skipped={stats.skipped} unchanged={stats.unchanged}"
    )


if __name__ == "__main__":
    main()
