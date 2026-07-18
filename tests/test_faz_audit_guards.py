"""
Faz audit: 3 küçük guard/test.
1. Polish safety: English reimport (operatik→operatic) reject edilsin.
2. Artifact/Turkic leak: skelet→iskelet, partladylan flag, evett→evet.
3. Idiom validator: come in right at X → girmek flaglensin.
"""
import unittest
import hybrid_translate as ht


class PolishEnglishReimportTest(unittest.TestCase):
    def test_rejects_operatic_reimport(self):
        ok, reason = ht.validate_polish_candidate(
            "Ben operatik soprano'yum.",
            "Ben operatic soprano'yum.",
            source_text="I am an operatic soprano.",
        )
        self.assertFalse(ok)
        self.assertIn("english_reimport", reason)

    def test_allows_unchanged_turkish(self):
        ok, reason = ht.validate_polish_candidate(
            "Ben operatik soprano'yum.",
            "Ben operatik soprano'yum.",
            source_text="I am an operatic soprano.",
        )
        self.assertTrue(ok)

    def test_allows_legitimate_turkish_polish(self):
        ok, reason = ht.validate_polish_candidate(
            "O bir şarkıcı.",
            "O bir opera şarkıcısı.",
            source_text="She is a singer.",
        )
        self.assertTrue(ok)

    def test_no_false_positive_turkish_ascii(self):
        ok, reason = ht.validate_polish_candidate(
            "Robot hareket ediyor.",
            "Robot hızlı hareket ediyor.",
            source_text="The robot moves quickly.",
        )
        self.assertTrue(ok)


class ArtifactTurkicLeakTest(unittest.TestCase):
    def test_skelet_fixed_to_iskelet(self):
        text, n = ht._apply_local_fixes("Bu bir skelet.")
        self.assertEqual(text, "Bu bir iskelet.")
        self.assertGreater(n, 0)

    def test_skeleti_fixed_to_iskeleti(self):
        text, n = ht._apply_local_fixes("skeleti gördüm")
        self.assertEqual(text, "iskeleti gördüm")

    def test_skelette_fixed_to_iskelette(self):
        text, n = ht._apply_local_fixes("skelette")
        self.assertEqual(text, "iskelette")

    def test_evett_fixed_to_evet(self):
        text, n = ht._apply_local_fixes("evett")
        self.assertEqual(text, "evet")

    def test_evett_lowercase(self):
        text, n = ht._apply_local_fixes("EVETT")
        self.assertEqual(text, "evet")

    def test_partladylan_flagged_as_turkic(self):
        self.assertTrue(ht.has_non_turkish_target_leak("partladylan bir skelet"))

    def test_partladylan_with_suffix(self):
        self.assertTrue(ht.has_non_turkish_target_leak("partladylanyň"))

    def test_clean_iskelet_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("Bu bir iskelet."))

    def test_evet_not_affected_by_fix(self):
        text, n = ht._apply_local_fixes("evet")
        self.assertEqual(text, "evet")
        self.assertEqual(n, 0)


class IdiomComeInAtPriceTest(unittest.TestCase):
    def test_come_in_at_12_girmek_flagged(self):
        self.assertTrue(
            ht._has_idiom_come_in_at_price(
                "I would have to come in right at 12 on this one.",
                "12'ye girmem gerekecek",
            )
        )

    def test_come_in_at_15_girecegim_flagged(self):
        self.assertTrue(
            ht._has_idiom_come_in_at_price(
                "I can come in at 15.",
                "15'e gireceğim",
            )
        )

    def test_normal_girmek_not_flagged(self):
        self.assertFalse(
            ht._has_idiom_come_in_at_price(
                "Please come in the door.",
                "Lütfen kapıdan gir.",
            )
        )

    def test_cikmak_not_flagged(self):
        self.assertFalse(
            ht._has_idiom_come_in_at_price(
                "I would have to come in right at 12 on this one.",
                "12'ye çıkmam gerekecek",
            )
        )

    def test_istemek_not_flagged(self):
        self.assertFalse(
            ht._has_idiom_come_in_at_price(
                "I would have to come in at 12 on this one.",
                "12 istemem gerekecek",
            )
        )

    def test_run_validators_includes_idiom_flag(self):
        source = "I would have to come in right at 12 on this one."
        # Simulate cue + tr_block
        class FakeCue:
            index = 1
            text = source
        tr_blocks = [("1", "00:00:01,000 --> 00:00:04,000", "12'ye girmem gerekecek")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "come_in_at_price" in r]
        self.assertEqual(len(reasons), 1)


if __name__ == "__main__":
    unittest.main()
