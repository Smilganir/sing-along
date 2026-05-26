"""Build original vs easy ChordPro sheets from fetched chord content."""

from __future__ import annotations

import re
from dataclasses import dataclass

CHORD_PATTERN = re.compile(
    r"\b([A-G][#b]?(?:m|maj|min|dim|aug|sus(?:2|4)?|add|maj7|m7|7|9|11|13)?(?:add(?:9|11)?)?)\b"
)

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

# Open-shape substitutes when capo alone cannot simplify a progression.
COERCE_AM = {
    "A#": "A",
    "A#m": "Am",
    "Ab": "G",
    "Abm": "Am",
    "Bb": "A",
    "Bbm": "Am",
    "B": "Am",
    "Bm": "Am",
    "C#": "C",
    "C#m": "Am",
    "Db": "C",
    "Dbm": "Dm",
    "D#": "D",
    "D#m": "Dm",
    "Eb": "D",
    "Ebm": "Dm",
    "F#": "E",
    "F#m": "Em",
    "G#": "G",
    "G#m": "Em",
    "Gb": "F",
    "Gbm": "F",
    "Gm": "G",
}

COERCE_EM = {
    "A#": "A",
    "A#m": "Am",
    "Ab": "G",
    "Abm": "Am",
    "Bb": "A",
    "Bbm": "Am",
    "B": "Em",
    "Bm": "Am",
    "C#": "C",
    "C#m": "Am",
    "Db": "C",
    "Dbm": "Dm",
    "D#": "D",
    "D#m": "Dm",
    "Eb": "D",
    "Ebm": "Dm",
    "F#": "E",
    "F#m": "Em",
    "G#": "G",
    "G#m": "Em",
    "Gb": "F",
    "Gbm": "F",
    "Gm": "G",
}


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
        return _empty(chordpro)

    if is_easy_progression(chords):
        return EasyVersionResult(
            chordpro_full=chordpro,
            chordpro_easy=chordpro,
            easy_note_he=None,
            easy_note_en=None,
        )

    capo_result = _capo_easy_result(chordpro, chords, language)
    if capo_result:
        return capo_result

    simplified = simplify_chords_in_sheet(chordpro)
    simplified_chords = extract_chords(simplified)
    if simplified_chords != chords:
        capo_result = _capo_easy_result(chordpro, simplified_chords, language, sheet=simplified)
        if capo_result:
            return capo_result

    fallback = _fallback_am_em_key(chordpro, simplified, language)
    if fallback:
        return fallback

    return _empty(chordpro)


def _empty(chordpro: str) -> EasyVersionResult:
    return EasyVersionResult(
        chordpro_full=chordpro,
        chordpro_easy=None,
        easy_note_he=None,
        easy_note_en=None,
    )


def _capo_easy_result(
    chordpro_full: str,
    chords: list[str],
    language: str,
    *,
    sheet: str | None = None,
) -> EasyVersionResult | None:
    easy_capo = _best_easy_capo(chords)
    if easy_capo is None:
        return None

    source = sheet if sheet is not None else chordpro_full
    easy = transpose_sheet(source, -easy_capo)
    note_he = f"גרסה קלה — קאפו בסריג {easy_capo} כדי לנגן עם המקור"
    note_en = f"Easy version — capo on fret {easy_capo} to match the original"
    return EasyVersionResult(
        chordpro_full=chordpro_full,
        chordpro_easy=easy,
        easy_note_he=note_he,
        easy_note_en=note_en,
    )


def _fallback_am_em_key(
    chordpro_full: str,
    chordpro_work: str,
    language: str,
) -> EasyVersionResult | None:
    chords = extract_chords(chordpro_work)
    if not chords:
        return None

    target = "Am" if _minor_leaning(chords) else "Em"
    best: tuple[int, int, dict[str, str]] | None = None

    for shift in range(-11, 12):
        mapping = _coerce_mapping(chords, shift, target)
        coerced = [mapping[chord] for chord in chords]
        if not is_easy_progression(coerced):
            continue
        preserved = sum(1 for chord in chords if mapping[chord] == transpose_chord(chord, shift))
        if best is None or preserved > best[1] or (preserved == best[1] and abs(shift) < abs(best[0])):
            best = (shift, preserved, mapping)

    if best is None:
        shift = _shift_first_chord_to_target(chords[0], target)
        mapping = _coerce_mapping(chords, shift, target)
        coerced = [mapping[chord] for chord in chords]
        if not is_easy_progression(coerced):
            mapping = {
                chord: _coerce_to_key(transpose_chord(chord, shift), target) for chord in chords
            }
        best = (shift, 0, mapping)

    shift, _, mapping = best
    easy = apply_chord_mapping(transpose_sheet(chordpro_work, shift), mapping, semitones=shift, source_chords=chords)

    if target == "Am":
        note_he = "גרסה קלה — צורות פתוחות בסול מ (Am key)"
        note_en = "Easy version — simplified open shapes in Am key"
    else:
        note_he = "גרסה קלה — צורות פתוחות במי מ (Em key)"
        note_en = "Easy version — simplified open shapes in Em key"

    return EasyVersionResult(
        chordpro_full=chordpro_full,
        chordpro_easy=easy,
        easy_note_he=note_he,
        easy_note_en=note_en,
    )


def _coerce_mapping(chords: list[str], shift: int, target: str) -> dict[str, str]:
    return {
        chord: _coerce_to_key(transpose_chord(chord, shift), target)
        for chord in chords
    }


def apply_chord_mapping(
    text: str,
    mapping: dict[str, str],
    *,
    semitones: int,
    source_chords: list[str],
) -> str:
    """Replace transposed chord names with coerced easy shapes."""
    replacements: dict[str, str] = {}
    for chord in source_chords:
        transposed = transpose_chord(chord, semitones)
        replacements[transposed] = mapping[chord]

    result = text
    for old, new in sorted(replacements.items(), key=lambda item: -len(item[0])):
        if old != new:
            result = re.sub(rf"\b{re.escape(old)}\b", new, result)
    return result


def _minor_leaning(chords: list[str]) -> bool:
    minor = 0
    for chord in chords:
        simple = simplify_chord_name(chord)
        if simple.endswith("m") and not simple.endswith("maj"):
            minor += 1
    return minor >= max(1, len(chords) // 2)


def _shift_first_chord_to_target(first_chord: str, target: str) -> int:
    first = simplify_chord_name(first_chord)
    for shift in range(-11, 12):
        if simplify_chord_name(transpose_chord(first, shift)) == target:
            return shift
    return 0


def _coerce_to_key(chord: str, target: str) -> str:
    simplified = simplify_chord_name(chord)
    if simplified in EASY_CHORDS:
        return simplified
    table = COERCE_AM if target == "Am" else COERCE_EM
    if simplified in table:
        return table[simplified]
    return "Am" if target == "Am" else "Em"


def simplify_chord_name(chord: str) -> str:
    match = CHORD_ROOT_SUFFIX.match(chord)
    if not match:
        return chord
    root, suffix = match.group(1), match.group(2)
    if not suffix:
        return root
    lowered = suffix.lower()
    if lowered in ("m", "min"):
        return f"{root}m"
    if lowered in ("m7", "min7"):
        return f"{root}m"
    if "dim" in lowered:
        return f"{root}m"
    if "aug" in lowered:
        return root
    if lowered.startswith("m"):
        return f"{root}m"
    return root


def simplify_chords_in_sheet(text: str) -> str:
    mapping = {chord: simplify_chord_name(chord) for chord in extract_chords(text)}
    result = text
    for old, new in sorted(mapping.items(), key=lambda item: -len(item[0])):
        if old != new:
            result = re.sub(rf"\b{re.escape(old)}\b", new, result)
    return result


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
    for capo in range(1, 12):
        transposed = [transpose_chord(chord, -capo) for chord in chords]
        if is_easy_progression(transposed):
            return capo
    return None
