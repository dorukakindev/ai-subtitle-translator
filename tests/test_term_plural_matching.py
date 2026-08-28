# -*- coding: utf-8 -*-
"""Sözlük terimi chunk'ta ÇEKİMLİ geçiyorsa da tanınmalı.

`term_in_text` düz `-s` / `'s` ekini tanıyordu ama İngilizcenin ünsüz+y
çoğulunu (`mummy` → `mummies`) tanımıyordu. Terim tanınmayınca o chunk'a
HİÇ enjekte edilmiyor; model onu yeniden çeviriyor ve dosya içinde terim
kayması oluşuyor — bu projenin bilinen `mixed_term` sınıfı.

Ölçüm: 150 gerçek kaynak dosyada 117 dosya-terim çifti kaçıyordu
(`lady`, `story`, `memory`, `monastery`, `property`…). Düzeltmeden sonra 12,
ve kalanların çoğu ölçüm gürültüsü (`Lucky` → `luckies` gerçek çoğul değil).
"""
import unittest

import hybrid_translate as ht


class ConsonantYPluralTest(unittest.TestCase):
    def test_single_word_plural_is_recognised(self):
        for term, text in (("mummy", "three mummies were found"),
                           ("lady", "the ladies arrived"),
                           ("story", "two stories told"),
                           ("monastery", "old monasteries stood"),
                           ("property", "their properties burned")):
            with self.subTest(term=term):
                self.assertTrue(ht.term_in_text(term, text))

    def test_singular_still_matches(self):
        self.assertTrue(ht.term_in_text("mummy", "a mummy stood there"))
        self.assertTrue(ht.term_in_text("lady", "the lady arrived"))

    def test_phrase_plural_is_recognised(self):
        """`lady` ile `young lady` aynı davranmalı."""
        self.assertTrue(ht.term_in_text("young lady", "two young ladies came"))
        self.assertTrue(ht.term_in_text("Greek tragedy", "the greek tragedies"))

    def test_plain_s_plural_unaffected(self):
        for term, text in (("day", "many days passed"),
                           ("boy", "the boys ran"),
                           ("detonator", "two detonators")):
            with self.subTest(term=term):
                self.assertTrue(ht.term_in_text(term, text))

    def test_word_boundary_guards_still_hold(self):
        """Eski davranış korunmalı: 'art' 'start' içinde eşleşmez."""
        self.assertFalse(ht.term_in_text("art", "the start of it"))
        self.assertFalse(ht.term_in_text("win", "open the window"))
        self.assertFalse(ht.term_in_text("mummy", "a mummification"))
        self.assertFalse(ht.term_in_text("young lady", "young ladle"))

    def test_punctuated_keys_still_work(self):
        self.assertTrue(ht.term_in_text("rock'n'roll", "we love rock'n'roll"))
        self.assertTrue(ht.term_in_text("New York", "in new york city"))
        self.assertTrue(ht.term_in_text("co-op", "the co-op store"))

    def test_it_is_a_source_side_matcher(self):
        """KAYNAK metinde arar; Türkçe ek çözümlemesi onun işi değil.

        Bütün çağrı yerleri kaynak metnini veriyor
        (`_locked_source_term_present`, chunk sözlüğü, deyim haritası),
        o yüzden `saray` / `sarayın` eşleşmemesi kusur DEĞİL. Kesme
        işaretiyle ayrılan ek zaten sınırda kalır ve eşleşir.
        """
        self.assertFalse(ht.term_in_text("saray", "sarayın kapısı"))
        self.assertTrue(ht.term_in_text("Göbekli Tepe",
                                        "göbekli tepe'nin taşları"))

    def test_turkish_vowel_before_y_gets_no_ies_form(self):
        """`-ay`/`-ey` sonlu anahtara İngilizce ünsüz+y kuralı uygulanmaz."""
        self.assertFalse(ht.term_in_text("saray", "saraies burada"))

    def test_possessive_still_matches(self):
        self.assertTrue(ht.term_in_text("Thebes", "they left thebes's walls"))


if __name__ == "__main__":
    unittest.main()
