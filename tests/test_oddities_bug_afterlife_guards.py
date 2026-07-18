"""
S04E11 "A Bug's Afterlife" verified quality fixes.

1. Oddities title stray apostrophe: "ODDITIES"'in → "ODDITIES"in
2. Both:/BOTH: speaker label → İkisi:
3. Oddities intro literal flow: bilim haline getirmek → fix + regression guard
4. Vajina ki... → Vajina değil...
5. cassowary → kasuar
6. Obscura grandma exception: Tabii, anneannen... → ...değilse o ayrı.
"""

import unittest

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]
_APPLY_TUPLE = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)
_VALIDATE = lambda o, n: __import__("hybrid_translate").validate_polish_candidate(o, n)


# ── 1. Oddities title stray apostrophe ─────────────────────────────────

class TitleApostropheTest(unittest.TestCase):
    def test_removes_stray_apostrophe(self):
        result = _APPLY('"ODDITIES"\'in tuhaf dünyasına')
        self.assertNotIn("''", result)
        self.assertNotIn("'\"", result)
        self.assertIn('"ODDITIES"in', result)

    def test_removes_double_apostrophe(self):
        result = _APPLY('"ODDITIES"\'in')
        self.assertNotIn("'", result)

    def test_removes_curly_apostrophe(self):
        result = _APPLY('"ODDITIES"\u2019in')
        self.assertIn('"ODDITIES"in', result)

    def test_keeps_normal_title(self):
        result = _APPLY('"ODDITIES"in tuhaf dünyasına hoş geldiniz')
        self.assertIn('"ODDITIES"in tuhaf dünyasına', result)
        self.assertIn('hoş geldiniz', result)
        self.assertNotIn("'", result)


# ── 2. Both:/BOTH: speaker label ──────────────────────────────────────

class BothSpeakerLabelTest(unittest.TestCase):
    def test_both_colon_replaced(self):
        result = _APPLY("Both: Hayatımızı tuhaf şeyler toplayarak geçirdik.")
        self.assertTrue(result.startswith("İkisi:"), result)

    def test_both_uppercase_replaced(self):
        result = _APPLY("BOTH: Haydi başlayalım.")
        self.assertTrue(result.startswith("İkisi:"), result)

    def test_inline_both_not_touched(self):
        result = _APPLY("Bu şey both anlama geliyor.")
        self.assertIn("both", result)

    def test_both_label_with_oddities_context(self):
        result = _APPLY("Both: Bu işi bilim haline getirmek için ömrümüzü toplama, alım-satım, araştırıp seçerek geçirdik.")
        self.assertTrue(result.startswith("İkisi:"), result)


# ── 3. Oddities intro literal flow ────────────────────────────────────

class IntroLiteralFlowTest(unittest.TestCase):
    def test_bilim_haline_getirmek_fixed(self):
        result = _APPLY("Bu işi bilim haline getirmek için ömrümüzü toplama, alım-satım, araştırıp seçerek geçirdik.")
        self.assertNotIn("bilim haline", result)

    def test_bilim_haline_getirdik_fixed(self):
        result = _APPLY("ömrümüzü bilim haline getirdik")
        self.assertNotIn("bilim haline", result)

    def test_polish_guard_rejects_bilim_haline_getirmek(self):
        ok, reason = _VALIDATE("bu işte iyice ustalaştık", "bilim haline getirmek için ömrümüzü harcadık")
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_polish_guard_rejects_bilim_haline_getirdik(self):
        ok, reason = _VALIDATE("tekniğini oturttuk", "işi bilim haline getirdik")
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_polish_guard_allows_normal(self):
        ok, _ = _VALIDATE("ustalaştık", "iyice ustalaştık")
        self.assertTrue(ok)


# ── 4. Vajina ki... → Vajina değil... ─────────────────────────────────

class VaginaFixTest(unittest.TestCase):
    def test_vajina_ki_fixed(self):
        result = _APPLY("Vajina ki... şey, üretradan bahsediyoruz.")
        self.assertNotIn("Vajina ki", result)
        self.assertIn("Vajina değil", result)

    def test_vajina_ki_period_fixed(self):
        result = _APPLY("Vajina ki... şey, üretradan bahsediyoruz")
        self.assertIn("Vajina değil", result)


# ── 5. cassowary → kasuar ────────────────────────────────────────────

class CassowaryFixTest(unittest.TestCase):
    def test_kassovar_to_kasuar(self):
        result = _APPLY("kassovar")
        self.assertEqual(result, "kasuar")

    def test_kassovar_kuşu_to_kasuar(self):
        result = _APPLY("kassovar kuşu")
        self.assertEqual(result, "kasuar kuşu")

    def test_kassovar_hançerleri_to_kasuar(self):
        result = _APPLY("kassovar hançerleri")
        self.assertEqual(result, "kasuar hançerleri")

    def test_cassowary_in_en_leftover(self):
        import hybrid_translate as ht
        self.assertTrue(ht._EN_LEFTOVER.search("cassowary"))
        self.assertTrue(ht._EN_LEFTOVER.search("CASSOWARY"))


# ── 6. Obscura grandma exception ────────────────────────────────────

class GrandmaExceptionTest(unittest.TestCase):
    def test_kacik_degilse_fixed(self):
        result = _APPLY("Tabii, anneannen biraz ka\u00e7\u0131k de\u011filse.")
        self.assertNotIn("Tabii,", result)
        self.assertIn("Tabii anneannen", result)
        self.assertIn("o ayr\u0131", result)

    def test_kacik_degilse_no_period_fixed(self):
        result = _APPLY("Tabii, anneannen biraz ka\u00e7\u0131k de\u011filse")
        self.assertIn("o ayr\u0131", result)

    def test_catlak_degilse_fixed(self):
        result = _APPLY("Tabii, anneannen biraz \u00e7atlak de\u011filse.")
        self.assertIn("o ayr\u0131", result)

    def test_anneanneniz_variant_fixed(self):
        result = _APPLY("Tabii, anneanneniz biraz ka\u00e7\u0131k de\u011filse.")
        self.assertIn("o ayr\u0131", result)


if __name__ == "__main__":
    unittest.main()
