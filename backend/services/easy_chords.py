"""Transpose-based easy ChordPro sheets (computed at display time, not stored per song)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from services.chord_suffixes import CHORD_TOKEN_PATTERN, simplify_chord_to_triad

CHORD_PATTERN = CHORD_TOKEN_PATTERN

CHORD_ROOT_SUFFIX = re.compile(r"^([A-G][#b]?)(.*)$", re.IGNORECASE)

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

MINOR_KEY_TARGETS = ("Am", "Em", "G")
MAJOR_KEY_TARGETS = ("C", "G", "Em")
KNOWN_KEY_LABELS = frozenset({"Am", "C", "Em", "G"})

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


@dataclass(frozen=True)
class _ShiftCandidate:
    shift: int
    score: int
    lands_on_priority: bool
    abs_shift: int
    sheet: str


def apply_easy_versions(chordpro: str, language: str = "en") -> EasyVersionResult:
    """Build an easy sheet by transposing to the most convenient open key."""
    chords = extract_chords(chordpro)
    if not chords:
        return _empty(chordpro)

    work = simplify_chords_in_sheet(chordpro)
    work_chords = extract_chords(work)
    simplified = [simplify_chord_name(chord) for chord in work_chords]

    if is_easy_progression(simplified):
        return EasyVersionResult(
            chordpro_full=chordpro,
            chordpro_easy=work,
            easy_note_he=None,
            easy_note_en=None,
        )

    first = work_chords[0]

    if not _any_shift_fully_easy(work, range(12)):
        for capo in range(1, 12):
            candidate = _evaluate_candidate(work, -capo)
            if candidate:
                note_he = f"גרסה קלה — קאפו בסריג {capo} (צורות פתוחות)"
                note_en = f"Easy version — capo on fret {capo} (open shapes)"
                return EasyVersionResult(
                    chordpro_full=chordpro,
                    chordpro_easy=candidate,
                    easy_note_he=note_he,
                    easy_note_en=note_en,
                )

    best = _pick_best_shift(work, first)
    key_label = _result_key_label(best.sheet)
    note_he, note_en = _easy_note(key_label, language)
    return EasyVersionResult(
        chordpro_full=chordpro,
        chordpro_easy=best.sheet,
        easy_note_he=note_he,
        easy_note_en=note_en,
    )


def _empty(chordpro: str) -> EasyVersionResult:
    return EasyVersionResult(
        chordpro_full=chordpro,
        chordpro_easy=None,
        easy_note_he=None,
        easy_note_en=None,
    )


def _easy_key_targets(first_chord: str) -> tuple[str, ...]:
    return MINOR_KEY_TARGETS if _is_minor_chord(first_chord) else MAJOR_KEY_TARGETS


def _is_minor_chord(chord: str) -> bool:
    simple = simplify_chord_name(chord)
    return simple.endswith("m") and not simple.endswith("maj")


def _any_shift_fully_easy(work: str, shifts: range) -> bool:
    return any(_evaluate_candidate(work, shift) for shift in shifts)


def _score_shift(work: str, shift: int, priority_targets: tuple[str, ...]) -> _ShiftCandidate:
    transposed = simplify_chords_in_sheet(transpose_sheet(work, shift))
    chords = extract_chords(transposed)
    simplified = [simplify_chord_name(chord) for chord in chords]
    distinct = set(simplified)
    score = sum(1 for chord in distinct if chord in EASY_CHORDS)
    first_simple = simplified[0] if simplified else ""
    lands_on_priority = first_simple in priority_targets
    return _ShiftCandidate(shift, score, lands_on_priority, abs(shift), transposed)


def _pick_best_shift(work: str, first_chord: str) -> _ShiftCandidate:
    priority_targets = _easy_key_targets(first_chord)
    best: _ShiftCandidate | None = None
    best_key: tuple[int, bool, int] | None = None

    for shift in range(12):
        candidate = _score_shift(work, shift, priority_targets)
        sort_key = (candidate.score, candidate.lands_on_priority, -candidate.abs_shift)
        if best is None or sort_key > best_key:
            best = candidate
            best_key = sort_key

    assert best is not None
    return best


def _result_key_label(result_sheet: str) -> str:
    chords = extract_chords(result_sheet)
    if not chords:
        return ""
    first_simple = simplify_chord_name(chords[0])
    return first_simple if first_simple in KNOWN_KEY_LABELS else first_simple


def _evaluate_candidate(work: str, shift: int) -> str | None:
    candidate = simplify_chords_in_sheet(transpose_sheet(work, shift))
    chords = [simplify_chord_name(chord) for chord in extract_chords(candidate)]
    return candidate if is_easy_progression(chords) else None


def _easy_note(key: str, language: str) -> tuple[str, str]:
    labels = {
        "Am": ("סול מ (Am)", "Am key"),
        "C": ("דו מז'ור (C)", "C major"),
        "Em": ("מי מ (Em)", "Em key"),
        "G": ("סול מז'ור (G)", "G major"),
    }
    he_label, en_label = labels.get(key, ("", key))
    if language == "he":
        return f"גרסה קלה — {he_label}", f"Easy version — {en_label}"
    return f"גרסה קלה — {he_label}", f"Easy version — {en_label}"


def _substitute_chords(text: str, mapping: dict[str, str]) -> str:
    def replace_match(match: re.Match[str]) -> str:
        chord = match.group(1)
        return mapping.get(chord, chord)

    return CHORD_PATTERN.sub(replace_match, text)


def apply_chord_mapping(
    text: str,
    mapping: dict[str, str],
    *,
    semitones: int = 0,
    source_chords: list[str] | None = None,
) -> str:
    del semitones, source_chords
    return _substitute_chords(text, mapping)


def simplify_chord_name(chord: str) -> str:
    return simplify_chord_to_triad(chord)


def simplify_chords_in_sheet(text: str) -> str:
    mapping = {chord: simplify_chord_name(chord) for chord in extract_chords(text)}
    return _substitute_chords(text, mapping)


def sheets_drifted_from_source(chordpro_full: str | None, fetched_content: str) -> bool:
    if not chordpro_full or not fetched_content.strip():
        return False
    src_chords = extract_chords(fetched_content)
    if not src_chords or not is_easy_progression([simplify_chord_name(c) for c in src_chords]):
        return False
    full_chords = extract_chords(chordpro_full)
    return full_chords != src_chords


def has_inverted_easy_pattern(chordpro_full: str | None, chordpro_easy: str | None) -> bool:
    if not chordpro_full or not chordpro_easy or chordpro_full == chordpro_easy:
        return False
    easy_chords = [simplify_chord_name(c) for c in extract_chords(chordpro_easy)]
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
    mapping = {chord: transpose_chord(chord, semitones) for chord in extract_chords(text)}
    return _substitute_chords(text, mapping)


def transpose_chord(chord: str, semitones: int) -> str:
    if "/" in chord:
        base, bass = chord.split("/", 1)
        return f"{transpose_chord(base, semitones)}/{transpose_chord(bass, semitones)}"

    match = re.match(r"^([A-G][#b]?)(.*)$", chord)
    if not match:
        return chord
    root, suffix = match.groups()
    normalized = FLAT_ALIASES.get(root, root)
    if normalized not in NOTES:
        return chord
    index = (NOTES.index(normalized) + semitones) % 12
    note = NOTES[index]
    prefer_flat = "b" in root.lower()
    if prefer_flat and "#" in note and note in SHARP_TO_FLAT:
        new_root = SHARP_TO_FLAT[note]
    else:
        new_root = note
    return f"{new_root}{suffix}"
