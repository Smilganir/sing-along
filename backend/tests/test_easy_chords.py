import unittest

from services.easy_chords import (
    apply_easy_versions,
    extract_chords,
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


if __name__ == "__main__":
    unittest.main()
