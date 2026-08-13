import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class SourceEnglishOverlapTest(unittest.TestCase):
    def test_real_lowercase_residues_are_flagged(self):
        cases = [
            ("It's the police.", "Bu, the police."),
            ("They returned to the capital.", "Görünüşe göre the capital çevresine döndüler."),
            ("Use the public phone box outside.", "Dışarıdaki public phone box kullan."),
        ]
        for source, translation in cases:
            with self.subTest(translation=translation):
                self.assertTrue(ht.has_source_english_overlap(source, translation))
                self.assertTrue(gui._is_untranslated(source, translation))

    def test_intentional_names_and_borrowed_phrases_are_not_flagged(self):
        cases = [
            ("According to The Princeton Review,", "The Princeton Review'a göre,"),
            ("Welcome to the House of Five Leaves.", "House of Five Leaves'a hoş geldin."),
            ("They played rock and roll.", "Bütün gece rock and roll çaldılar."),
            ("The unit is called westage.", "Bu birime westage denir."),
        ]
        for source, translation in cases:
            with self.subTest(translation=translation):
                self.assertFalse(ht.has_source_english_overlap(source, translation))

    def test_quoted_song_titles_are_not_flagged_as_english_residue(self):
        source = (
            'One seven-inch single - "I\'m the Leader of the Gang," brackets, '
            '"I Am" by Gary Glitter.'
        )
        translation = (
            'Bir tane yedi inçlik plak: Gary Glitter\'dan '
            '"I\'m the Leader of the Gang", parantez içinde, "I Am".'
        )
        self.assertFalse(ht.has_source_english_overlap(source, translation))
        self.assertFalse(gui._is_untranslated(
            source, translation, source_language="English"))

    def test_preserved_foreign_titles_are_not_flagged_as_english_residue(self):
        cases = [
            (
                'You\'re wrong, "La tabernera del puerto" is from Sorozábal.',
                'Yanılıyorsun, "La tabernera del puerto" Sorozábal\'ındır.',
            ),
            (
                'You were going to stage "El castigo es sinn fein acta" with María Guerrero.',
                'María Guerrero\'yla "El castigo es sinn fein acta"yı sahnelemeye gidiyordun.',
            ),
        ]
        for source, translation in cases:
            with self.subTest(translation=translation):
                self.assertFalse(ht.has_source_english_overlap(source, translation))
                self.assertFalse(gui._is_untranslated(
                    source, translation, source_language="English"))

    def test_quoted_ordinary_dialogue_is_still_flagged(self):
        source = 'He said, "Please come here before dinner."'
        translation = '"Please come here before dinner," dedi.'
        self.assertTrue(ht.has_source_english_overlap(source, translation))

    def test_unquoted_cocktail_titles_are_not_flagged_as_english_residue(self):
        cases = [
            (
                "For a Between the Sheets, take three different liquors.",
                "Between the Sheets için üç farklı içki alırsın.",
            ),
            (
                "A Hair of the Dog, to get you going.",
                "Seni kendine getirsin diye bir Hair of the Dog.",
            ),
        ]
        for source, translation in cases:
            with self.subTest(translation=translation):
                self.assertFalse(ht.has_source_english_overlap(source, translation))

    def test_ordinary_untranslated_phrase_beside_title_is_still_flagged(self):
        self.assertTrue(ht.has_source_english_overlap(
            "For a Between the Sheets, take three different liquors.",
            "Between the Sheets için take three different liquors.",
        ))

    def test_validator_routes_overlap_to_quality_pass(self):
        cue = SimpleNamespace(
            index=7,
            start="00:00:01,000",
            end="00:00:02,000",
            text="Use the public phone box outside.",
        )
        suspicious = ht.run_validators([
            ("7", "00:00:01,000 --> 00:00:02,000", "Dışarıdaki public phone box kullan.")
        ], cues=[cue])
        reasons = suspicious[0][3].split("|")
        self.assertIn("SOURCE_ENGLISH_OVERLAP", reasons)
        self.assertTrue(ht._is_semantic_reconciliation_reason("SOURCE_ENGLISH_OVERLAP"))

    def test_existing_language_and_turkish_flow_signals_reach_final_pass(self):
        for reason in ("EN_LEFTOVER", "BAD_TURKISH_CASE_FLOW", "TURKISH_ODDITY"):
            with self.subTest(reason=reason):
                self.assertTrue(ht._is_semantic_reconciliation_reason(reason))


class AlignmentSemanticRoutingTest(unittest.TestCase):
    def test_alignment_findings_are_sent_to_final_semantic_pass(self):
        app = gui.App.__new__(gui.App)
        app.semantic_reconcile_var = SimpleNamespace(get=lambda: True)
        app.src_var = SimpleNamespace(get=lambda: "English")
        app.tgt_var = SimpleNamespace(get=lambda: "Turkish")
        app._log = MagicMock()
        app._helper_api_key = MagicMock(return_value="k")
        app._helper_api_base_url = MagicMock(return_value=None)
        app._helper_api_model = MagicMock(return_value="m")
        app._token_callback_for_model = MagicMock(return_value=MagicMock())
        app._get_locked_terms_dict = MagicMock(return_value={})
        blocks = [
            ("245", "00:00:01,000 --> 00:00:02,000", "Bir."),
            ("247", "00:00:02,000 --> 00:00:03,000", "İki."),
            ("249", "00:00:03,000 --> 00:00:04,000", "Üç."),
        ]
        stats = {
            "clusters": 0, "suspects": 0, "proposed": 0,
            "fixed": 0, "rejected": 0, "details": [],
        }

        with patch("subtitle_translator_gui.detect_alignment_issues", return_value=[
            {"type": "outlier_cluster", "ids": ["247", "249"], "detail": "küme"}
        ]), patch("hybrid_translate.semantic_reconciliation_pass",
                  return_value=(list(blocks), stats)) as semantic:
            fixed = app._maybe_semantic_reconciliation(
                "episode.srt",
                {"245": "One.", "247": "Two.", "249": "Three."},
                blocks,
            )

        self.assertEqual(fixed, 0)
        reasons = semantic.call_args.kwargs["extra_suspect_reasons"]
        self.assertEqual(reasons["247"], {"ALIGNMENT_OUTLIER_CLUSTER"})
        self.assertEqual(reasons["249"], {"ALIGNMENT_OUTLIER_CLUSTER"})


if __name__ == "__main__":
    unittest.main()
