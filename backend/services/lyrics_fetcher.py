import re
from dataclasses import dataclass

from services.chords_fetcher import clean_title_for_search
from services.http_cache import get_http_session

LRCLIB_BASE = "https://lrclib.net/api"
USER_AGENT = "Sing-Along/0.2 (https://github.com/local/sing-along)"
HTTP = get_http_session()


@dataclass
class LyricsResult:
    plain_lyrics: str
    synced_lyrics: str | None
    source: str = "lrclib"


def clean_artist_name(artist: str) -> str:
    name = artist.replace(" - Topic", "").strip()
    if "," in name:
        name = name.split(",")[0].strip()
    return name


def fetch_lyrics(title: str, artist: str) -> LyricsResult | None:
    params = {
        "track_name": clean_title_for_search(title, artist),
        "artist_name": clean_artist_name(artist),
    }
    response = HTTP.get(
        f"{LRCLIB_BASE}/search",
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if not response.ok:
        return None

    results = response.json()
    if not results:
        return None

    best = _pick_best_match(results, title, artist)
    plain = (best.get("plainLyrics") or "").strip()
    if not plain:
        return None

    synced = (best.get("syncedLyrics") or "").strip() or None
    return LyricsResult(plain_lyrics=plain, synced_lyrics=synced)


def _pick_best_match(results: list[dict], title: str, artist: str) -> dict:
    title_key = clean_title_for_search(title, artist).lower()
    artist_key = clean_artist_name(artist).lower()

    def score(item: dict) -> int:
        value = 0
        if item.get("trackName", "").lower() == title_key:
            value += 3
        elif title_key in item.get("trackName", "").lower():
            value += 2
        if artist_key in item.get("artistName", "").lower():
            value += 2
        if item.get("plainLyrics"):
            value += 1
        return value

    return max(results, key=score)
