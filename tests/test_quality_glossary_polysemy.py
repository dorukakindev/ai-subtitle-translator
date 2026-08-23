# -*- coding: utf-8 -*-
"""Sabit kalite sözlüğü artık çok anlamlı genel sözcük dayatmıyor."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht

TR = "Türkçe"


class PolysemousEntriesAreGoneTest(unittest.TestCase):
    """202 gerçek çiftte ölçüldü: aktivasyon 60 dosya/88 -> 5 dosya/5.

    Dayatılan karşılığın teslimde kullanılma oranı 'pupils' 0/8, 'pupil'
    1/15, 'mummy' 6/29 idi; yani tablo neredeyse hep yanılıyordu.
    """

    # (kaynak cümle, tabloda ARTIK olmaması gereken anahtar)
    CASES = (
        ("I have enough pupils. Go away.", "pupil"),
        ("none of your pupils would be my rival.", "pupils"),
        ("Say bye to mummy", "mummy"),
        ("the authentic sound of Leonin's Organum", "authentic"),
        ("This is the mortuary temple of Queen Hapshepsut", "mortuary"),
        ("This year I can break a leg, if you wish.", "break a leg"),
        ("Keep an eye on the house.", "on the house"),
        ("a lot of it is downright macabre.", "macabre"),
    )

    def test_no_polysemous_term_is_forced(self):
        for text, term in self.CASES:
            with self.subTest(term=term):
                self.assertNotIn(term, ht.quality_glossary_for_source(text, TR))

    def test_unambiguous_domain_terms_still_work(self):
        self.assertEqual(ht.quality_glossary_for_source("the taxidermy shop", TR),
                         {"taxidermy": "taksidermi"})
        self.assertIn("orrery",
                      ht.quality_glossary_for_source("a brass orrery", TR))

    def test_multi_word_variants_of_dropped_words_survive(self):
        # 'braces' çıktı ama 'polio braces' tek anlamlı, kalmalı.
        self.assertIn("polio braces",
                      ht.quality_glossary_for_source("his polio braces", TR))
        self.assertIn("mortuary school",
                      ht.quality_glossary_for_source("mortuary school", TR))

    def test_no_entry_offers_a_choice_instead_of_a_translation(self):
        # 'macabre' -> 'ürkütücü/ölüm temalı' bir çeviri değil, seçenek listesiydi.
        for src, tgt in ht._COMMON_TURKISH_TERM_GUARD:
            with self.subTest(src=src):
                self.assertNotIn("/", tgt)

    def test_the_turkish_gate_still_holds(self):
        self.assertEqual(ht.quality_glossary_for_source("taxidermy", "İngilizce"), {})

    def test_the_measurement_is_documented(self):
        import inspect
        self.assertIn("YENİ GİRDİ EKLERKEN", inspect.getsource(ht))


if __name__ == "__main__":
    unittest.main()
