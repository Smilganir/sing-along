"""Canonical chord-suffix vocabulary (Python mirror).

This mirrors `frontend/src/constants/chordSuffixes.js`. Keep the two in sync;
the styler/coverage tests assert that the derived maps match expectations.

Each entry is (canonical, aliases, db, agc, intervals, parent). See the JS file
for the full field documentation.
"""

from __future__ import annotations

from typing import NamedTuple


class SuffixEntry(NamedTuple):
    canonical: str
    aliases: tuple[str, ...]
    db: str | None
    agc: str | None
    intervals: tuple[int, ...]
    parent: str | None


CHORD_SUFFIXES: tuple[SuffixEntry, ...] = (
    # Triads
    SuffixEntry("major", ("", "maj", "M", "major"), "major", "major", (0, 4, 7), None),
    SuffixEntry("minor", ("m", "min", "minor"), "minor", "minor", (0, 3, 7), None),
    SuffixEntry("dim", ("dim",), "dim", "dim", (0, 3, 6), "minor"),
    SuffixEntry("aug", ("aug",), "aug", "aug", (0, 4, 8), "major"),
    SuffixEntry("sus2", ("sus2",), "sus2", "sus2", (0, 2, 7), "major"),
    SuffixEntry("sus4", ("sus4", "sus"), "sus4", "sus4", (0, 5, 7), "major"),
    # Sixths
    SuffixEntry("6", ("6",), "6", "6", (0, 4, 7, 9), "major"),
    SuffixEntry("m6", ("m6", "min6"), "m6", "m6", (0, 3, 7, 9), "minor"),
    # Sevenths
    SuffixEntry("7", ("7", "dom7"), "7", "7", (0, 4, 7, 10), "major"),
    SuffixEntry("maj7", ("maj7", "M7", "major7"), "maj7", "maj7", (0, 4, 7, 11), "major"),
    SuffixEntry("m7", ("m7", "min7", "minor7"), "m7", "m7", (0, 3, 7, 10), "minor"),
    SuffixEntry("m7b5", ("m7b5", "min7b5", "minor7b5"), "m7b5", "m7b5", (0, 3, 6, 10), "dim"),
    SuffixEntry("mmaj7", ("mmaj7", "mM7", "minmaj7"), "mmaj7", None, (0, 3, 7, 11), "m7"),
    SuffixEntry("dim7", ("dim7",), "dim7", "dim7", (0, 3, 6, 9), "dim"),
    # Altered dominants
    SuffixEntry("7b5", ("7b5",), "7b5", "7b5", (0, 4, 6, 10), "7"),
    SuffixEntry("7#5", ("7#5", "aug7", "7+5"), "aug7", None, (0, 4, 8, 10), "7"),
    SuffixEntry("7b9", ("7b9",), "7b9", "7b9", (0, 4, 7, 10, 13), "7"),
    SuffixEntry("7#9", ("7#9",), "7#9", None, (0, 4, 7, 10, 15), "7"),
    SuffixEntry("7sus4", ("7sus4",), "7sus4", "7sus4", (0, 5, 7, 10), "sus4"),
    SuffixEntry("m7#5", ("m7#5",), None, None, (0, 3, 8, 10), "m7"),
    SuffixEntry("maj7b5", ("maj7b5",), "maj7b5", None, (0, 4, 6, 11), "maj7"),
    SuffixEntry("maj7#5", ("maj7#5",), "maj7#5", None, (0, 4, 8, 11), "maj7"),
    # Ninths
    SuffixEntry("9", ("9",), "9", "9", (0, 4, 7, 10, 14), "7"),
    SuffixEntry("m9", ("m9", "min9"), "m9", "m9", (0, 3, 7, 10, 14), "m7"),
    SuffixEntry("maj9", ("maj9", "M9"), "maj9", None, (0, 4, 7, 11, 14), "maj7"),
    # Elevenths
    SuffixEntry("11", ("11",), "11", "11", (0, 7, 10, 14, 17), "9"),
    SuffixEntry("m11", ("m11", "min11"), "m11", "m11", (0, 3, 7, 10, 14, 17), "m9"),
    SuffixEntry("maj11", ("maj11", "M11"), "maj11", None, (0, 4, 7, 11, 14, 17), "maj9"),
    # Thirteenths
    SuffixEntry("13", ("13",), "13", "13", (0, 4, 7, 10, 14, 21), "9"),
    SuffixEntry("m13", ("m13", "min13"), None, None, (0, 3, 7, 10, 14, 21), "m9"),
    SuffixEntry("maj13", ("maj13", "M13"), "maj13", None, (0, 4, 7, 11, 14, 21), "maj9"),
    # Added tones
    SuffixEntry("add9", ("add9",), "add9", "add9", (0, 4, 7, 14), "major"),
    SuffixEntry("add2", ("add2",), None, None, (0, 2, 4, 7), "major"),
    SuffixEntry("add4", ("add4",), None, None, (0, 4, 5, 7), "major"),
    SuffixEntry("add11", ("add11",), "add11", None, (0, 4, 7, 17), "major"),
    SuffixEntry("add", ("add",), "major", "major", (0, 4, 7), "major"),
)

SUFFIX_BY_CANONICAL: dict[str, SuffixEntry] = {e.canonical: e for e in CHORD_SUFFIXES}


def _build_alias_map(field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in CHORD_SUFFIXES:
        value = getattr(entry, field)
        if value is None:
            continue
        for alias in entry.aliases:
            out.setdefault(alias, value)
    return out


SUFFIX_TO_DB = _build_alias_map("db")
SUFFIX_TO_AGC = _build_alias_map("agc")


def _build_canonical_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in CHORD_SUFFIXES:
        for alias in entry.aliases:
            out.setdefault(alias, entry.canonical)
    return out


SUFFIX_TO_CANONICAL = _build_canonical_map()


def suffix_fallback_chain(canonical: str) -> list[str]:
    """Ordered simplification chain from `canonical` down to its core triad."""
    chain: list[str] = []
    current: str | None = canonical
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        entry = SUFFIX_BY_CANONICAL.get(current)
        current = entry.parent if entry else None
    return chain
