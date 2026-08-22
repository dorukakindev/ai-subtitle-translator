# -*- coding: utf-8 -*-
"""Türkçe İ ile başlayan sayı sözcükleri — dış denetim 2026-08-22, B1/B3.

str.lower() Türkçe "İ"yi "i" + U+0307 (birleşik nokta) yapar; sözlükteki
"iki" ile eşleşmez. Etkisi kaçırmakla kalmıyor, YANLIŞ DEĞER üretiyordu:
"İki bin" 2000 değil 1000, "İki yüz elli" 250 değil 150 — cümle başındaki
sayı sözcüğü düşüp komşusu tek başına değerleniyordu.

Bu yüzden hem yanlış uyarı çıkıyordu hem de GERÇEK hata maskeleniyordu:
kaynak "a thousand", çeviri yanlışlıkla "İki bin" ise eski kod 1000 okuyup
uyuşma sanıyordu.

Gerçek arşivde (181 çift, 129.529 cue): 214 -> 212 uyarı, ikisi de İ vakası,
yeni uyarı yok.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht


class TurkishLowerTest(unittest.TestCase):
    def test_dotted_capital_i_becomes_plain_i(self):
        self.assertEqual(ht._tr_lower("İki"), "iki")
        self.assertEqual(ht._tr_lower("İşte"), "işte")

    def test_dotless_capital_i_becomes_dotless(self):
        self.assertEqual(ht._tr_lower("Irak"), "ırak")

    def test_python_lower_really_does_break_it(self):
        # Kuralın var olma sebebi: bu satır geçerse yardımcı gereksizdir.
        self.assertNotEqual("İki".lower(), "iki")


class TrSpelledNumbersTest(unittest.TestCase):
    def test_sentence_initial_numbers_read_correctly(self):
        self.assertEqual(ht._tr_spelled_numbers("İki bin"), [2000])
        self.assertEqual(ht._tr_spelled_numbers("İki yüz elli"), [250])

    def test_lowercase_forms_are_unchanged(self):
        self.assertEqual(ht._tr_spelled_numbers("iki bin"), [2000])
        self.assertEqual(ht._tr_spelled_numbers("bin dört yüz"), [1400])

    def test_the_neighbour_is_no_longer_read_alone(self):
        # Eski hata: "İki bin" -> 1000 (İki düşüp "bin" tek başına kaldığı için)
        self.assertNotIn(1000, ht._tr_spelled_numbers("İki bin"))

    def test_punctuation_splitting_still_holds(self):
        self.assertEqual(ht._tr_spelled_numbers("İki... bir... ateş!"), [])


class EnglishSideUntouchedTest(unittest.TestCase):
    """İngilizce tarafta I -> ı yapılmamalı: 'SIX' -> 'sıx' olurdu."""

    def test_all_caps_english_still_parses(self):
        self.assertEqual(ht._en_spelled_numbers("SIX HUNDRED"), [600])
        self.assertEqual(ht._en_spelled_numbers("FOURTEEN HUNDRED"), [1400])

    def test_an_all_caps_source_matches_its_translation(self):
        self.assertFalse(
            ht._spelled_number_mismatch("SIX HUNDRED MEN", "Altı yüz adam"))


class EndToEndTest(unittest.TestCase):
    def test_a_correct_translation_no_longer_flags(self):
        for source, target in (
                ("It's been missing for two hundred years.",
                 "İki yüz yıldır kayıp."),
                ("A thousand? Two thousand?", "Bin mi? İki bin mi?")):
            self.assertFalse(ht._spelled_number_mismatch(source, target),
                             (source, target))

    def test_a_real_error_is_no_longer_masked(self):
        # Eskiden "İki bin" 1000 okunduğu için kaynak 1000 ile uyuşuyordu.
        self.assertTrue(
            ht._spelled_number_mismatch("a thousand years passed",
                                        "İki bin yıl geçti"))


class NumericPluralRegressionTest(unittest.TestCase):
    """B3: ondalık ayracı da değişince çoğul regresyonu kaçıyordu."""

    def test_same_spelling_is_caught(self):
        self.assertTrue(
            ht._has_numeric_plural_regression("3 yıl geçti", "3 yıllar geçti"))

    def test_a_changed_separator_no_longer_hides_it(self):
        self.assertTrue(ht._has_numeric_plural_regression(
            "1,5 yıl geçti", "1.5 yıllar geçti"))

    def test_an_untouched_line_is_not_flagged(self):
        self.assertFalse(
            ht._has_numeric_plural_regression("3 yıl geçti", "3 yıl geçti"))

    def test_a_different_number_is_not_this_guards_business(self):
        self.assertFalse(
            ht._has_numeric_plural_regression("3 yıl geçti", "4 yıllar geçti"))


if __name__ == "__main__":
    unittest.main()
