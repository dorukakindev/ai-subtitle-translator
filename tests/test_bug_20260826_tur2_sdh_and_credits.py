# -*- coding: utf-8 -*-
"""Tur 2: gerçek diyalog SDH sanılıyordu; iki künye biçimi kapıdan geçiyordu."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


class RealDialogueIsNotACaptionLabelTest(unittest.TestCase):
    """`_DELIVERY_BARE_ENGLISH_SDH_RE` baştan sona BÜYÜK HARF yazılmış ama
    `re.IGNORECASE` ile derlenmiş. 'herhangi bir ad + konuşma fiili' dalı bu
    yüzden sıradan cümleyi de yutuyordu: 'You speak Portuguese.' gerçek
    diyaloğu SDH sanılıp teslimden silindi ve teslim denetimi kaybı
    'beklenen silme' saydı — yani kayıp raporda da görünmedi.

    215.918 gerçek kaynak cue'sunda önce/sonra ölçüldü: silinmekten kurtulan
    1 cue (ölçülen gerçek vaka), yeni silinen 0.
    """

    def test_the_measured_case_survives(self):
        self.assertFalse(
            gui._source_cue_is_delivery_removable("You speak Portuguese."))

    def test_other_sentence_case_dialogue_survives(self):
        for text in ("You speak English.", "I speak Turkish.",
                     "She speaks French.", "He speaks well."):
            with self.subTest(text=text):
                self.assertFalse(gui._source_cue_is_delivery_removable(text))

    def test_a_capitalised_label_is_still_removed(self):
        # Gerçek etiket her zaman BÜYÜK HARF yazılır; 250 çıplak örnek var.
        for text in ("HE SPEAKS GREEK", "HE SPEAKS KOREAN", "SHE SPEAKS",
                     "THE SPEAK IN TONGUES", "SHE TRANSLATES"):
            with self.subTest(text=text):
                self.assertTrue(gui._source_cue_is_delivery_removable(text))

    def test_a_bracketed_label_is_still_removed(self):
        for text in ("(THEY SPEAK RUSSIAN)", "[speaking Portuguese]"):
            with self.subTest(text=text):
                self.assertTrue(gui._source_cue_is_delivery_removable(text))

    def test_other_branches_keep_their_case_insensitivity(self):
        # Yalnız konuşmacı-fiil dalı duyarlı yapıldı; gerisi aynen kaldı.
        for text in ("APPLAUSE", "EXPLOSION", "Uh."):
            with self.subTest(text=text):
                self.assertTrue(gui._source_cue_is_delivery_removable(text))


class TheseCreditFormsDoNotSlipThroughTest(unittest.TestCase):
    """Künye tanıyıcısı 'copyright' sözcüğüne bağlıydı. 'Subtitles ©ad, yıl'
    ve çıplak '© yıl Şirket' biçimleri iki gerçek teslimde temizlenmeden
    kaldı ve teslim denetiminden `ok` aldı.

    1.121.870 cue ölçüldü: yeni künye sayılan 9 cue (aynı iki dosyanın
    kaynak/final/partial kopyaları), künye olmaktan çıkan 0.
    """

    def test_the_measured_subtitle_credit(self):
        for text in ("Altyazılar ©almoner, 2012", "Subtitles ©almoner, 2012"):
            with self.subTest(text=text):
                self.assertTrue(gui._is_delivery_credit(text))

    def test_the_measured_bare_copyright(self):
        self.assertTrue(gui._is_delivery_credit("© 2016 Chain Production Ltd."))

    def test_the_year_may_come_last(self):
        self.assertTrue(gui._is_delivery_credit("Chain Production Ltd. © 2016"))

    def test_the_old_form_still_works(self):
        self.assertTrue(gui._is_delivery_credit("Copyright © 1999 Acme"))
        self.assertTrue(gui._is_delivery_credit("Subtitles by John"))

    def test_copyright_talked_about_on_screen_is_not_a_credit(self):
        # Ekranda telif KONUSU geçebilir; künye değildir, silinmemeli.
        for text in ("Telif hakkı önemli bir konudur.",
                     "O yıl © sembolü icat edildi.",
                     "Şirket 2016 yılında kuruldu.",
                     "Bu film 1999 yapımıdır.",
                     "Copyright yasası 1976'da değişti ve her şeyi kökten "
                     "dönüştürdü, çünkü artık eserler otomatik korunuyordu."):
            with self.subTest(text=text[:32]):
                self.assertFalse(gui._is_delivery_credit(text))


if __name__ == "__main__":
    unittest.main()
