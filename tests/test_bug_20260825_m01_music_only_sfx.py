# -*- coding: utf-8 -*-
"""Madde 1: parantez içinde salt nota taşıyan kaynak cue SFX sayılmalı."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sdh_cleaner as s


class ABracketedMusicOnlyCueIsSfxTest(unittest.TestCase):
    """Çıplak '♪♪♪' SFX sayılıyordu ama '[ ♪♪♪ ]' sayılmıyordu: parantez içi
    ne betimleyici ne konuşmacı olduğu için reddediliyordu. Bu cue'lar
    "çeviri eksik" işaretlenip dosyaları partial bıraktı.

    300 gerçek kaynakta 224.270 cue ölçüldü: 211 cue SFX'e geçti (hepsi salt
    nota), SFX olmaktan çıkan 0. Etkilenen 6 dosyanın tamamı How We Got to
    Now S01E01-E06.
    """

    def test_the_measured_form_is_sfx(self):
        self.assertTrue(s.src_is_sfx_only("[ ♪♪♪ ]"))

    def test_the_other_measured_forms(self):
        for text in ("[♪♪♪]", "[♪ ♪ ♪]"):
            with self.subTest(text=text):
                self.assertTrue(s.src_is_sfx_only(text))

    def test_round_brackets_and_a_single_note(self):
        for text in ("( ♪♪♪ )", "[ ♪ ]", "[♪ ♪]"):
            with self.subTest(text=text):
                self.assertTrue(s.src_is_sfx_only(text))

    def test_a_bare_note_run_still_works(self):
        self.assertTrue(s.src_is_sfx_only("♪♪♪"))

    def test_a_lyric_between_notes_is_not_sfx(self):
        # Muafiyet yalnız HARF taşımayan gruba açılır; şarkı sözü çeviri ister.
        for text in ("♪ Please don't keep me waiting ♪",
                     "♪ Lütfen beni bekletme ♪",
                     "[ ♪ Bir varmış bir yokmuş ♪ ]"):
            with self.subTest(text=text):
                self.assertFalse(s.src_is_sfx_only(text))

    def test_a_music_descriptor_stays_sfx(self):
        # Bu bir şarkı sözü değil ses etiketidir; silinmesi doğrudur.
        self.assertTrue(s.src_is_sfx_only("[ ♪ Rock müziği çalıyor ♪ ]"))

    def test_plain_dialogue_is_not_sfx(self):
        for text in ("Merhaba", "[ Adam ] Selam", "Bu bir replik."):
            with self.subTest(text=text):
                self.assertFalse(s.src_is_sfx_only(text))

    def test_a_mojibake_note_before_a_descriptor_still_works(self):
        # 4 gerçek dosyada 18 cue bu biçimde; mevcut kod zaten doğru çalışıyor.
        self.assertTrue(s.src_is_sfx_only("Âª[violin playing]"))
        self.assertTrue(s.src_is_sfx_only("Âª[soldier whistling]"))


if __name__ == "__main__":
    unittest.main()
