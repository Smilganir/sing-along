"""Map chord names to all-guitar-chords.com SVG diagram URLs."""

from __future__ import annotations

import re

from services.chord_suffixes import SUFFIX_TO_AGC

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


def _normalize_chord_name(chord_name: str) -> str:
    clean = (chord_name or "").strip().split("/")[0].strip()
    return re.sub(r"\(([#b]?\d+)\)", r"\1", clean)


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
        return SUFFIX_TO_AGC[""]
    key = raw.strip()
    if key in SUFFIX_TO_AGC:
        return SUFFIX_TO_AGC[key]
    lowered = key.lower()
    if lowered in SUFFIX_TO_AGC:
        return SUFFIX_TO_AGC[lowered]
    aliases = {
        "major": "major",
        "minor": "minor",
    }
    return aliases.get(lowered)


def _root_to_svg_segment(root: str) -> str:
    letter = root[0].lower()
    if len(root) > 1 and root[1] == "#":
        return f"{letter}_sharp"
    return letter


def agc_svg_url(chord_name: str) -> str | None:
    """Return absolute SVG URL on all-guitar-chords.com, or None if unmapped."""
    clean = _normalize_chord_name(chord_name)
    if not clean:
        return None

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
_STRING_STATUS_COLOR = "#94a3b8"
_FINGER_COLORS = {
    1: "#A2D2C9",
    2: "#A2C2F2",
    3: "#D2B4DE",
    4: "#F9B7D1",
}
_AGC_SHAPE_RE = re.compile(r"<(circle|rect)\s[^>]*/>")
_AGC_FINGER_NUM_TEXT_RE = re.compile(
    r"""<text x='(\d+)' y='(\d+)' font-size='14' font-family='(?:Arial|Heebo)' fill='black'([^>]*)>([1-4])</text>"""
)
_AGC_MUTE_TEXT_RE = re.compile(
    r"""<text x='(\d+)' y='26' font-size='20' font-family='Arial' fill='[^']*'>X</text>"""
)
_FINGER_NUMBER_TEXT_RE = re.compile(
    r"""<text x='(\d+)' y='(\d+)' font-size='14' font-family='(?:Arial|Heebo)' fill='black'>(\d)</text>"""
)


def _parse_agc_finger_labels(svg: str) -> list[dict[str, float | int]]:
    labels: list[dict[str, float | int]] = []
    for match in _AGC_FINGER_NUM_TEXT_RE.finditer(svg):
        centered = "text-anchor='middle'" in match.group(3)
        labels.append(
            {
                "x": int(match.group(1)) if centered else int(match.group(1)) + 4,
                "y": int(match.group(2)) if centered else int(match.group(2)) - 5,
                "digit": int(match.group(4)),
            }
        )
    return labels


def _parse_agc_shape(tag: str) -> dict[str, float | int | str] | None:
    if re.search(r"""width='150'\s+height='160'|height='160'\s+width='150'""", tag):
        return None

    if tag.startswith("<circle"):
        cx_match = re.search(r"cx='(\d+)'", tag)
        cy_match = re.search(r"cy='(\d+)'", tag)
        r_match = re.search(r"r='(\d+)'", tag)
        if not cx_match or not cy_match:
            return None
        cx = float(cx_match.group(1))
        cy = float(cy_match.group(1))
        r = float(r_match.group(1)) if r_match else 0.0
        if r <= 8 and cy <= 25:
            return {"kind": "open", "cx": cx, "cy": cy, "r": r}
        if r >= 12 and cy >= 40:
            return {"kind": "finger", "cx": cx, "cy": cy, "r": r}
        return None

    x_match = re.search(r"x='(\d+)'", tag)
    y_match = re.search(r"y='(\d+)'", tag)
    width_match = re.search(r"width='(\d+)'", tag)
    height_match = re.search(r"height='(\d+)'", tag)
    if not x_match or not y_match or not width_match or not height_match:
        return None
    width = float(width_match.group(1))
    height = float(height_match.group(1))
    x = float(x_match.group(1))
    y = float(y_match.group(1))
    if 26 <= height <= 30 and 20 <= width <= 120:
        return {"kind": "barre", "cx": x + width / 2, "cy": y + height / 2, "r": 0.0}
    return None


def _nearest_agc_finger_label(
    labels: list[dict[str, float | int]],
    cx: float,
    cy: float,
    max_distance: float = 24.0,
) -> dict[str, float | int] | None:
    best: dict[str, float | int] | None = None
    best_distance = max_distance
    for label in labels:
        distance = ((float(label["x"]) - cx) ** 2 + (float(label["y"]) - cy) ** 2) ** 0.5
        if distance < best_distance:
            best_distance = distance
            best = label
    return best


def _set_agc_fill(tag: str, fill_color: str) -> str:
    if re.search(r"fill='", tag):
        return re.sub(r"fill='[^']+'", f"fill='{fill_color}'", tag, count=1)
    return tag.replace("/>", f" fill='{fill_color}'/>", 1)


def _set_agc_stroke(tag: str, stroke_color: str, stroke_width: str = "2") -> str:
    next_tag = re.sub(r"stroke='[^']+'", f"stroke='{stroke_color}'", tag, count=1)
    if "stroke='" not in next_tag:
        next_tag = next_tag.replace("/>", f" stroke='{stroke_color}' stroke-width='{stroke_width}'/>", 1)
    elif "stroke-width='" not in next_tag:
        next_tag = next_tag.replace("/>", f" stroke-width='{stroke_width}'/>", 1)
    return next_tag


def _style_agc_open_string_marker(tag: str) -> str:
    return _set_agc_stroke(_set_agc_fill(tag, _STRING_STATUS_COLOR), "none", "0")


def _style_agc_finger_shape(tag: str, fill_color: str) -> str:
    return _set_agc_stroke(_set_agc_fill(tag, fill_color), "white")


def _style_agc_mute_markers(svg: str) -> str:
    return _AGC_MUTE_TEXT_RE.sub(
        rf"<text x='\1' y='26' font-size='20' font-family='Arial' fill='{_STRING_STATUS_COLOR}'>X</text>",
        svg,
    )


def _recolor_agc_finger_shapes(svg: str) -> str:
    labels = _parse_agc_finger_labels(svg)

    def replace_shape(match: re.Match[str]) -> str:
        tag = match.group(0)
        shape = _parse_agc_shape(tag)
        if shape is None:
            return tag

        if shape["kind"] == "open":
            return _style_agc_open_string_marker(tag)

        if shape["kind"] == "barre":
            return _style_agc_finger_shape(tag, _FINGER_COLORS[1])

        label = _nearest_agc_finger_label(labels, float(shape["cx"]), float(shape["cy"]))
        fill_color = _FINGER_COLORS[int(label["digit"])] if label else _FINGER_COLORS[2]
        return _style_agc_finger_shape(tag, fill_color)

    return _AGC_SHAPE_RE.sub(replace_shape, svg)


def _is_fret_axis_label(tag: str) -> bool:
    return bool(re.search(r"""\bx=(['"])20\1""", tag))


def _is_string_axis_label(tag: str) -> bool:
    return bool(re.search(r"""\by=(['"])221\1""", tag))


def adapt_agc_svg_for_dark_bg(svg: str) -> str:
    """Style all-guitar-chords SVGs for the dark popover UI."""
    out = svg.replace("fill='#e1dce2'", "fill='#243047'")
    out = _recolor_agc_finger_shapes(out)
    out = _style_agc_mute_markers(out)
    out = out.replace("stroke='black'", "stroke='#94a3b8'")
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
            f"<text x='{cx}' y='{cy}' font-size='14' font-family='Heebo' fill='black' "
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
