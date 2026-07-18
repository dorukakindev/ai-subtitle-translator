"""Tests for Turkic/Somali/Arabic residue guards, English residue, polish guards, and conjunction fragment/spill."""
import unittest
import hybrid_translate as ht
from unittest.mock import MagicMock, patch


class ApplyLocalFixesTest(unittest.TestCase):
    """Fix 1+2: Turkic/source-language + English residue."""

    def test_dawut_patsa(self):
        fixed, n = ht._apply_local_fixes("Dawut patşa'nın kayıp")
        self.assertIn("Kral Davud'un", fixed)
        self.assertGreaterEqual(n, 1)

    def test_dawut_bare(self):
        fixed, n = ht._apply_local_fixes("Dawut dedi ki")
        self.assertEqual(fixed, "Davud dedi ki")
        self.assertGreaterEqual(n, 1)

    def test_äht_sandygy(self):
        fixed, n = ht._apply_local_fixes("Äht sandygy'nu buldular")
        self.assertIn("Ahit Sandığı'nı", fixed)
        self.assertGreaterEqual(n, 1)

    def test_äht_sandygy_bare(self):
        fixed, n = ht._apply_local_fixes("Äht sandygy")
        self.assertEqual(fixed.strip(), "Ahit Sandığı")

    def test_sandygy_standalone(self):
        fixed, n = ht._apply_local_fixes("kayıp sandygy")
        self.assertIn("Sandığı", fixed)

    def test_sandygyny(self):
        fixed, n = ht._apply_local_fixes("sandygyny buldular")
        self.assertIn("Sandığı'nı", fixed)

    def test_iýerusalim(self):
        fixed, n = ht._apply_local_fixes("Iýerusalim'e gitti")
        self.assertEqual(fixed, "Kudüs'e gitti")

    def test_iýerusalim_bare(self):
        fixed, n = ht._apply_local_fixes("Iýerusalim")
        self.assertEqual(fixed.strip(), "Kudüs")

    def test_ysraýyl(self):
        fixed, n = ht._apply_local_fixes("Ysraýyl'da yasiyor")
        self.assertIn("İsrail'de", fixed)

    def test_ysraýyl_bare(self):
        fixed, n = ht._apply_local_fixes("Ysraýyl")
        self.assertEqual(fixed.strip(), "İsrail")

    def test_ybadathane(self):
        fixed, n = ht._apply_local_fixes("Yahudi ybadathanesinin")
        self.assertIn("tapınağının", fixed)

    def test_ybadathaneler(self):
        fixed, n = ht._apply_local_fixes("ybadathaneler")
        self.assertEqual(fixed.strip(), "tapınaklar")

    def test_ybadathane_bare(self):
        fixed, n = ht._apply_local_fixes("ybadathane")
        self.assertEqual(fixed.strip(), "tapınak")

    def test_solomon_patsa(self):
        fixed, n = ht._apply_local_fixes("Solomon patşa")
        self.assertEqual(fixed, "Kral Solomon")

    def test_king_david(self):
        fixed, n = ht._apply_local_fixes("King David")
        self.assertEqual(fixed, "Kral Davud")

    def test_king_solomon(self):
        fixed, n = ht._apply_local_fixes("King Solomon")
        self.assertEqual(fixed, "Kral Solomon")

    def test_king_james_untouched(self):
        """King James must NOT be altered."""
        fixed, n = ht._apply_local_fixes("King James version")
        self.assertEqual(fixed, "King James version")

    def test_world_freemasonry(self):
        fixed, n = ht._apply_local_fixes("World Freemasonry")
        self.assertEqual(fixed, "Dünya Masonluğu")

    def test_temple_institute(self):
        fixed, n = ht._apply_local_fixes("Temple Institute")
        self.assertEqual(fixed, "Tapınak Enstitüsü")

    def test_full_sentence(self):
        src = "Dawut patşa'nın kayıp Äht sandygy'nu Iýerusalim'de buldular"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("Kral Davud'un", fixed)
        self.assertIn("Ahit Sandığı'nı", fixed)
        self.assertIn("Kudüs'te", fixed)

    # ── Curly-apostrophe variants (gerçek SRT'de görülen ' = U+2019) ──
    CUR_APOS = "\u2019"

    def test_ysraýyl_curly_apostrophe_da(self):
        src = f"Ysraýyl{self.CUR_APOS}da"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("İsrail'de", fixed)

    def test_ysraýyl_curly_apostrophe_in(self):
        src = f"Ysraýyl{self.CUR_APOS}in"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("İsrail'in", fixed)

    def test_iýerusalim_curly_apostrophe_de(self):
        src = f"Iýerusalim{self.CUR_APOS}de"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("Kudüs'te", fixed)

    def test_iýerusalim_curly_apostrophe_e(self):
        src = f"Iýerusalim{self.CUR_APOS}e"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("Kudüs'e", fixed)

    def test_äht_sandygy_curly_apostrophe_nu(self):
        src = f"Äht sandygy{self.CUR_APOS}nu"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("Ahit Sandığı'nı", fixed)

    def test_dawut_patsa_curly_apostrophe_nin(self):
        src = f"Dawut patşa{self.CUR_APOS}nın kayıp"
        fixed, n = ht._apply_local_fixes(src)
        self.assertIn("Kral Davud'un", fixed)


class ResidualDetectionTest(unittest.TestCase):
    """Ensure the overflow regexes flag the raw residues."""

    def test_dawut_in_source_leftover(self):
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("Dawut"))

    def test_äht_in_turkic_drift(self):
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("Äht sandygy"))

    def test_sandygy_in_turkic_drift(self):
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("sandygy"))

    def test_iýerusalim_in_turkic_drift(self):
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("Iýerusalim"))

    def test_ysraýyl_in_turkic_drift(self):
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("Ysraýyl"))

    def test_ybadathane_in_turkic_drift(self):
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("ybadathane"))

    def test_freemasonry_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("World Freemasonry"))

    def test_temple_institute_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("Temple Institute"))


class EnglishArticleReimportTest(unittest.TestCase):
    """Fix 3: validate_polish_candidate english_article_reimport."""

    def test_article_reimport_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu bir tür saflıktı",
            "Bu bir tür a saflıktı",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "english_article_reimport")

    def test_no_false_positive_plan_a(self):
        """'A planı' (uppercase A, letter name) must NOT be flagged."""
        ok, reason = ht.validate_polish_candidate(
            "B planı",
            "A planı",
        )
        self.assertTrue(ok, f"should accept but got {reason}")

    def test_unchanged_passes(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu bir tür saflıktı",
            "Bu bir tür saflıktı",
        )
        self.assertTrue(ok)

    def test_article_already_in_old(self):
        """If old already has 'a', reimport is not an issue."""
        ok, reason = ht.validate_polish_candidate(
            "bu bir a seçenekti",
            "bu bir a seçenekti",
        )
        self.assertTrue(ok)


class GreekWordExplanationLossTest(unittest.TestCase):
    """Fix 4: validate_polish_candidate + run_validators."""

    def test_polish_rejects_loss(self):
        ok, reason = ht.validate_polish_candidate(
            "aion Yunanca bir kelimedir, yani",
            "Bu, bir aion sonu; aion",
            source_text="aion, a Greek word which",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "greek_word_loss")

    def test_polish_accepts_with_explanation(self):
        ok, reason = ht.validate_polish_candidate(
            "aion gelir",
            "aion yunanca gelir",
            source_text="aion, a Greek word which",
        )
        self.assertTrue(ok, f"should accept but got {reason}")

    def test_no_greek_word_no_flag(self):
        ok, reason = ht.validate_polish_candidate(
            "merhaba",
            "merhaba",
            source_text="normal source",
        )
        self.assertTrue(ok)

    def test_run_validators_flowers_greek_loss(self):
        """run_validators should flag GREEK_WORD_EXPLANATION_LOSS."""
        tr_blocks = [("713", "00:10:00 --> 00:10:05", "Bu, bir aion sonu; aion")]
        cues = [type("Cue", (), {"index": 713, "text": "aion, a Greek word which"})()]
        results = ht.run_validators(tr_blocks, cues=cues)
        reasons_strs = [r[3] for r in results]
        self.assertTrue(
            any("GREEK_WORD_EXPLANATION_LOSS" in r for r in reasons_strs),
            f"should flag Greek word loss: {reasons_strs}",
        )

    def test_run_validators_not_flag_with_explanation(self):
        tr_blocks = [("713", "00:10:00 --> 00:10:05", "aion Yunanca bir kelimedir")]
        cues = [type("Cue", (), {"index": 713, "text": "aion, a Greek word which"})()]
        results = ht.run_validators(tr_blocks, cues=cues)
        reasons_strs = [r[3] for r in results]
        self.assertFalse(
            any("GREEK_WORD_EXPLANATION_LOSS" in r for r in reasons_strs),
            f"should NOT flag: {reasons_strs}",
        )


class ConjunctionFragmentSpillTest(unittest.TestCase):
    """Fix 5: _has_conjunction_fragment_spill."""

    def _make_blocks(self, text1: str, text2: str):
        return [("316", "00:10:00 --> 00:10:05", text1),
                ("317", "00:10:06 --> 00:10:11", text2)]

    def test_çünkü_fragment_spill_detected(self):
        blocks = self._make_blocks("çünkü güneş,", "getirmeye çalışmışlardı")
        self.assertTrue(ht._has_conjunction_fragment_spill(blocks, 0))

    def test_çünkü_two_words(self):
        blocks = self._make_blocks("çünkü güneş çok", "önemlidir")
        self.assertTrue(ht._has_conjunction_fragment_spill(blocks, 0))

    def test_three_words_after_çünkü(self):
        blocks = self._make_blocks("çünkü güneş çok önemli", "World Freemasonry'de")
        self.assertTrue(ht._has_conjunction_fragment_spill(blocks, 0))

    def test_complete_sentence_not_flagged(self):
        """Text ending with a complete thought after çünkü should NOT be flagged."""
        blocks = self._make_blocks(
            "çünkü güneş çok önemli bir unsurdur",
            "devamı",
        )
        self.assertFalse(ht._has_conjunction_fragment_spill(blocks, 0))

    def test_no_çünkü_not_flagged(self):
        blocks = self._make_blocks("sadece bir cümle", "devamı")
        self.assertFalse(ht._has_conjunction_fragment_spill(blocks, 0))

    def test_run_validators_flowers_spill(self):
        tr_blocks = self._make_blocks("çünkü güneş,", "getirmeye çalışmışlardı")
        results = ht.run_validators(tr_blocks)
        reasons_strs = [r[3] for r in results]
        self.assertTrue(
            any("CONJUNCTION_FRAGMENT_SPILL" in r for r in reasons_strs),
            f"should flag CONJUNCTION_FRAGMENT_SPILL: {reasons_strs}",
        )


if __name__ == "__main__":
    unittest.main()
