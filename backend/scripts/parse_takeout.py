"""CLI helper to preview ranked songs from a Takeout watch-history.json file."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.takeout_sync import parse_takeout_history  # noqa: E402


def main() -> None:
    default_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "takeout"
        / "Takeout"
        / "YouTube and YouTube Music"
        / "history"
        / "watch-history.json"
    )
    path = default_path
    limit = 50
    output_json: Path | None = None

    for arg in sys.argv[1:]:
        if arg.isdigit():
            limit = int(arg)
        elif Path(arg).exists():
            path = Path(arg)
        elif arg.endswith(".json"):
            output_json = Path(arg)

    ranked, music_entries = parse_takeout_history(path)
    total_plays = sum(item["play_count"] for item in ranked)

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(
            json.dumps(ranked[:limit], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Source: {path}")
    print(f"Total YouTube Music plays: {total_plays}")
    print(f"Unique songs: {len(ranked)}")
    print(f"Music history entries processed: {music_entries}")
    print()
    print(f"TOP {min(limit, len(ranked))} MOST PLAYED")
    print("-" * 95)

    for index, song in enumerate(ranked[:limit], 1):
        lang = song["language"].upper()
        artist = song["artist"][:35] + ("…" if len(song["artist"]) > 35 else "")
        title = song["title"][:48] + ("…" if len(song["title"]) > 48 else "")
        print(f"{index:3}. [{lang}] {song['play_count']:3}x  {title:<50}  {artist}")


if __name__ == "__main__":
    main()
