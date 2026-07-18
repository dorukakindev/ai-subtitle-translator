"""Output-driven guards from Oddities S05E04 Evan's Odd Anniversary."""

import unittest

import hybrid_translate as ht


def _apply(text: str) -> str:
    return ht._apply_local_fixes(text)[0]


class AnniversaryLocalFixTest(unittest.TestCase):
    def test_oddities_title_in_variant_fixed(self):
        raw = 'Mike: "ODDITIES"IN TUHAF DÜNYASINA\nHOŞ GELDİNİZ.'
        fixed = _apply(raw)
        self.assertIn('"ODDITIES"in tuhaf dünyasına', fixed)
        self.assertIn("hoş geldiniz", fixed)
        self.assertNotIn('"ODDITIES"IN', fixed)

    def test_obscura_big_grandma_variant_fixed(self):
        fixed = _apply("Mike: Obscura, büyükannenizin\nantikacı dükkânı değil.")
        self.assertEqual(fixed, "Mike: Obscura, anneannenizin antikacısı değil.")

    def test_grandma_crack_exception_fixed(self):
        fixed = _apply("Tabii, büyükanneniz biraz\nçatlak değilse.")
        self.assertEqual(fixed, "Tabii anneanneniz biraz çatlaksa o ayrı.")

    def test_bilime_cevirdik_fixed(self):
        fixed = _apply("iyice bir bilime çevirdik.")
        self.assertEqual(fixed, "bu işte iyice ustalaştık.")

    def test_morbid_seylere_ile_kemiklere_fixed(self):
        fixed = _apply("morbid şeylere\nile kemiklere meraklıydık,")
        self.assertEqual(fixed, "morbid şeylere ve kemiklere meraklıydık,")

    def test_antikacilikta_cagrisini_buldu_fixed(self):
        fixed = _apply("sonra sanırım o,\nantikacılıkta çağrısını buldu.")
        self.assertEqual(fixed, "sonra sanırım o,\nantikacılıkta aradığı şeyi buldu.")

    def test_birinin_o_ogrenmesi_fixed(self):
        fixed = _apply("Yani, birinin\no öğrenmesi için --")
        self.assertEqual(fixed, "Yani, birinin öğrenmesi için --")


class AnniversaryPolishGuardTest(unittest.TestCase):
    def test_fragment_expansion_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Sadece",
            "Sadece lavmanlar vardı",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "fragment_expansion_regression")

    def test_fragment_expansion_allows_unchanged(self):
        ok, reason = ht.validate_polish_candidate("Sadece", "Sadece")
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_stray_o_learning_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Yani, birinin\nöğrenmesi için --",
            "Yani, birinin\no öğrenmesi için --",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "stray_o_learning_regression")

    def test_bilime_cevirdik_regression_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "bu işte iyice ustalaştık",
            "iyice bir bilime çevirdik",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")


if __name__ == "__main__":
    unittest.main()
