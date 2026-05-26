import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import Song
from services.chordpro_builder import build_chordpro, build_status
from services.chords_fetcher import fetch_chords, fetch_chords_from_url
from services.easy_chords import apply_easy_versions, has_inverted_easy_pattern, sheets_drifted_from_source
from services.lyrics_fetcher import LyricsResult, fetch_lyrics

MAX_ENRICH_HISTORY = 10


@dataclass
class EnrichSummary:
    processed: int
    ready: int
    needs_chords: int
    failed: int
    skipped: int
    skipped_max_attempts: int = 0


def _has_valid_sheet(song: Song) -> bool:
    return bool(song.chordpro_full) and song.source_status in {"ready", "needs_chords"}


def _should_skip_enrichment(song: Song, force: bool) -> bool:
    return not force and _has_valid_sheet(song)


def should_retry(song: Song, max_attempts: int = 5) -> bool:
    return (song.enrich_attempts or 0) < max_attempts


def _append_enrich_attempt(song: Song, status: str) -> None:
    record = {
        "ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "status": status,
        "source": song.chord_source,
        "error": song.enrich_error,
    }
    history: list[dict] = []
    if song.enrich_history:
        try:
            history = json.loads(song.enrich_history)
        except json.JSONDecodeError:
            history = []
    history.append(record)
    song.enrich_history = json.dumps(history[-MAX_ENRICH_HISTORY:])
    song.enrich_attempts = (song.enrich_attempts or 0) + 1


def enrich_song(song: Song, force: bool = False) -> str:
    chords_only = (
        force
        and song.source_status == "needs_chords"
        and bool(song.plain_lyrics)
    )

    if _should_skip_enrichment(song, force):
        return song.source_status

    errors: list[str] = []
    lyrics: LyricsResult | None = None
    chords = None

    if chords_only:
        lyrics = LyricsResult(
            plain_lyrics=song.plain_lyrics or "",
            synced_lyrics=song.synced_lyrics,
            source="cached",
        )
    else:
        try:
            lyrics = fetch_lyrics(song.title, song.artist)
        except Exception as exc:
            errors.append(f"lyrics: {exc}")

    try:
        chords = fetch_chords(song.title, song.artist, song.language)
    except Exception as exc:
        errors.append(f"chords: {exc}")

    chordpro, has_chords = build_chordpro(song.title, song.artist, lyrics, chords)
    has_lyrics = bool(lyrics and lyrics.plain_lyrics) or bool(chords and chords.content)

    if lyrics:
        song.plain_lyrics = lyrics.plain_lyrics
        song.synced_lyrics = lyrics.synced_lyrics

    if chordpro:
        if has_chords:
            versions = apply_easy_versions(chordpro, song.language)
            song.chordpro_full = versions.chordpro_full
            song.chordpro_easy = versions.chordpro_easy
            song.easy_note_he = versions.easy_note_he
            song.easy_note_en = versions.easy_note_en
        else:
            song.chordpro_full = chordpro
            song.chordpro_easy = None
            song.easy_note_he = None
            song.easy_note_en = None

    if chords:
        song.chord_source = chords.source
        song.source_url = chords.source_url
    elif lyrics:
        song.chord_source = lyrics.source

    song.enriched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    song.enrich_error = "; ".join(errors) if errors else None
    song.source_status = build_status(has_lyrics, has_chords)

    if not has_lyrics and not has_chords:
        song.enrich_error = (song.enrich_error or "") + " No lyrics or chords found"

    _append_enrich_attempt(song, song.source_status)
    return song.source_status


def enrich_song_from_url(song: Song, source_url: str) -> str:
    """Re-enrich a song using chords/lyrics from a specific source URL."""
    errors: list[str] = []
    lyrics: LyricsResult | None = None

    if song.plain_lyrics:
        lyrics = LyricsResult(
            plain_lyrics=song.plain_lyrics,
            synced_lyrics=song.synced_lyrics,
            source="cached",
        )
    else:
        try:
            lyrics = fetch_lyrics(song.title, song.artist)
        except Exception as exc:
            errors.append(f"lyrics: {exc}")

    chords = fetch_chords_from_url(source_url)

    chordpro, has_chords = build_chordpro(song.title, song.artist, lyrics, chords)
    has_lyrics = bool(lyrics and lyrics.plain_lyrics) or bool(chords.content)

    if lyrics and lyrics.source != "cached":
        song.plain_lyrics = lyrics.plain_lyrics
        song.synced_lyrics = lyrics.synced_lyrics

    if chordpro:
        if has_chords:
            versions = apply_easy_versions(chordpro, song.language)
            song.chordpro_full = versions.chordpro_full
            song.chordpro_easy = versions.chordpro_easy
            song.easy_note_he = versions.easy_note_he
            song.easy_note_en = versions.easy_note_en
        else:
            song.chordpro_full = chordpro
            song.chordpro_easy = None
            song.easy_note_he = None
            song.easy_note_en = None

    song.chord_source = chords.source
    song.source_url = chords.source_url
    song.enriched_at = datetime.now(timezone.utc).replace(tzinfo=None)
    song.enrich_error = "; ".join(errors) if errors else None
    song.source_status = build_status(has_lyrics, has_chords)

    if not has_lyrics and not has_chords:
        song.enrich_error = (song.enrich_error or "") + " No lyrics or chords found"

    _append_enrich_attempt(song, song.source_status)
    return song.source_status


def repair_song_sheets_from_url(song: Song) -> bool:
    """Re-fetch source_url and rebuild sheets when stored full drifts from the source tab."""
    if not song.source_url:
        return False

    lyrics: LyricsResult | None = None
    if song.plain_lyrics:
        lyrics = LyricsResult(
            plain_lyrics=song.plain_lyrics,
            synced_lyrics=song.synced_lyrics,
            source="cached",
        )

    try:
        chords = fetch_chords_from_url(song.source_url)
    except Exception:
        return False

    if not chords.content.strip():
        return False

    if not sheets_drifted_from_source(song.chordpro_full, chords.content):
        return False

    chordpro, has_chords = build_chordpro(song.title, song.artist, lyrics, chords)
    if not chordpro or not has_chords:
        return False

    versions = apply_easy_versions(chordpro, song.language)
    song.chordpro_full = versions.chordpro_full
    song.chordpro_easy = versions.chordpro_easy
    song.easy_note_he = versions.easy_note_he
    song.easy_note_en = versions.easy_note_en
    song.chord_source = chords.source
    return True


@dataclass
class RepairSummary:
    scanned: int
    repaired: int
    skipped: int
    failed: int


def repair_drifted_sheets(
    db: Session,
    *,
    limit: int | None = None,
    song_id: int | None = None,
    delay_sec: float = 0.3,
) -> RepairSummary:
    """Repair songs whose chordpro_full was wrongly transposed away from the source tab."""
    query = db.query(Song).filter(
        Song.deleted_at.is_(None),
        Song.source_url.isnot(None),
        Song.chordpro_full.isnot(None),
    )
    if song_id is not None:
        query = query.filter(Song.id == song_id)
    query = query.order_by(Song.play_count.desc(), Song.id.asc())
    if limit is not None:
        query = query.limit(limit)

    summary = RepairSummary(scanned=0, repaired=0, skipped=0, failed=0)
    songs = query.all()
    total = len(songs)

    for index, song in enumerate(songs, 1):
        summary.scanned += 1
        if song.chordpro_full == song.chordpro_easy:
            summary.skipped += 1
            continue
        if not has_inverted_easy_pattern(song.chordpro_full, song.chordpro_easy):
            summary.skipped += 1
            continue
        try:
            if repair_song_sheets_from_url(song):
                summary.repaired += 1
            else:
                summary.skipped += 1
        except Exception:
            summary.failed += 1
        if index < total and delay_sec > 0:
            time.sleep(delay_sec)

    return summary


def enrich_top_songs(
    db: Session,
    limit: int = 100,
    offset: int = 0,
    force: bool = False,
    delay_sec: float = 0.4,
) -> EnrichSummary:
    songs = (
        db.query(Song)
        .filter(Song.deleted_at.is_(None))
        .order_by(Song.play_count.desc(), Song.title.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    summary = EnrichSummary(
        processed=0, ready=0, needs_chords=0, failed=0, skipped=0, skipped_max_attempts=0
    )

    for song in songs:
        if _should_skip_enrichment(song, force):
            summary.skipped += 1
            continue

        status = enrich_song(song, force=force)
        summary.processed += 1
        print(f"  [{summary.processed}] {song.title[:60]} -> {status}", flush=True)
        if status == "ready":
            summary.ready += 1
        elif status == "needs_chords":
            summary.needs_chords += 1
        else:
            summary.failed += 1

        db.commit()
        time.sleep(delay_sec)

    return summary


def enrich_retry_songs(
    db: Session,
    delay_sec: float = 0.5,
    max_attempts: int = 5,
) -> EnrichSummary:
    """Re-fetch chords for needs_chords and retry failed songs."""
    songs = (
        db.query(Song)
        .filter(
            Song.deleted_at.is_(None),
            Song.source_status.in_(("needs_chords", "failed")),
        )
        .order_by(Song.play_count.desc(), Song.title.asc())
        .all()
    )

    summary = EnrichSummary(
        processed=0, ready=0, needs_chords=0, failed=0, skipped=0, skipped_max_attempts=0
    )

    for song in songs:
        if not should_retry(song, max_attempts=max_attempts):
            summary.skipped_max_attempts += 1
            continue

        status = enrich_song(song, force=True)
        summary.processed += 1
        print(f"  [{summary.processed}] {song.title[:60]} -> {status}", flush=True)
        if status == "ready":
            summary.ready += 1
        elif status == "needs_chords":
            summary.needs_chords += 1
        else:
            summary.failed += 1

        db.commit()
        time.sleep(delay_sec)

    return summary


@dataclass
class BackfillEasySummary:
    scanned: int
    updated: int
    skipped: int
    unchanged: int


def backfill_missing_easy_sheets(
    db: Session,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> BackfillEasySummary:
    query = (
        db.query(Song)
        .filter(
            Song.deleted_at.is_(None),
            Song.chordpro_full.isnot(None),
            Song.chordpro_full != "",
        )
        .order_by(Song.play_count.desc(), Song.id.asc())
    )
    if limit is not None:
        query = query.limit(limit)

    summary = BackfillEasySummary(scanned=0, updated=0, skipped=0, unchanged=0)
    for song in query.all():
        summary.scanned += 1
        if song.chordpro_easy and song.chordpro_easy.strip():
            summary.skipped += 1
            continue

        versions = apply_easy_versions(song.chordpro_full or "", song.language)
        if not versions.chordpro_easy:
            summary.unchanged += 1
            continue

        summary.updated += 1
        if dry_run:
            continue

        song.chordpro_easy = versions.chordpro_easy
        song.easy_note_he = versions.easy_note_he
        song.easy_note_en = versions.easy_note_en

    if not dry_run:
        db.commit()
    return summary
