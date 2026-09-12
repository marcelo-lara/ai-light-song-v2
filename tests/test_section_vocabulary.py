from __future__ import annotations

import unittest

from analyzer.section_vocabulary import normalize_allin1_label, normalize_human_label


class NormalizeHumanLabelTests(unittest.TestCase):
    def test_canonical_term_passes_through(self) -> None:
        self.assertEqual(normalize_human_label("Verse"), "Verse")

    def test_fixes_case_and_whitespace(self) -> None:
        self.assertEqual(normalize_human_label("  breakdown "), "Breakdown")

    def test_instrumental_alias_maps_to_main(self) -> None:
        # docs/segments-vocabulary.md has no "Instrumental" entry; this is the
        # same target/rationale as allin1's inst/solo -> Main mapping.
        self.assertEqual(normalize_human_label("Instrumental"), "Main")
        self.assertEqual(normalize_human_label("instrumental"), "Main")
        self.assertEqual(normalize_human_label("  Instrumental  "), "Main")

    def test_unknown_label_passes_through_stripped_unchanged(self) -> None:
        # No silent fallback: a genuinely novel human label is not overwritten.
        self.assertEqual(normalize_human_label(" Freestyle Rap "), "Freestyle Rap")


class NormalizeAllin1LabelTests(unittest.TestCase):
    def test_none_passes_through(self) -> None:
        self.assertIsNone(normalize_allin1_label(None))

    def test_known_token_maps(self) -> None:
        self.assertEqual(normalize_allin1_label("inst"), "Main")
        self.assertEqual(normalize_allin1_label("solo"), "Main")
        self.assertEqual(normalize_allin1_label("chorus"), "Chorus")

    def test_unknown_token_raises(self) -> None:
        with self.assertRaises(ValueError):
            normalize_allin1_label("not-a-real-token")


if __name__ == "__main__":
    unittest.main()
