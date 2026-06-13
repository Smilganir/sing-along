"""Pull recent YouTube Music history into the song library."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.database import SessionLocal, init_db
from services.ytmusic_sync import auth_configured, sync_ytmusic


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync YouTube Music play history")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only verify auth file exists, then exit",
    )
    args = parser.parse_args()

    if not auth_configured():
        print(
            "YouTube Music auth not found.\n\n"
            "1. Open https://music.youtube.com while logged in\n"
            "2. DevTools → Network → filter browse → copy request headers\n"
            "3. Run: ytmusicapi browser\n"
            "4. Move browser.json to backend/data/ytmusic/browser.json\n\n"
            "Or paste auth JSON via Admin → YouTube Music setup in the app.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if args.check:
        print("YouTube Music auth file found.")
        return

    init_db()
    db = SessionLocal()
    try:
        run = sync_ytmusic(db)
        play_events = getattr(run, "play_events", 0)
        print(
            f"Sync done: +{run.songs_added} added, {run.songs_updated} updated, "
            f"{play_events} new plays from {run.history_items} history rows"
        )
        if run.error:
            print(f"Warning: {run.error}", file=sys.stderr)
            raise SystemExit(1)
    except Exception as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
