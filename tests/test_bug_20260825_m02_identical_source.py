# -*- coding: utf-8 -*-
"""Madde 2: korunması doğru olan kaynak metin identical_source sayılmamalı."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

EN, TR = "İngilizce", "Türkçe"


def reason(text):
    return g._untranslated_reason(text, text, source_language=EN,
                                  target_language=TR)


class AnInstitutionOrTitleIsNotUntranslatedTest(unittest.TestCase):
    """`name_particles` listesinde 'of' ve 'from' yoktu, bu yüzden bütün
    'X of Y' kurum/eser adları özel ad sayılmıyor ve çevrilmemiş
    işaretleniyordu.

    278 gerçek çiftte 206.882 cue ölçüldü: identical_source bulgusu 22'den
    17'ye indi (düşen 5'in 5'i yanlış pozitif). Taklit yankı sınamasında
    192.944 ateşlemenin 56'sı kayboldu (%0,029); 56'sının tamamı özel ad
    öbeği ve gerçek arşivde hiçbiri yankılanmamıştı. Özel adın çevrilmeden
    kalması ayrı egzonim geçişinin konusudur.
    """

    def test_the_measured_institution_names(self):
        for text in ("Lloyd's of London.", "Bank of England",
                     "Tower of London", "Plan 10 from Outer Space..."):
            with self.subTest(text=text):
                self.assertEqual(reason(text), "")

    def test_ordinary_dialogue_is_still_flagged(self):
        for text in ("Doesn't exist.", "Three minutes past 5.",
                     "It is potentially explosive,",
                     "Including one called cyclopropane.",
                     "Some of them left."):
            with self.subTest(text=text):
                self.assertEqual(reason(text), "identical_source")

    def test_the_particles_are_registered(self):
        self.assertTrue(g._src_is_proper_name_phrase("Bank of England"))
        self.assertTrue(g._src_is_proper_name_phrase("Plan 10 from Outer Space"))
        self.assertFalse(g._src_is_proper_name_phrase("Some of them left."))


class MarkupIsStrippedBeforeTheIdentityChecksTest(unittest.TestCase):
    """'<i># Hey, hey, hey, hey #</i>' içindeki etiketin 'i' harfi token
    listesine giriyordu; tekrarlı ünlem muafiyeti bu yüzden hiç çalışmadı.
    Etiketsiz hâli zaten muaftı — yani kural doğruydu, girdi kirliydi."""

    def test_the_measured_cue(self):
        self.assertEqual(reason("<i># Hey, hey, hey, hey #</i>"), "")

    def test_the_bare_form_was_already_exempt(self):
        for text in ("Hey, hey, hey, hey", "# Hey, hey, hey, hey #",
                     "♪ Hey, hey, hey, hey ♪"):
            with self.subTest(text=text):
                self.assertEqual(reason(text), "")

    def test_markup_does_not_hide_a_real_echo(self):
        self.assertEqual(reason("<i>It is potentially explosive,</i>"),
                         "identical_source")


class TheForeignLyricClassIsStillOpenTest(unittest.TestCase):
    """Kalan 17 bulgunun tamamı yabancı dilde şarkı sözü/alıntı (Latin ilahi,
    Eski İngilizce). Bunları ayırmak için 'kaynakta İngilizce işlev sözcüğü
    yok' kuralı ölçüldü ve REDDEDİLDİ: 16 yanlış pozitifi düşürürken 39.791
    gerçek yankıyı kaçırıyordu (%20,6). Bu test o sınırı kayda geçirir —
    davranış değişirse ölçüm tekrarlanmalı.
    """

    def test_the_latin_chant_is_still_flagged(self):
        self.assertEqual(reason("# Viderunt omnes. #"), "identical_source")


if __name__ == "__main__":
    unittest.main()
