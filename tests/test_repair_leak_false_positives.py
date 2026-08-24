# -*- coding: utf-8 -*-
"""Onarım doğrulayıcısı: korunan özel ad ve kilitli terim sızıntı sayılmaz."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

EN = "İngilizce"
TR = "Türkçe"


class AKeptProperNounIsNotALeakTest(unittest.TestCase):
    """2026-08-24 koşusu: onarım üç cue'yu reddetti, üçü de DOĞRU çeviriydi.
    'american' sızıntı listesinde ama 'American Film Institute' korunması
    gereken kurum adı. Kodda yalnız 'british' için muafiyet vardı.

    196 gerçek kaynak/teslim çiftinde 145.108 cue ölçüldü: kuralın ürettiği
    2 bayrağın 2'si de yanlış pozitifti ('American Brain Foundation'),
    muafiyetle ikisi de düştü. Gerçek sızıntı bulgusu kaybolmadı.
    """

    def test_an_institution_name_with_a_turkish_suffix(self):
        self.assertEqual(g._untranslated_reason(
            "It was Trent's thesis film at the American Film Institute",
            "Trent'in American Film Institute'taki tez filmiydi,",
            source_language=EN, target_language=TR), "")

    def test_a_bank_name_with_a_turkish_suffix(self):
        self.assertEqual(g._untranslated_reason(
            "It's sitting there behind American State Bank.",
            "O, American State Bank'in arkasında duruyor.",
            source_language=EN, target_language=TR), "")

    def test_the_measured_real_file_case(self):
        self.assertEqual(g._untranslated_reason(
            "THE AMERICAN BRAIN FOUNDATION SUPPORTS VITAL RESEARCH",
            "American Brain Foundation, önemli araştırmaları destekler;",
            source_language=EN, target_language=TR), "")

    def test_a_bare_leak_is_still_caught(self):
        for src, tgt in (
                ("The Americans came here in 1920.",
                 "Americans buraya 1920'de geldi."),
                ("Egyptian mythology is rich.", "Egyptian mythology zengindir."),
                ("The Europeans arrived.", "Europeans geldi."),
                ("The Egyptian priests knew.", "Egyptian rahipler biliyordu.")):
            with self.subTest(src=src):
                self.assertTrue(g._untranslated_reason(
                    src, tgt, source_language=EN,
                    target_language=TR).startswith("partial_english_token"))

    def test_a_phrase_absent_from_the_source_is_still_a_leak(self):
        # Hedefte büyük harfli öbek var ama kaynakta o öbek YOK: korunan ad değil.
        self.assertTrue(g._untranslated_reason(
            "Egyptian creation myths.", "Egyptian Yaratılış Efsaneleri.",
            source_language=EN,
            target_language=TR).startswith("partial_english_token"))

    def test_the_phrase_match_does_not_swallow_ordinary_words(self):
        # Desenin tamamına re.I verilirse büyük harf sınıfı küçük harfleri de
        # yutar ve öbeğe 'tez filmiydi' karışıp muafiyet hiç çalışmazdı.
        self.assertTrue(g._leak_word_is_kept_proper_noun(
            "american", "at the American Film Institute",
            "American Film Institute'taki tez filmiydi"))


class ALockedTermIsNotUntranslatedTest(unittest.TestCase):
    """'Plan 10 from Outer Space' dosyanın kilitli terimiydi ve hedefte
    olduğu gibi durması gerekiyordu; İngilizce örtüşme denetimi bunu
    çevrilmemişlik sayıp doğru onarımı reddetti (Beaver Trilogy #685)."""

    LOCK = {"Plan 10 from Outer Space": "Plan 10 from Outer Space"}

    def test_a_locked_title_is_accepted(self):
        self.assertEqual(g._untranslated_reason(
            "After Trent finished Plan 10 from Outer Space,",
            "Trent, Plan 10 from Outer Space'i tamamladıktan sonra",
            locked_terms=self.LOCK,
            source_language=EN, target_language=TR), "")

    def test_the_masking_only_covers_identity_terms(self):
        # Çevrilmesi kararlaştırılmış terim maskelenmez.
        masked = g._mask_locked_term_spans(
            "the Blue Period and Plan 10 from Outer Space",
            {"Plan 10 from Outer Space": "Plan 10 from Outer Space",
             "Blue Period": "Mavi Dönem"})
        self.assertIn("Blue Period", masked)
        self.assertNotIn("Outer Space", masked)

    def test_a_single_word_term_is_not_masked(self):
        # Tek sözcüklük terim maskelenirse denetim körleşir.
        self.assertIn("Hollywood", g._mask_locked_term_spans(
            "born in Hollywood", {"Hollywood": "Hollywood"}))


if __name__ == "__main__":
    unittest.main()
