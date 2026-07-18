"""Tests for Solar Worship guards: religion/Egypt/zodiac/Virgo local fixes, first-person intent shift, neighbor semantic repeat."""
import unittest
import hybrid_translate as ht


class SolarLocalFixesTest(unittest.TestCase):
    """Fix 1: _LOCAL_FIXES for religion, Egypt, zodiac, Virgo."""

    def test_religion_larina(self):
        fixed, n = ht._apply_local_fixes("religion'larına")
        self.assertEqual(fixed, "dinlerine")

    def test_religion_larini(self):
        fixed, n = ht._apply_local_fixes("religion'larını")
        self.assertEqual(fixed, "dinlerini")

    def test_religion_lari(self):
        fixed, n = ht._apply_local_fixes("religion'ları")
        self.assertEqual(fixed, "dinleri")

    def test_religion_u(self):
        fixed, n = ht._apply_local_fixes("religion'u")
        self.assertEqual(fixed, "dini")

    def test_religion_bare(self):
        fixed, n = ht._apply_local_fixes("religion")
        self.assertEqual(fixed, "din")

    def test_religions(self):
        fixed, n = ht._apply_local_fixes("religions")
        self.assertEqual(fixed, "dinler")

    def test_religion_curly_apostrophe(self):
        fixed, n = ht._apply_local_fixes("religion\u2019larına")
        self.assertEqual(fixed, "dinlerine")

    def test_egypt_e(self):
        fixed, n = ht._apply_local_fixes("Egypt'e")
        self.assertEqual(fixed, "Mısır'a")

    def test_egypt_curly_apostrophe(self):
        fixed, n = ht._apply_local_fixes("Egypt\u2019e")
        self.assertEqual(fixed, "Mısır'a")

    def test_egypt_bare(self):
        fixed, n = ht._apply_local_fixes("Egypt")
        self.assertEqual(fixed, "Mısır")

    def test_zodiac_in(self):
        fixed, n = ht._apply_local_fixes("zodiac'ın")
        self.assertEqual(fixed, "zodyağın")

    def test_zodiac_in_curly(self):
        fixed, n = ht._apply_local_fixes("zodiac\u2019ın")
        self.assertEqual(fixed, "zodyağın")

    def test_zodiac_ta(self):
        fixed, n = ht._apply_local_fixes("zodiac'ta")
        self.assertEqual(fixed, "zodyakta")

    def test_zodiac_curly_ta(self):
        fixed, n = ht._apply_local_fixes("zodiac\u2019ta")
        self.assertEqual(fixed, "zodyakta")

    def test_zodiac_bare(self):
        fixed, n = ht._apply_local_fixes("zodiac")
        self.assertEqual(fixed, "zodyak")

    def test_virgo_dur_bakire(self):
        fixed, n = ht._apply_local_fixes("Virgo'dur, Bakire")
        self.assertEqual(fixed, "Başak'tır, Bakire")

    def test_virgo_curly_dur_bakire(self):
        fixed, n = ht._apply_local_fixes("Virgo\u2019dur, Bakire")
        self.assertEqual(fixed, "Başak'tır, Bakire")

    def test_virgo_comma_the_virgin(self):
        fixed, n = ht._apply_local_fixes("Virgo, the Virgin")
        self.assertEqual(fixed, "Başak, Bakire")

    def test_virgo_comma_bakire(self):
        fixed, n = ht._apply_local_fixes("Virgo, Bakire")
        self.assertEqual(fixed, "Başak, Bakire")

    def test_virgo_bare(self):
        fixed, n = ht._apply_local_fixes("Virgo")
        self.assertEqual(fixed, "Başak")


class ResidualDetectionSolarTest(unittest.TestCase):
    """Fix 1b: _EN_LEFTOVER flags religion/Egypt/zodiac/Virgo."""

    def test_religion_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("religion"))

    def test_egypt_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("Egypt"))

    def test_zodiac_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("zodiac"))

    def test_virgo_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("Virgo"))


class FirstPersonIntentShiftTest(unittest.TestCase):
    """Fix 2: validate_polish_candidate rejects first-person → plural shift."""

    def test_rejects_konusacagiz_shift(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu bölümde biraz S-U-N...",
            "Bu bölümde biraz S-U-N...",
            source_text="I'd like to talk a little about S-U-N...",
        )
        self.assertTrue(ok, f"baseline should pass: {reason}")

    def test_rejects_shift_to_konusacagiz(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu bölümde konuşmak istiyorum",
            "tüm hikâyede zodyakta konuşacağız",
            source_text="I'd like to talk about the whole story",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "first_person_intent_shift")

    def test_no_source_flag(self):
        """Without source, the check should not trigger."""
        ok, reason = ht.validate_polish_candidate(
            "Bu bölümde konuşmak istiyorum",
            "biraz konuşmak istiyorum",
            source_text="",
        )
        self.assertTrue(ok, f"no source should pass: {reason}")

    def test_preserves_first_person(self):
        """Candidate that keeps first person should pass."""
        ok, reason = ht.validate_polish_candidate(
            "Bu bölümde konuşmak istiyorum",
            "bu bölümde biraz konuşmak istiyorum",
            source_text="I'd like to talk a little",
        )
        self.assertTrue(ok, f"should pass: {reason}")

    def test_no_intent_in_source(self):
        """Source without intent keywords should not trigger."""
        ok, reason = ht.validate_polish_candidate(
            "bir şey oldu",
            "bir şey oldu",
            source_text="something happened",
        )
        self.assertTrue(ok)


class NeighborSemanticRepeatTest(unittest.TestCase):
    """Fix 3: _has_neighbor_semantic_repeat + run_validators."""

    def _make_blocks(self, text1: str, text2: str):
        return [("532", "00:10:00 --> 00:10:05", text1),
                ("533", "00:10:06 --> 00:10:11", text2)]

    def test_yineleme_tekrarlanma_nedeni_detected(self):
        blocks = self._make_blocks(
            "İşte bu temaların sürekli yinelemesinin nedeni",
            "sürekli tekrarlanmasının nedeni",
        )
        self.assertTrue(ht._has_neighbor_semantic_repeat(blocks, 0))

    def test_different_meaning_not_flagged(self):
        blocks = self._make_blocks(
            "Bu çok önemli bir konudur",
            "bir sonraki bölümde devam edecek",
        )
        self.assertFalse(ht._has_neighbor_semantic_repeat(blocks, 0))

    def test_only_one_nedeni_not_flagged(self):
        blocks = self._make_blocks(
            "sürekli yinelemesinin nedeni budur",
            "farklı bir konu",
        )
        self.assertFalse(ht._has_neighbor_semantic_repeat(blocks, 0))

    def test_run_validators_flowers_repeat(self):
        tr_blocks = self._make_blocks(
            "İşte bu temaların sürekli yinelemesinin nedeni",
            "sürekli tekrarlanmasının nedeni",
        )
        results = ht.run_validators(tr_blocks)
        reasons_strs = [r[3] for r in results]
        self.assertTrue(
            any("NEIGHBOR_SEMANTIC_REPEAT" in r for r in reasons_strs),
            f"should flag: {reasons_strs}",
        )

    def test_hata_block_skipped(self):
        blocks = [("532", "00:10:00 --> 00:10:05", "[HATA]"),
                  ("533", "00:10:06 --> 00:10:11", "sürekli tekrarlanmasının nedeni")]
        self.assertFalse(ht._has_neighbor_semantic_repeat(blocks, 0))


if __name__ == "__main__":
    unittest.main()
