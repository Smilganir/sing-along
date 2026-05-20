"""Shared HTTP session with SQLite disk cache for scraper requests."""

from __future__ import annotations

from pathlib import Path

import requests_cache
from requests import Request

CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "http_cache"
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

_session: requests_cache.CachedSession | None = None


def get_http_session() -> requests_cache.CachedSession:
    global _session
    if _session is None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _session = requests_cache.CachedSession(
            cache_name=str(CACHE_DIR / "scraper_cache"),
            backend="sqlite",
            expire_after=CACHE_TTL_SECONDS,
            allowable_methods=("GET",),
            stale_if_error=True,
        )
    return _session


def bust_cache_for_song(
    title: str,
    artist: str,
    language: str,
    source_url: str | None = None,
) -> int:
    """Delete cached scraper responses for the URLs a song enrichment would hit."""
    from services.chords_fetcher import candidate_cache_urls

    session = get_http_session()
    urls = candidate_cache_urls(title, artist, language)
    if source_url:
        urls.append(source_url)

    deleted = 0
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        key = session.cache.create_key(Request("GET", url).prepare())
        if key in session.cache.responses:
            session.cache.delete(urls=[url])
            deleted += 1
    return deleted


def clear_http_cache() -> None:
    get_http_session().cache.clear()
