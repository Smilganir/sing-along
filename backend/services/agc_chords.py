"""Map chord names to all-guitar-chords.com SVG diagram URLs."""

from __future__ import annotations

import re

AGC_BASE = "https://www.all-guitar-chords.com"

CHORD_NAME_RE = re.compile(
    r"^([A-G][#b]?)(.*)$",
    re.IGNORECASE,
)

FLAT_TO_SHARP = {
    "Db": "C#",
    "Eb": "D#",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
    "Cb": "B",
    "Fb": "E",
}

SUFFIX_MAP = {
    "": "major",
    "maj": "major",
    "m": "minor",
    "min": "minor",
    "7": "7",
    "maj7": "maj7",
    "M7": "maj7",
    "m7": "m7",
    "min7": "m7",
    "sus4": "sus4",
    "sus2": "sus2",
    "sus": "sus4",
    "dim": "dim",
    "aug": "aug",
    "add9": "add9",
    "6": "6",
}


def _normalize_root(root: str) -> str:
    if not root:
        return root
    letter = root[0].upper()
    acc = root[1:] if len(root) > 1 else ""
    if acc in ("b", "♭"):
        return FLAT_TO_SHARP.get(letter + "b", letter + "b")
    if acc in ("#", "♯"):
        return letter + "#"
    return letter


def _map_suffix(raw: str) -> str | None:
    if not raw:
        return "major"
    key = raw.strip()
    if key in SUFFIX_MAP:
        return SUFFIX_MAP[key]
    lowered = key.lower()
    if lowered in SUFFIX_MAP:
        return SUFFIX_MAP[lowered]
    # Common sheet spellings
    aliases = {
        "major": "major",
        "minor": "minor",
        "min7": "m7",
        "minor7": "m7",
    }
    return aliases.get(lowered)


def _root_to_svg_segment(root: str) -> str:
    letter = root[0].lower()
    if len(root) > 1 and root[1] == "#":
        return f"{letter}_sharp"
    return letter


def agc_svg_url(chord_name: str) -> str | None:
    """Return absolute SVG URL on all-guitar-chords.com, or None if unmapped."""
    clean = (chord_name or "").strip()
    if not clean:
        return None

    # Slash chords: diagram follows the chord quality, not bass note.
    clean = clean.split("/")[0].strip()

    match = CHORD_NAME_RE.match(clean)
    if not match:
        return None

    root = _normalize_root(match.group(1))
    suffix = _map_suffix(match.group(2))
    if suffix is None:
        return None

    svg_segment = _root_to_svg_segment(root)
    return f"{AGC_BASE}/chords/img/guitar-chord-{svg_segment}-{suffix}-1.svg"


_FRET_LABEL_Y = {61: 56, 101: 96, 141: 136, 181: 176}
_AXIS_LABEL_FILL = "#e2e8f0"
_FINGER_DOT_ORANGE = "#9381CB"
_FINGER_DOT_YELLOW = "#97CBE8"
_FINGER_NUMBER_TEXT_RE = re.compile(
    r"""<text x='(\d+)' y='(\d+)' font-size='14' font-family='Arial' fill='black'>(\d)</text>"""
)


def _is_fret_axis_label(tag: str) -> bool:
    return bool(re.search(r"""\bx=(['"])20\1""", tag))


def _is_string_axis_label(tag: str) -> bool:
    return bool(re.search(r"""\by=(['"])221\1""", tag))


def adapt_agc_svg_for_dark_bg(svg: str) -> str:
    """Style all-guitar-chords SVGs for the dark popover UI."""
    out = (
        svg.replace("fill='#e1dce2'", "fill='#243047'")
        .replace("fill='#FF8000'", f"fill='{_FINGER_DOT_ORANGE}'")
        .replace("fill='#FFBB00'", f"fill='{_FINGER_DOT_YELLOW}'")
        .replace("stroke='black'", "stroke='#94a3b8'")
    )
    out = re.sub(
        r"""<svg\s+width=['"]230['"]\s+height=['"]230['"]""",
        "<svg width='230' height='250' viewBox='0 0 230 250' overflow='visible'",
        out,
        count=1,
    )

    def center_finger_number(match: re.Match[str]) -> str:
        cx = int(match.group(1)) + 4
        cy = int(match.group(2)) - 5
        digit = match.group(3)
        return (
            f"<text x='{cx}' y='{cy}' font-size='14' font-family='Arial' fill='black' "
            f"text-anchor='middle' dominant-baseline='middle'>{digit}</text>"
        )

    out = _FINGER_NUMBER_TEXT_RE.sub(center_finger_number, out)

    label_fill = re.compile(r"""fill=(['"])(?:black|#000(?:000)?)\1""", re.IGNORECASE)

    def style_axis_label(match: re.Match[str]) -> str:
        tag = match.group(0)
        fret_label = _is_fret_axis_label(tag)
        string_label = _is_string_axis_label(tag)
        if not fret_label and not string_label:
            return tag

        next_tag = tag.replace("<text", '<text class="agc-axis-label"', 1)
        next_tag = label_fill.sub(rf"fill=\1{_AXIS_LABEL_FILL}\1", next_tag)
        if "fill=" not in next_tag:
            next_tag = next_tag.replace("<text", f"<text fill='{_AXIS_LABEL_FILL}'", 1)

        if string_label:
            next_tag = re.sub(
                r"""\by=(['"])221\1""",
                r"y=\g<1>228\g<1> dominant-baseline='middle'",
                next_tag,
            )

        if fret_label:
            def nudge_fret_y(y_match: re.Match[str]) -> str:
                quote = y_match.group(1)
                y_val = int(y_match.group(2))
                nudged = _FRET_LABEL_Y.get(y_val)
                if nudged is None:
                    return y_match.group(0)
                return f"y={quote}{nudged}{quote}"

            next_tag = re.sub(r"""\by=(['"])(\d+)\1""", nudge_fret_y, next_tag)
            if "dominant-baseline=" not in next_tag:
                next_tag = next_tag[:-1] + " dominant-baseline='middle'>"

        return next_tag

    return re.sub(r"<text[^>]*>", style_axis_label, out)
