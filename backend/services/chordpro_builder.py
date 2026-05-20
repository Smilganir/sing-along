from services.chords_fetcher import ChordSheetResult
from services.lyrics_fetcher import LyricsResult


def build_chordpro(
    title: str,
    artist: str,
    lyrics: LyricsResult | None,
    chords: ChordSheetResult | None,
) -> tuple[str, bool]:
    header = [f"{{title: {title}}}", f"{{artist: {artist}}}", ""]

    if chords and chords.has_chords:
        return "\n".join(header + [chords.content]), True

    if chords and chords.content:
        body = chords.content
    elif lyrics:
        body = lyrics.plain_lyrics
    else:
        return "", False

    return "\n".join(header + [body]), False


def build_status(has_lyrics: bool, has_chords: bool) -> str:
    if has_chords:
        return "ready"
    if has_lyrics:
        return "needs_chords"
    return "failed"
