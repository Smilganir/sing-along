"""One-shot post-deploy seed: init DB, import Takeout, enrich top songs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import TAKEOUT_HISTORY_PATH
from db.database import SessionLocal, init_db
from services.enrichment import enrich_top_songs
from services.takeout_sync import import_takeout


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Takeout history and enrich top songs")
    parser.add_argument(
        "--takeout",
        type=Path,
        default=TAKEOUT_HISTORY_PATH,
        help="Path to watch-history.json",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        default=100,
        help="Number of top songs to enrich after import",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Import only; skip enrichment",
    )
    args = parser.parse_args()

    if not args.takeout.is_file():
        print(f"Takeout file not found: {args.takeout}", file=sys.stderr)
        raise SystemExit(1)

    init_db()
    db = SessionLocal()
    try:
        run = import_takeout(db, args.takeout)
        print(
            f"Import done: +{run.songs_added} added, {run.songs_updated} updated, "
            f"{run.history_items} history items"
        )
        if run.error:
            print(f"Import warning: {run.error}")

        if not args.skip_enrich:
            summary = enrich_top_songs(db, limit=args.enrich_limit, force=False, delay_sec=0.4)
            print(f"Enrichment done: {summary}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
