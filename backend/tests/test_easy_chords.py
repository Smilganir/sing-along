import unittest

from services.easy_chords import (
    EASY_CHORDS,
    apply_easy_versions,
    extract_chords,
    simplify_chord_name,
    simplify_chords_in_sheet,
    transpose_chord,
    transpose_sheet,
)


class EasyChordsTests(unittest.TestCase):
    def test_transpose_sheet_does_not_remap_intermediate_chords(self):
        line = "Gm  Eb  Cm  B"
        self.assertEqual(transpose_sheet(line, 2), "Am  F  Dm  Db")

    def test_transpose_flat_spelling(self):
        self.assertEqual(transpose_chord("Eb", 1), "E")
        self.assertEqual(transpose_chord("Eb", 2), "F")
        self.assertEqual(transpose_chord("Bb", 2), "C")

    def test_minor_song_transposes_to_am(self):
        sample = "\n".join(
            [
                "Intro:",
                "Gm  Eb  Cm  B",
                "x2",
                "",
                "Verse 1:",
                "Eb  Gm",
                "lyric",
            ]
        )
        result = apply_easy_versions(sample, "he")
        self.assertIsNotNone(result.chordpro_easy)
        intro = result.chordpro_easy.splitlines()[1]
        self.assertEqual(extract_chords(intro)[:2], ["Am", "F"])
        verse = result.chordpro_easy.splitlines()[5]
        self.assertEqual(extract_chords(verse)[:2], ["F", "Am"])
        self.assertIn("Am", result.easy_note_en or "")

    def test_major_song_targets_c_key(self):
        sample = "B\nlyric\nE\nmore"
        result = apply_easy_versions(sample, "en")
        self.assertIsNotNone(result.chordpro_easy)
        self.assertIn("C", result.easy_note_en or "")
        self.assertEqual(extract_chords(result.chordpro_easy or "")[0], "C")

    def test_simplify_chord_name_major_sevenths_and_extensions(self):
        cases = {
            "Cmaj7": "C",
            "Fmaj7": "F",
            "C6": "C",
            "G9": "G",
            "Dsus4": "D",
            "Cm7": "Cm",
            "Bm7b5": "Bm",
            "Cdim": "Cm",
            "Caug": "C",
            "Cmaj7/E": "C/E",
        }
        for original, expected in cases.items():
            with self.subTest(chord=original):
                self.assertEqual(simplify_chord_name(original), expected)

    def test_extract_chords_includes_extended_vocabulary(self):
        line = "Am Bm7b5 Dm Fmaj7 Cmaj7 C6 G9 Dsus4 Cadd9"
        chords = extract_chords(line)
        for expected in ["Am", "Bm7b5", "Dm", "Fmaj7", "Cmaj7", "C6", "G9", "Dsus4", "Cadd9"]:
            self.assertIn(expected, chords)

    def test_am_sheet_does_not_turn_major_sevenths_minor(self):
        sample = "Am Bm Dm Fmaj7 Cmaj7 C6 G9 Dsus4 Cadd9"
        result = apply_easy_versions(sample, "en")
        self.assertIsNotNone(result.chordpro_easy)
        easy_text = result.chordpro_easy or ""
        self.assertIn("C", easy_text)
        self.assertIn("F", easy_text)
        self.assertNotIn("Cm", easy_text)
        self.assertNotIn("Fm", easy_text)
        self.assertIn("Am", result.easy_note_en or "")

    def test_key_selection_maximizes_open_chords(self):
        sample = "B  E  F#  G#m"
        work = simplify_chords_in_sheet(sample)
        result = apply_easy_versions(sample, "en")
        self.assertIsNotNone(result.chordpro_easy)
        easy_chords = extract_chords(result.chordpro_easy or "")
        simplified = {simplify_chord_name(chord) for chord in easy_chords}
        actual = len(simplified & EASY_CHORDS)

        best = 0
        for shift in range(12):
            candidate = simplify_chords_in_sheet(transpose_sheet(work, shift))
            cand_chords = {simplify_chord_name(c) for c in extract_chords(candidate)}
            best = max(best, len(cand_chords & EASY_CHORDS))

        self.assertEqual(actual, best)
        self.assertGreaterEqual(actual, 3)


if __name__ == "__main__":
    unittest.main()
