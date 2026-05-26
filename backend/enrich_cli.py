"""Unified enrichment CLI for Sing-Along.

Usage (from backend/):
    python -m enrich_cli top [--limit N] [--offset N] [--force]
    python -m enrich_cli retry [--limit N] [--language he|en] [--statuses failed,needs_chords] [--dry-run]
    python -m enrich_cli one <song_id> [--no-force]
    python -m enrich_cli continue [--start-offset N] [--batch-size N] [--batch-count N] [--skip-retry]
    python -m enrich_cli repair [--limit N] [--song-id ID] [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from db.database import SessionLocal, init_db
from db.models import Song
from services.enrichment import (
    EnrichSummary,
    enrich_retry_songs,
    enrich_song,
    enrich_top_songs,
    repair_drifted_sheets,
    backfill_missing_easy_sheets,
)
from services.easy_chords import has_inverted_easy_pattern, sheets_drifted_from_source
from services.chords_fetcher import fetch_chords_from_url


@dataclass
class RetryAttempt:
    title: str
    artist: str
    old_status: str
    new_status: str
    new_chord_source: str | None


def configure_utf8() -> None:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)


def safe(value: str | None, width: int) -> str:
    text = (value or "").strip()
    if len(text) <= width:
        return text.ljust(width)
    return text[: width - 1] + "…"


def print_summary(label: str, summary: EnrichSummary) -> None:
    print(f"\n{label}: {summary}")


def load_retry_candidates(
    db,
    *,
    limit: int,
    language: str | None,
    statuses: tuple[str, ...],
) -> list[Song]:
    query = db.query(Song).filter(
        Song.deleted_at.is_(None),
        Song.source_status.in_(statuses),
    )
    if language:
        query = query.filter(Song.language == language)
    return query.order_by(Song.play_count.desc(), Song.title.asc()).limit(limit).all()


def print_retry_dry_run(songs: list[Song], statuses: tuple[str, ...]) -> None:
    status_label = ", ".join(statuses)
    print(f"\nDry run — {len(songs)} candidate(s) for retry ({status_label}):\n")
    print(f"  {'#':>3}  {'status':<14}  {'lang':<4}  {'plays':>6}  {'source':<8}  artist · title")
    print(f"  {'-' * 3}  {'-' * 14}  {'-' * 4}  {'-' * 6}  {'-' * 8}  {'-' * 60}")
    for i, song in enumerate(songs, 1):
        plays = song.play_count or 0
        source = song.chord_source or "—"
        artist = song.artist or "Unknown"
        print(
            f"  {i:>3}  {song.source_status:<14}  {song.language:<4}  {plays:>6}  {source:<8}  "
            f"{safe(artist, 28)} · {safe(song.title, 60)}"
        )


def run_filtered_retry(
    db,
    songs: list[Song],
    *,
    delay: float,
) -> tuple[EnrichSummary, list[RetryAttempt]]:
    summary = EnrichSummary(
        processed=0, ready=0, needs_chords=0, failed=0, skipped=0, skipped_max_attempts=0
    )
    attempts: list[RetryAttempt] = []
    total = len(songs)

    for index, song in enumerate(songs, 1):
        old_status = song.source_status
        old_title = song.title
        old_artist = song.artist

        try:
            new_status = enrich_song(song, force=True)
            db.commit()
        except Exception as exc:
            db.rollback()
            new_status = "failed"
            song.enrich_error = f"crash: {exc}"

        summary.processed += 1
        if new_status == "ready":
            summary.ready += 1
        elif new_status == "needs_chords":
            summary.needs_chords += 1
        else:
            summary.failed += 1

        attempts.append(
            RetryAttempt(
                title=old_title,
                artist=old_artist,
                old_status=old_status,
                new_status=new_status,
                new_chord_source=song.chord_source,
            )
        )

        marker = {
            "ready": "OK  ",
            "needs_chords": "LYR ",
            "failed": "MISS",
        }.get(new_status, new_status[:4])
        print(
            f"  [{index:>3}/{total}] {marker}  "
            f"{safe(old_artist or 'Unknown', 24)} · {safe(old_title, 48)}",
            flush=True,
        )

        if index < total and delay > 0:
            time.sleep(delay)

    return summary, attempts


def print_retry_report(summary: EnrichSummary, attempts: list[RetryAttempt]) -> None:
    if not attempts:
        print("\nNo songs attempted.")
        return

    recovered_ready = [a for a in attempts if a.new_status == "ready"]
    recovered_needs = [a for a in attempts if a.new_status == "needs_chords"]
    recovered_total = len(recovered_ready) + len(recovered_needs)
    recovery_pct = (recovered_total / len(attempts)) * 100 if attempts else 0.0

    print("\n" + "=" * 60)
    print("RETRY REPORT")
    print("=" * 60)
    print(f"Total attempted         : {summary.processed}")
    print(f"Recovered → ready       : {summary.ready}")
    print(f"Recovered → needs_chords: {summary.needs_chords}")
    print(f"Still failed            : {summary.failed}")
    print(f"Recovery rate           : {recovery_pct:.1f}%")

    if recovered_ready:
        print("\nTop ready recoveries:")
        for attempt in recovered_ready[:5]:
            print(
                f"  - {safe(attempt.artist or 'Unknown', 24)} · "
                f"{safe(attempt.title, 50)}  [{attempt.new_chord_source or '—'}]"
            )

    if recovered_needs:
        print("\nTop needs_chords recoveries:")
        for attempt in recovered_needs[:5]:
            print(
                f"  - {safe(attempt.artist or 'Unknown', 24)} · "
                f"{safe(attempt.title, 50)}  [{attempt.new_chord_source or '—'}]"
            )

    recovered = recovered_ready + recovered_needs
    if recovered:
        sources = Counter((a.new_chord_source or "unknown") for a in recovered)
        print("\nPer-source breakdown (recovered songs):")
        for src, count in sources.most_common():
            print(f"  {src:<10} {count}")


def cmd_top(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        print(f"Enriching songs rank {args.offset + 1}–{args.offset + args.limit} (force={args.force})…")
        summary = enrich_top_songs(
            db,
            limit=args.limit,
            offset=args.offset,
            force=args.force,
            delay_sec=0.4,
        )
        print_summary("Top enrichment done", summary)
    finally:
        db.close()


def cmd_retry(args: argparse.Namespace) -> None:
    statuses = tuple(s.strip() for s in args.statuses.split(",") if s.strip())
    if not statuses:
        print("No statuses provided.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        songs = load_retry_candidates(
            db,
            limit=args.limit,
            language=args.language,
            statuses=statuses,
        )

        if not songs:
            scope = f" {args.language}" if args.language else ""
            print(f"No{scope} songs matching {statuses} to retry.")
            return

        if args.dry_run:
            print_retry_dry_run(songs, statuses)
            return

        if args.reset_attempts:
            for song in songs:
                song.enrich_attempts = 0
            db.commit()
            print(f"Reset enrich_attempts for {len(songs)} song(s).")

        status_label = ", ".join(statuses)
        scope = f" {args.language}" if args.language else ""
        print(f"\nRetrying {len(songs)}{scope} song(s) ({status_label}) with force=True…\n")
        summary, attempts = run_filtered_retry(db, songs, delay=args.delay)
        print_retry_report(summary, attempts)
        print_summary("Retry enrichment done", summary)
    finally:
        db.close()


def cmd_one(args: argparse.Namespace) -> None:
    force = not args.no_force
    db = SessionLocal()
    try:
        song = (
            db.query(Song)
            .filter(Song.deleted_at.is_(None), Song.id == args.song_id)
            .one_or_none()
        )
        if song is None:
            print(f"Song {args.song_id} not found.", file=sys.stderr)
            sys.exit(1)

        print(f"Enriching song {song.id}: {song.title} (force={force})…")
        status = enrich_song(song, force=force)
        db.commit()

        summary = EnrichSummary(
            processed=1,
            ready=1 if status == "ready" else 0,
            needs_chords=1 if status == "needs_chords" else 0,
            failed=1 if status not in {"ready", "needs_chords"} else 0,
            skipped=0,
            skipped_max_attempts=0,
        )
        print(f"Result: {status} (source={song.chord_source or '—'})")
        if song.enrich_error:
            print(f"Error: {song.enrich_error}")
        print_summary("Single-song enrichment done", summary)
    finally:
        db.close()


def run_continue_batch(label: str, limit: int, offset: int) -> EnrichSummary:
    print(f"\n[{datetime.now().isoformat()}] {label} — rank {offset + 1}–{offset + limit}", flush=True)
    db = SessionLocal()
    try:
        summary = enrich_top_songs(db, limit=limit, offset=offset, force=False, delay_sec=0.4)
        print(f"[{datetime.now().isoformat()}] {label} done: {summary}", flush=True)
        return summary
    finally:
        db.close()


def cmd_continue(args: argparse.Namespace) -> None:
    if not args.skip_retry:
        db = SessionLocal()
        try:
            print(f"\n[{datetime.now().isoformat()}] Retry needs_chords + failed", flush=True)
            retry_summary = enrich_retry_songs(db, delay_sec=0.5)
            print(f"[{datetime.now().isoformat()}] Retry done: {retry_summary}", flush=True)
        finally:
            db.close()

    totals = EnrichSummary(
        processed=0, ready=0, needs_chords=0, failed=0, skipped=0, skipped_max_attempts=0
    )
    for i in range(args.batch_count):
        offset = args.start_offset + i * args.batch_size
        batch_summary = run_continue_batch(f"Batch {i + 1}", args.batch_size, offset)
        totals.processed += batch_summary.processed
        totals.ready += batch_summary.ready
        totals.needs_chords += batch_summary.needs_chords
        totals.failed += batch_summary.failed
        totals.skipped += batch_summary.skipped

    print_summary("Continue enrichment done", totals)


def cmd_repair(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        if args.dry_run:
            query = db.query(Song).filter(
                Song.deleted_at.is_(None),
                Song.source_url.isnot(None),
                Song.chordpro_full.isnot(None),
            )
            if args.song_id is not None:
                query = query.filter(Song.id == args.song_id)
            query = query.order_by(Song.play_count.desc(), Song.id.asc())
            if args.limit is not None:
                query = query.limit(args.limit)

            candidates: list[Song] = []
            for song in query.all():
                if song.chordpro_full == song.chordpro_easy:
                    continue
                if not has_inverted_easy_pattern(song.chordpro_full, song.chordpro_easy):
                    continue
                try:
                    chords = fetch_chords_from_url(song.source_url)
                    if sheets_drifted_from_source(song.chordpro_full, chords.content):
                        candidates.append(song)
                except Exception:
                    continue

            print(f"\nDry run — {len(candidates)} song(s) would be repaired:\n")
            for song in candidates:
                print(f"  {song.id:>5}  {safe(song.artist or 'Unknown', 24)} · {safe(song.title, 50)}")
            return

        print(
            f"Repairing drifted sheets"
            + (f" for song {args.song_id}" if args.song_id else "")
            + (f" (limit {args.limit})" if args.limit else "")
            + "…"
        )
        summary = repair_drifted_sheets(
            db,
            limit=args.limit,
            song_id=args.song_id,
            delay_sec=args.delay,
        )
        db.commit()
        print(
            f"\nRepair done: scanned={summary.scanned} repaired={summary.repaired} "
            f"skipped={summary.skipped} failed={summary.failed}"
        )
    finally:
        db.close()


def cmd_backfill_easy(args: argparse.Namespace) -> None:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sing-Along enrichment CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    top = subparsers.add_parser("top", help="Enrich top songs by play count")
    top.add_argument("--limit", type=int, default=100, help="Number of songs (default: 100)")
    top.add_argument("--offset", type=int, default=0, help="Rank offset (default: 0)")
    top.add_argument("--force", action="store_true", help="Re-enrich even if already ready")
    top.set_defaults(func=cmd_top)

    retry = subparsers.add_parser("retry", help="Retry songs by status with recovery report")
    retry.add_argument("--limit", type=int, default=100, help="Max songs to retry (default: 100)")
    retry.add_argument("--language", choices=("he", "en"), default=None, help="Filter by language")
    retry.add_argument(
        "--statuses",
        default="failed",
        help="Comma-separated statuses (default: failed)",
    )
    retry.add_argument("--dry-run", action="store_true", help="List candidates without enriching")
    retry.add_argument("--delay", type=float, default=0.5, help="Delay between songs (default: 0.5)")
    retry.add_argument(
        "--reset-attempts",
        action="store_true",
        help="Reset enrich_attempts counter before retrying",
    )
    retry.set_defaults(func=cmd_retry)

    one = subparsers.add_parser("one", help="Enrich a single song by ID")
    one.add_argument("song_id", type=int, help="Song database ID")
    one.add_argument("--no-force", action="store_true", help="Skip if sheet already exists")
    one.set_defaults(func=cmd_one)

    cont = subparsers.add_parser("continue", help="Retry failures then enrich ranked batches")
    cont.add_argument("--start-offset", type=int, default=1000, help="First rank offset (default: 1000)")
    cont.add_argument("--batch-size", type=int, default=500, help="Songs per batch (default: 500)")
    cont.add_argument("--batch-count", type=int, default=4, help="Number of batches (default: 4)")
    cont.add_argument("--skip-retry", action="store_true", help="Skip needs_chords/failed retry pass")
    cont.set_defaults(func=cmd_continue)

    repair = subparsers.add_parser(
        "repair",
        help="Re-fetch source_url tabs and fix chordpro_full drift (e.g. A#m vs Am)",
    )
    repair.add_argument("--limit", type=int, default=None, help="Max songs to scan (default: all)")
    repair.add_argument("--song-id", type=int, default=None, help="Repair a single song by ID")
    repair.add_argument("--dry-run", action="store_true", help="List candidates without repairing")
    repair.add_argument("--delay", type=float, default=0.3, help="Delay between fetches (default: 0.3)")
    repair.set_defaults(func=cmd_repair)

    backfill_easy = subparsers.add_parser(
        "backfill-easy",
        help="Generate missing chordpro_easy sheets (capo, simplify, or Am/Em fallback)",
    )
    backfill_easy.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    backfill_easy.add_argument("--limit", type=int, default=None, help="Max songs to scan")
    backfill_easy.set_defaults(func=cmd_backfill_easy)

    return parser


def main() -> None:
    configure_utf8()
    init_db()
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
