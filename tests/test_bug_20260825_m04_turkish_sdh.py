# -*- coding: utf-8 -*-
"""Madde 4: Türkçe ses etiketi tanınmıyordu; temizleme sayacı yoktu."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sdh_cleaner as s
import subtitle_translator_gui as g


class TurkishSoundLabelsAreRecognisedTest(unittest.TestCase):
    """377 anahtar sözcüğün tamamına yakını İngilizceydi. 377 gerçek teslimde
    284.076 cue tarandığında 10 dosyada 17 parantezli etiket ayakta kalmıştı
    ve 15'i Türkçe ses tarifiydi.

    Ölçüm önce/sonra: 20 cue yeni siliniyor, hepsi gerçek ses etiketi;
    yanlışlıkla korunan yok, silinen replik yok.
    """

    def test_the_measured_labels(self):
        for text in ("KEDİ MİYAVLAR", "GICIRTI!", "HAYVAN ULUMASI",
                     "KEÇİ MELEMESİ", "HOROZ TISLAMASI", "KÖPEK İNLEMESİ",
                     "KUŞ CİVILTISI", "KÖPEK HAVLAMASI", "SİREN ULUMASI",
                     "VIZILTI", "ACILI ÇIĞLIKLAR", "SESLERİN UĞULTUSU"):
            with self.subTest(text=text):
                self.assertTrue(s.is_sdh_descriptor(text))

    def test_a_bracketed_label_in_sentence_case(self):
        self.assertTrue(s.is_sdh_descriptor("Gıcırtı!", bracketed=True))


class RealDialogueUsingASoundWordSurvivesTest(unittest.TestCase):
    """İlk deneme yalnız köke bakıyordu ve ölçüm onu REDDETTİ: gerçek
    replikleri siliyordu. Etiket olabilmek için metnin parantez içinde ya da
    baştan sona büyük harf OLMASI ve en çok dört sözcük tutması gerekir.
    """

    def test_the_measured_dialogue_lines(self):
        for text in ("kibirli bir homurtuyla çekip gittiler;",
                     "Bir mandolinin hoş iniltisini",
                     "İster bir köpeğin havlaması olsun,",
                     "Acı meyveyi tükürme içgüdüsü",
                     "Yogi Gi, migren ve kulak çınlamasının",
                     "Kahkahadan kırılıp geçerken herhangi bir"):
            with self.subTest(text=text):
                self.assertFalse(s._tr_sdh_label(text))

    def test_a_first_person_line_is_never_a_label(self):
        # Konuşan kişiyi işaret eden ek varsa etiket olamaz.
        for text in ("YUKARI ÇIKIYORUZ", "BENİ DAVET ETSELERDİ"):
            with self.subTest(text=text):
                self.assertFalse(s._tr_sdh_label(text))

    def test_a_long_capitalised_sentence_is_not_a_label(self):
        # Tamamı büyük harf kaynakta uzun cümle etiket sanılmamalı.
        self.assertFalse(
            s._tr_sdh_label("KAHKAHA, DEMOKRASİDEN YANA BİR GÜÇTÜR"))


class TheCleaningPassReportsWhatItRemovedTest(unittest.TestCase):
    """Geçiş sessizdi: log'da yalnız süre görünüyordu, silinen cue sayısı
    hiç yazılmıyordu — çalışmadığını fark etmenin yolu yoktu."""

    TS = "00:00:01,000 --> 00:00:03,000"

    def test_a_removal_is_reported(self):
        seen = []
        blocks = [("1", self.TS, "[LAUGHS]"), ("2", self.TS, "Merhaba")]
        g.clean_sdh(blocks, log_fn=lambda msg, kind="info": seen.append(msg))
        self.assertTrue(seen)
        self.assertIn("SDH temizleme", seen[0])

    def test_an_empty_run_is_also_reported(self):
        seen = []
        blocks = [("1", self.TS, "Merhaba"), ("2", self.TS, "Nasılsın")]
        g.clean_sdh(blocks, log_fn=lambda msg, kind="info": seen.append(msg))
        self.assertEqual(len(seen), 1)
        self.assertIn("bulunmadı", seen[0])

    def test_the_pass_still_returns_its_blocks_without_a_logger(self):
        blocks = [("1", self.TS, "Merhaba")]
        self.assertEqual(len(g.clean_sdh(blocks)), 1)


if __name__ == "__main__":
    unittest.main()
