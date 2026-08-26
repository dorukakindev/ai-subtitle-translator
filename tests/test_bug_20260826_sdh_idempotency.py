# -*- coding: utf-8 -*-
"""SDH temizliği yarım kalıp kalıntı bırakıyor; ikinci geçiş kalıntıyı siliyordu."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sdh_cleaner as s
import subtitle_translator_gui as g

TS = "00:00:01,000 --> 00:00:03,000"


class ACapitalisedBracketIsALabelByItsShapeTest(unittest.TestCase):
    """Betimleyici sözlüğü gerçek dil adlarıyla çalışıyor; genel ifadeleri
    ('SPEAKING NATIVE LANGUAGE'), 'IN' biçimini ('SPEAKING IN GEORGIAN') ve
    listede olmayan ses sözcüklerini ('SHEEP BAAS', 'SNAPS FINGERS')
    kaçırıyordu. Parantez içi baştan sona büyük harf Latin ise etiket olduğu
    biçiminden bellidir.

    215.918 gerçek kaynak cue'su ölçüldü: 126 cue yeni yakalanıyor, 54
    farklı biçim, hepsi elle doğrulandı; SFX olmaktan çıkan 0.
    """

    def test_a_generic_language_label(self):
        for text in ("[SPEAKING NATIVE LANGUAGE]",
                     "[LORNG SPEAKING NATIVE LANGUAGE]",
                     "[SPEAKS IN FOREIGN LANGUAGE]",
                     "(GREETINGS IN LOCAL LANGUAGE)",
                     "(SPEAKING IN QUECHUA)"):
            with self.subTest(text=text):
                self.assertTrue(s.src_is_sfx_only(text))

    def test_a_language_the_dictionary_does_not_know(self):
        for text in ("(SPEAKS CORNISH)", "(SPEAKING DOGON)",
                     "(SPEAKS TUAREG)", "(SPEAKING IN QUECHUA)"):
            with self.subTest(text=text):
                self.assertTrue(s.src_is_sfx_only(text))

    def test_a_speaker_name_before_the_verb(self):
        for text in ("(JOHN RECITES IN GAELIC)", "(THEY SPEAK PORTUGUESE)",
                     "[REPEATING IN HEBREW]", "[WOMEN SPEAKING IN TONGUES]"):
            with self.subTest(text=text):
                self.assertTrue(s.src_is_sfx_only(text))

    def test_non_latin_signs_are_still_protected(self):
        # '[東京都庁]' gerçek ekran tabelası; silinmemeli.
        self.assertFalse(s.src_is_sfx_only("[東京都庁]"))

    def test_real_dialogue_is_untouched(self):
        for text in ("Merhaba, nasılsın?", "[Adam] Selam",
                     "He said (quietly) it was over.",
                     "(bizim vagonlarımız"):
            with self.subTest(text=text):
                self.assertFalse(s.src_is_sfx_only(text))

    def test_the_idiom_is_not_a_label(self):
        # '[Speaking of which]' bir deyim; fiilden sonra 'of' gelirse
        # eslesme reddedilir.
        self.assertFalse(s._is_speech_activity_label("Speaking of which"))

    def test_the_check_needs_a_verb_and_an_object(self):
        self.assertTrue(s._is_speech_activity_label("SPEAKING NATIVE LANGUAGE"))
        self.assertFalse(s._is_speech_activity_label("PARIS"))
        self.assertFalse(s._is_speech_activity_label("CHAPTER ONE"))
        self.assertFalse(s._is_speech_activity_label(""))


class TheRuleRespectsTheLockedDesignTest(unittest.TestCase):
    """İlk iki denemem kilitli davranışları bozdu ve mevcut testler yakaladı:
    '[MUSIC] [CHAPTER ONE]' başlığı ve '[MUSIC] [PARIS]' konum kartı
    KORUNMALI, '[OK]' teknik parça sayılmalı.

    Ders: parantez + büyük harf BİÇİMİ tek başına karar veremez, çünkü ses
    etiketiyle yer/bölüm kartı aynı görünür. Kural bu yüzden biçime değil
    KONUŞMA FİİLİNE bakıyor.
    """

    def test_a_heading_or_place_beside_a_label_is_kept(self):
        self.assertFalse(s.src_is_sfx_only("[MUSIC] [CHAPTER ONE]"))
        self.assertFalse(s.src_is_sfx_only("[MUSIC] [PARIS]"))

    def test_a_short_technical_bracket_is_not_a_label(self):
        self.assertFalse(s.src_is_sfx_only("[OK]"))

    def test_the_partial_residue_case_was_left_alone(self):
        # '[Horse neighs] [Screech] [Boing]' icin denedigim ikinci kural
        # baslik/konum gruplarini da siliyordu; olculen kazanc 10 cue idi ve
        # kilitli tasarimi bozuyordu, bu yuzden GERI ALINDI.
        self.assertFalse(s.src_is_sfx_only("[Horse neighs] [Screech] [Boing]"))


if __name__ == "__main__":
    unittest.main()
