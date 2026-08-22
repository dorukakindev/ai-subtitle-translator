# -*- coding: utf-8 -*-
"""Sayı guard'ının kesinliği — derin denetim Tur 4, madde 3/4/5.

Üç ayrı kusur aynı guard'ı yanıltıyordu:
  3) Tokenizer noktalamayı atıyordu: "Two... one..." tek grup olup 3 okunuyordu.
  4) Kaynak dili bilinmeden beş sözlük aynı cümlede çalışıyordu: "cents"
     Fransızca cent=100 sayılıyordu.
  5) _digit_tokens_as_ints rakam dışını siliyordu: "2,5" -> 25, "8-16" -> 816,
     "-25" -> 25; yani biçim ve işaret bozulmaları guard'dan geçiyordu.

Gerçek arşivde (181 kaynak-teslim çifti, 129.529 cue) ölçüm:
315 uyarı -> 214 uyarı; 101 yanlış-pozitif elendi, YENİ uyarı çıkmadı.
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht


class PunctuationBoundaryTest(unittest.TestCase):
    def test_ellipsis_does_not_merge_a_countdown(self):
        self.assertEqual(ht._source_spelled_numbers("Two... one... fire!"), [])

    def test_commas_split_a_counting_sequence(self):
        self.assertEqual(ht._source_spelled_numbers("Seven, eight, nine..."), [])

    def test_a_comma_inside_one_number_still_joins(self):
        # "four thousand, five hundred" tek sayıdır: çarpan içeren grupta
        # virgül ayırıcı değil, binlik yazımıdır.
        self.assertEqual(
            ht._source_spelled_numbers("four thousand, five hundred"), [4500])

    def test_hyphen_still_joins(self):
        self.assertEqual(ht._source_spelled_numbers("twenty-five"), [25])

    def test_sentence_end_splits(self):
        self.assertEqual(
            ht._source_spelled_numbers("It cost thirteen. Twenty came back."),
            [13, 20])

    def test_multiplier_groups_survive(self):
        for text, expected in (("fourteen hundred", [1400]),
                               ("fifty thousand spectators", [50000]),
                               ("one hundred twenty", [120]),
                               ("half a hundred", [50])):
            self.assertEqual(ht._source_spelled_numbers(text), expected, text)

    def test_turkish_side_splits_the_same_way(self):
        # Asimetri yapay uyuşmazlık üretiyordu: kaynak bölünüp çeviri
        # bölünmezse aynı cümle uyuşmaz görünür.
        self.assertEqual(ht._tr_spelled_numbers("İki... bir... ateş!"), [])
        self.assertEqual(ht._tr_spelled_numbers("dört bin beş yüz"), [4500])

    def test_the_reported_countdown_no_longer_flags(self):
        self.assertFalse(ht._spelled_number_mismatch(
            "Two... one... fire!", "İki... bir... ateş!"))


class SourceLanguageTest(unittest.TestCase):
    def test_english_source_ignores_the_french_lexicon(self):
        self.assertEqual(
            ht._source_spelled_numbers("for 25 cents.", "English"), [])

    def test_unknown_language_rejects_a_lone_foreign_word(self):
        # 'cents' tek başına Fransızca sayılmaz; tek sözcüklük eşleşme yetersiz.
        self.assertEqual(ht._source_spelled_numbers("for 25 cents."), [])

    def test_french_source_still_reads_french(self):
        self.assertEqual(
            ht._source_spelled_numbers("vingt cinq mille", "French"), [25000])

    def test_named_language_blocks_the_other_lexicons(self):
        # 'once' İspanyolca 11'dir ama kaynak İngilizceyse sayı değildir.
        self.assertEqual(
            ht._source_spelled_numbers("I saw it once", "English"), [])

    def test_language_hints_are_case_and_locale_tolerant(self):
        for name in ("english", "EN", "İngilizce", "en-US"):
            self.assertEqual(ht._source_number_lang_code(name), "en", name)
        self.assertEqual(ht._source_number_lang_code("Fransızca"), "fr")
        self.assertEqual(ht._source_number_lang_code("Klingon"), "")

    def test_unknown_language_keeps_multiword_foreign_numbers(self):
        self.assertIn(600, ht._source_spelled_numbers("six cents"))


class DigitTokenTypeTest(unittest.TestCase):
    def test_decimal_is_not_flattened_into_an_integer(self):
        self.assertEqual(ht._digit_tokens_as_ints("2,5"), [2.5])
        self.assertTrue(ht._spelled_number_mismatch("twenty-five", "2,5"))

    def test_range_is_split_not_concatenated(self):
        self.assertEqual(ht._digit_tokens_as_ints("8-16"), [8, 16])
        self.assertTrue(
            ht._spelled_number_mismatch("eight hundred sixteen", "8-16"))

    def test_sign_is_preserved(self):
        self.assertEqual(ht._digit_tokens_as_ints("-25"), [-25])
        self.assertTrue(ht._spelled_number_mismatch("twenty-five", "-25"))

    def test_thousands_separator_still_reads_as_one_number(self):
        self.assertEqual(ht._digit_tokens_as_ints("50.000"), [50000])
        self.assertFalse(ht._spelled_number_mismatch("fifty thousand", "50.000"))

    def test_a_correct_digit_translation_is_still_accepted(self):
        self.assertFalse(ht._spelled_number_mismatch(
            "fourteen hundred years ago", "1400 yıl önce"))

    def test_time_is_split_into_its_parts(self):
        self.assertEqual(ht._digit_tokens_as_ints("12:30"), [12, 30])


class ValidatorPlumbingTest(unittest.TestCase):
    """src_lang gerçekten guard'a ulaşıyor mu?"""

    def _reasons(self, **kwargs):
        cues = [SimpleNamespace(index=7, text="for 25 cents.")]
        blocks = [(7, "00:00:01,000 --> 00:00:02,000", "25 sent için.")]
        hits = ht.run_validators(blocks, cues, **kwargs)
        return {str(idx): reason for idx, _ts, _text, reason in hits}

    def test_english_source_silences_the_french_reading(self):
        reasons = self._reasons(tgt_lang="Turkish", src_lang="English")
        self.assertNotIn("SPELLED_NUMBER_MISMATCH", reasons.get("7", ""))

    def test_default_call_still_works_without_src_lang(self):
        reasons = self._reasons(tgt_lang="Turkish")
        self.assertNotIn("SPELLED_NUMBER_MISMATCH", reasons.get("7", ""))

    def test_a_real_loss_is_still_reported(self):
        cues = [SimpleNamespace(index=8, text="fourteen hundred years ago")]
        blocks = [(8, "00:00:01,000 --> 00:00:02,000", "yıllar önce")]
        hits = ht.run_validators(blocks, cues, tgt_lang="Turkish",
                                 src_lang="English")
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}
        self.assertIn("SPELLED_NUMBER_MISMATCH", reasons.get("8", ""))


if __name__ == "__main__":
    unittest.main()
