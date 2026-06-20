import unittest
from pathlib import Path

from services.agc_chords import adapt_agc_svg_for_dark_bg, agc_svg_url
from services.chord_suffixes import (
    CHORD_SUFFIXES,
    SUFFIX_TO_AGC,
    SUFFIX_TO_CANONICAL,
    suffix_fallback_chain,
)

FIXTURES = Path(__file__).parent / "fixtures"
CORE_FAMILIES = {"major", "minor", "dim", "7", "sus4"}


class ChordSuffixVocabularyTests(unittest.TestCase):
    def test_every_alias_maps_to_its_canonical(self):
        for entry in CHORD_SUFFIXES:
            for alias in entry.aliases:
                self.assertEqual(SUFFIX_TO_CANONICAL[alias], entry.canonical)

    def test_fallback_chains_terminate_at_a_core_family(self):
        for entry in CHORD_SUFFIXES:
            chain = suffix_fallback_chain(entry.canonical)
            self.assertEqual(chain[0], entry.canonical)
            self.assertIn(chain[-1], CORE_FAMILIES)

    def test_agc_url_resolves_for_mapped_suffixes(self):
        # Anything with an AGC mapping must yield a URL for a real root.
        for alias, segment in SUFFIX_TO_AGC.items():
            url = agc_svg_url(f"C{alias}")
            self.assertIsNotNone(url, f"no AGC url for C{alias!r}")
            self.assertIn(segment, url)


class AgcStylerGoldenTests(unittest.TestCase):
    def test_python_styler_matches_golden(self):
        source = (FIXTURES / "agc-sample.svg").read_text(encoding="utf-8")
        golden = (FIXTURES / "agc-sample.golden.svg").read_text(encoding="utf-8")
        # The frontend JS styler asserts byte-equality against this same golden,
        # so a match here proves the two implementations stay equivalent.
        self.assertEqual(adapt_agc_svg_for_dark_bg(source), golden)


if __name__ == "__main__":
    unittest.main()
