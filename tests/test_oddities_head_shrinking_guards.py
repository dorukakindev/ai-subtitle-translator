"""Tests for Oddities S05E07 Head Shrinking 101 guards: fa'a'aitiiti, sloth, fox/sloth consistency, head→face regression, derece köylerine."""
import unittest
import hybrid_translate as ht


class FaAitiitiLocalFixesTest(unittest.TestCase):
    """Fix 1: Samoan fa'a'aitiiti residue."""

    def test_kafa_faaitiiti(self):
        fixed, n = ht._apply_local_fixes("kafa fa'a'aitiiti")
        self.assertEqual(fixed, "küçültülmüş kafa")

    def test_kafa_curly_apostrophe(self):
        fixed, n = ht._apply_local_fixes("kafa fa\u2019a\u2019aitiiti")
        self.assertEqual(fixed, "küçültülmüş kafa")

    def test_ulu_faaitiiti(self):
        fixed, n = ht._apply_local_fixes("ulu fa'aitiiti")
        self.assertEqual(fixed, "küçültülmüş kafa")

    def test_ulu_curly_apostrophe(self):
        fixed, n = ht._apply_local_fixes("ulu fa\u2019aitiiti")
        self.assertEqual(fixed, "küçültülmüş kafa")

    def test_bare_faaitiiti(self):
        fixed, n = ht._apply_local_fixes("fa'a'aitiiti")
        self.assertEqual(fixed, "küçültülmüş")

    def test_bare_faaitiiti_short(self):
        fixed, n = ht._apply_local_fixes("fa'aitiiti")
        self.assertEqual(fixed, "küçültülmüş")

    def test_in_source_leftover(self):
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("fa'a'aitiiti"))
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("fa'aitiiti"))


class SlothLocalFixesTest(unittest.TestCase):
    """Fix 2: Sloth residue."""

    def test_slotha(self):
        fixed, n = ht._apply_local_fixes("Ryan: Slotha taşlarla")
        self.assertIn("tembel hayvanı", fixed)

    def test_sloth_apostrophe_a(self):
        fixed, n = ht._apply_local_fixes("sloth'a vurdular")
        self.assertIn("tembel hayvana", fixed)

    def test_sloth_apostrophe_u(self):
        fixed, n = ht._apply_local_fixes("sloth'u gördüm")
        self.assertIn("tembel hayvanı", fixed)

    def test_sloth_curly_apostrophe(self):
        fixed, n = ht._apply_local_fixes("sloth\u2019u gördüm")
        self.assertIn("tembel hayvanı", fixed)

    def test_sloth_bare(self):
        fixed, n = ht._apply_local_fixes("sloth")
        self.assertEqual(fixed, "tembel hayvan")

    def test_sloth_in_en_leftover(self):
        self.assertIsNotNone(ht._EN_LEFTOVER.search("sloth"))


class FoxSlothInconsistencyTest(unittest.TestCase):
    """Fix 3: tilki derisi flagged in sloth context."""

    def _make_blocks(self, text: str, neighbor: str, pos: int = 0):
        return [("1", "00:01 --> 00:04", "bu bir tembel hayvan sahnesi"),
                ("2", "00:05 --> 00:08", text),
                ("3", "00:09 --> 00:12", "başka kafa konusu")]

    def test_tilki_derisi_with_sloth_context_flowers(self):
        blocks = self._make_blocks("TİLKİ DERİSİ", None)
        blocks[2] = ("3", "00:09 --> 00:12", "tembel hayvan")
        self.assertTrue(ht._has_fox_sloth_inconsistency("TİLKİ DERİSİ", blocks, 1))

    def test_no_sloth_context_no_flag(self):
        blocks = [("1", "00:01 --> 00:04", "bu bir normal"),
                  ("2", "00:05 --> 00:08", "TİLKİ DERİSİ"),
                  ("3", "00:09 --> 00:12", "başka normal")]
        self.assertFalse(ht._has_fox_sloth_inconsistency("TİLKİ DERİSİ", blocks, 1))

    def test_local_fix_tilki_derisi(self):
        fixed, n = ht._apply_local_fixes("TİLKİ DERİSİ")
        self.assertIn("tembel hayvan derisi", fixed.lower())

    def test_run_validators_flowers_fox_sloth(self):
        tr_blocks = [("1", "00:01 --> 00:04", "tembel hayvan"),
                     ("2", "00:05 --> 00:08", "TİLKİ DERİSİ"),
                     ("3", "00:09 --> 00:12", "kafa")]
        results = ht.run_validators(tr_blocks)
        reasons_strs = [r[3] for r in results]
        self.assertTrue(
            any("FOX_SLOTH_INCONSISTENCY" in r for r in reasons_strs),
            f"should flag: {reasons_strs}",
        )


class HeadToFaceRegressionTest(unittest.TestCase):
    """Fix 4: validate_polish_candidate head→face regression."""

    def test_rejects_kafa_to_yuz(self):
        ok, reason = ht.validate_polish_candidate(
            "Benim işim için tam biçilmiş kafa bu",
            "Benim işim için tam yüz bu",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "head_to_face_regression")

    def test_accepts_unchanged_kafa(self):
        ok, reason = ht.validate_polish_candidate(
            "Benim işim için tam biçilmiş kafa bu",
            "tam biçilmiş kafa",
        )
        self.assertTrue(ok, f"should pass: {reason}")

    def test_no_biçilmiş_kafa_no_flag(self):
        """Without 'biçilmiş kafa' in old, check should not trigger."""
        ok, reason = ht.validate_polish_candidate(
            "bu kafa çok güzel",
            "bu yüz çok güzel",
        )
        self.assertTrue(ok, f"should pass: {reason}")

    def test_kafa_still_in_new_no_flag(self):
        ok, reason = ht.validate_polish_candidate(
            "biçilmiş kafa bu",
            "biçilmiş kafa",
        )
        self.assertTrue(ok)


class DereceKoylerineFlagTest(unittest.TestCase):
    """Fix 5: WEIRD_TURKISH_PHRASE for derece köylerine."""

    def test_run_validators_flowers(self):
        tr_blocks = [("1", "00:01 --> 00:04", "derece köylerine gittiler")]
        results = ht.run_validators(tr_blocks)
        reasons_strs = [r[3] for r in results]
        self.assertTrue(
            any("WEIRD_TURKISH_PHRASE:derece_köylerine" in r for r in reasons_strs),
            f"should flag: {reasons_strs}",
        )

    def test_normal_phrase_not_flagged(self):
        tr_blocks = [("1", "00:01 --> 00:04", "normal bir cümle")]
        results = ht.run_validators(tr_blocks)
        reasons_strs = [r[3] for r in results]
        self.assertFalse(
            any("WEIRD_TURKISH_PHRASE" in r for r in reasons_strs),
        )


if __name__ == "__main__":
    unittest.main()
