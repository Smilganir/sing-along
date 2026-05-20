"""Build original vs easy ChordPro sheets from fetched chord content."""

from __future__ import annotations

import re
from dataclasses import dataclass

CHORD_PATTERN = re.compile(
    r"\b([A-G][#b]?(?:m|maj|min|dim|aug|sus(?:2|4)?|add|maj7|m7|7|9|11|13)?(?:add(?:9|11)?)?)\b"
)

EASY_CHORDS = frozenset(
    {
        "A",
        "Am",
        "C",
        "D",
        "Dm",
        "E",
        "Em",
        "G",
        "F",
        "A7",
        "C7",
        "D7",
        "E7",
        "G7",
    }
)

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_ALIASES = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
    "Cb": "B",
    "Fb": "E",
}
SHARP_TO_FLAT = {v: k for k, v in FLAT_ALIASES.items()}


@dataclass
class EasyVersionResult:
    chordpro_full: str
    chordpro_easy: str | None
    easy_note_he: str | None
    easy_note_en: str | None


def apply_easy_versions(chordpro: str, language: str = "en") -> EasyVersionResult:
    """Split fetched sheet into original (full) and optional easy version."""
    chords = extract_chords(chordpro)
    if not chords:
        return EasyVersionResult(chordpro_full=chordpro, chordpro_easy=None, easy_note_he=None, easy_note_en=None)

    if is_easy_progression(chords):
        # Fetched sheets from chord sites are already in the song's playing key
        # (e.g. Am C G F). Never transpose that up for "full" — keep source as-is.
        return EasyVersionResult(
            chordpro_full=chordpro,
            chordpro_easy=chordpro,
            easy_note_he=None,
            easy_note_en=None,
        )

    easy_capo = _best_easy_capo(chords)
    if easy_capo is None:
        return EasyVersionResult(
            chordpro_full=chordpro,
            chordpro_easy=None,
            easy_note_he=None,
            easy_note_en=None,
        )

    easy = transpose_sheet(chordpro, -easy_capo)
    note_he = f"גרסה קלה — קאפו בסריג {easy_capo} כדי לנגן עם המקור"
    note_en = f"Easy version — capo on fret {easy_capo} to match the original"
    return EasyVersionResult(
        chordpro_full=chordpro,
        chordpro_easy=easy,
        easy_note_he=note_he,
        easy_note_en=note_en,
    )


def sheets_drifted_from_source(chordpro_full: str | None, fetched_content: str) -> bool:
    """True when stored full sheet no longer matches open-chord content from the source URL."""
    if not chordpro_full or not fetched_content.strip():
        return False
    src_chords = extract_chords(fetched_content)
    if not src_chords or not is_easy_progression(src_chords):
        return False
    full_chords = extract_chords(chordpro_full)
    return full_chords != src_chords


def has_inverted_easy_pattern(chordpro_full: str | None, chordpro_easy: str | None) -> bool:
    """True when full looks like easy transposed up (legacy bug) rather than a real capo split."""
    if not chordpro_full or not chordpro_easy or chordpro_full == chordpro_easy:
        return False
    easy_chords = extract_chords(chordpro_easy)
    if not is_easy_progression(easy_chords):
        return False
    for capo in range(1, 10):
        if transpose_sheet(chordpro_easy, capo) == chordpro_full:
            return True
    return False


def extract_chords(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if "|" in line:
            continue
        for match in CHORD_PATTERN.finditer(line):
            chord = match.group(1)
            if chord not in seen:
                seen.add(chord)
                found.append(chord)
    return found


def is_easy_progression(chords: list[str]) -> bool:
    return bool(chords) and all(chord in EASY_CHORDS for chord in chords)


def transpose_sheet(text: str, semitones: int) -> str:
    if semitones == 0:
        return text
    mapping = {}
    for chord in extract_chords(text):
        mapping[chord] = transpose_chord(chord, semitones)
    result = text
    for old, new in sorted(mapping.items(), key=lambda item: -len(item[0])):
        result = re.sub(rf"\b{re.escape(old)}\b", new, result)
    return result


def transpose_chord(chord: str, semitones: int) -> str:
    match = re.match(r"^([A-G][#b]?)(.*)$", chord)
    if not match:
        return chord
    root, suffix = match.groups()
    normalized = FLAT_ALIASES.get(root, root)
    if normalized not in NOTES:
        return chord
    index = (NOTES.index(normalized) + semitones) % 12
    prefer_flat = "b" in root.lower()
    if prefer_flat and NOTES[index] in SHARP_TO_FLAT:
        new_root = SHARP_TO_FLAT[NOTES[index]]
    else:
        new_root = NOTES[index]
    return f"{new_root}{suffix}"


def _best_easy_capo(chords: list[str]) -> int | None:
    for capo in range(1, 10):
        transposed = [transpose_chord(chord, -capo) for chord in chords]
        if is_easy_progression(transposed):
            return capo
    return None
