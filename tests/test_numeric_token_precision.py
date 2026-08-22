# -*- coding: utf-8 -*-
"""_numeric_token_mismatch kesinliği — derin denetim Tur 4, madde 6.

Guard ham token dizilerini birebir karşılaştırıyordu; bu yüzden üç MEŞRU
sınıfı hata sayıyordu: rakamın doğru yazıyla çevrilmesi, saat biçimi farkı
ve birim dönüşümü. Karşılaştırma artık DEĞER üzerinden yapılıyor.

Gerçek arşiv ölçümü (181 çift, 129.344 cue): 872 uyarı -> 252.
Kalanların çoğu kaynak biçim bozukluğu ("- 2, 000...") veya deyimsel
karşılık ("about 40" -> "kırklarında"); gerçek sayı kayıpları duruyor.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht


class SpelledTranslationTest(unittest.TestCase):
    def test_a_digit_written_out_in_turkish_is_accepted(self):
        for source, target in (("For 3 years nobody noticed",
                                "Üç yıl boyunca kimse fark etmedi"),
                               ("Engaged for 15 years.",
                                "On beş yıl nişanlı kaldılar."),
                               ("200 grams", "iki yüz gram"),
                               ("50,000 spectators", "Elli bin seyirci"),
                               ("5%", "yüzde beş")):
            self.assertFalse(ht._numeric_token_mismatch(source, target),
                             (source, target))

    def test_a_sentence_initial_number_is_seen(self):
        # "İki".lower() birleşik nokta bırakır; Türkçe İ elle indiriliyor.
        self.assertFalse(
            ht._numeric_token_mismatch("2 more cows", "İki inek daha"))

    def test_suffixed_number_words_count(self):
        self.assertFalse(
            ht._numeric_token_mismatch("I start at 5", "Beşte başlıyorum"))
        self.assertFalse(ht._numeric_token_mismatch(
            "from 5 to 7. now 8", "beşle yedi arasındaydı. Şimdi saat sekiz."))

    def test_the_suffix_list_is_closed(self):
        # Serbest kısaltma "Biró"yu "bir" sanıp havuza 1 ekliyor ve komşu
        # sayılarla birleşip 38'i 39 yapıyordu.
        values = ht._tr_number_values_unfiltered("János Biró, otuz sekiz yaşında")
        self.assertIn(38, values)
        self.assertNotIn(39, values)

    def test_adjacent_words_count_individually_too(self):
        values = ht._tr_number_values_unfiltered("beşle yedi arasında")
        self.assertIn(5, values)
        self.assertIn(7, values)


class TimeFormatTest(unittest.TestCase):
    def test_clock_formats_differ_without_being_wrong(self):
        for source, target in (("Today at 8:30 A.M.", "Bugün saat 08.30'da,"),
                               ("07:00 to 08:00 Exercise.",
                                "07:00-08:00 Egzersiz.")):
            self.assertFalse(ht._numeric_token_mismatch(source, target),
                             (source, target))

    def test_digit_groups_ignore_separator_style(self):
        self.assertEqual(sorted(ht._numeric_digit_groups("8:30")), [8, 30])
        self.assertEqual(sorted(ht._numeric_digit_groups("08.30")), [8, 30])
        self.assertEqual(ht._numeric_digit_groups("1,400"), [1400])


class UnitConversionTest(unittest.TestCase):
    def test_imperial_to_metric_is_expected(self):
        for source, target in (("150 pounds", "68 kilo"),
                               ("102 degrees", "38,9 derece"),
                               ("6 feet tall", "1,80 metre boyunda")):
            self.assertFalse(ht._numeric_token_mismatch(source, target),
                             (source, target))

    def test_a_metric_word_alone_does_not_excuse_anything(self):
        self.assertTrue(
            ht._numeric_token_mismatch("200 grams", "300 gram"))


class RealLossTest(unittest.TestCase):
    def test_a_changed_year_is_still_caught(self):
        self.assertTrue(ht._numeric_token_mismatch("1993 idi", "1933 idi"))

    def test_a_changed_count_is_still_caught(self):
        self.assertTrue(
            ht._numeric_token_mismatch("He was 3 years old", "O 5 yaşındaydı"))

    def test_a_dropped_number_is_still_caught(self):
        self.assertTrue(
            ht._numeric_token_mismatch("back in 1912", "savaş öncesi"))

    def test_a_source_without_digits_never_fires(self):
        self.assertFalse(ht._numeric_token_mismatch("no numbers here", "üç beş"))


if __name__ == "__main__":
    unittest.main()
