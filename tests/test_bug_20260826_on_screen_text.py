# -*- coding: utf-8 -*-
"""Ekran yazısı tespiti gerçek repliği tabela sayıyordu."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht

TS = "00:00:01,000 --> 00:00:03,000"


class OrdinaryDialogueIsNotASignTest(unittest.TestCase):
    """`is_ost` işaretli cue prompt'a "tabela gibi çevir; kısa ve etiket
    biçiminde tut, konuşma dili ve HİTAP BİÇİMİ ekleme" talimatıyla gidiyor.
    Yanlış işaret bu yüzden doğrudan çeviri kalitesini düşürür.

    Desende iki kusur vardı: son dalın birim grubu opsiyoneldi (yani fiilen
    "rakamla başlayan her satır") ve `re.IGNORECASE` açık `[A-Z]`
    sınıflarını etkisizleştiriyordu.

    290 gerçek kaynakta 215.918 cue ölçüldü: işaret 3.344'ten 1.337'ye indi,
    yeni işaretlenen 0.
    """

    def test_a_line_starting_with_a_number_is_not_a_card(self):
        for text in ("3 people died that night.",
                     "1959 was the year everything changed.",
                     "12 of them were children.",
                     "303 heroic warriors die in the battle.",
                     "30 million people were now in darkness."):
            with self.subTest(text=text):
                self.assertFalse(ht.looks_like_on_screen_text(text))

    def test_a_card_word_in_sentence_case_is_not_a_card(self):
        for text in ("Then 20 people arrived.",
                     "Later 3 men came to the village.",
                     "Part 2 of the story begins here."):
            with self.subTest(text=text):
                self.assertFalse(ht.looks_like_on_screen_text(text))

    def test_a_genuine_card_still_matches(self):
        for text in ("CHAPTER 4", "PART 2", "DAY 3", "20 MINUTES",
                     "30 SECONDS", "London, 1959"):
            with self.subTest(text=text):
                self.assertTrue(ht.looks_like_on_screen_text(text))

    def test_the_card_must_be_the_whole_cue(self):
        # 'EAGLEMAN. VOICE OVER: 6 SECONDS ELAPSED...' etiketi soyulunca
        # '6 SECONDS ELAPSED...' kalıyordu ve süre kartı sanılıyordu.
        self.assertFalse(
            ht.looks_like_on_screen_text("London, 1959 was a hard year."))


class AnAllCapsSourceDisablesTheCapsSignalTest(unittest.TestCase):
    """Kapalı altyazı kaynaklarının tamamı büyük harftir; orada "tamamı
    büyük harf" hiçbir şey ayırt etmez ve gerçek replik de tabela sayılır.
    Aynı karar `sdh_cleaner.src_is_sfx_only` için de dosya düzeyinde
    veriliyor. Ölçümde 6 kaynak dosya bu sınıfa girdi.
    """

    CAPS = [("1", TS, "WOMAN: SHOULD NOT WHAT MAKES US UNIQUE"),
            ("2", TS, "ADVANCED GENOMIC TESTING"),
            ("3", TS, "THE BRAIN WITH DAVID EAGLEMAN")]
    MIXED = [("1", TS, "He said it was over."),
             ("2", TS, "CHAPTER 4"),
             ("3", TS, "She left early.")]

    def test_the_file_level_detector(self):
        self.assertTrue(ht.source_is_all_caps_file(self.CAPS))
        self.assertFalse(ht.source_is_all_caps_file(self.MIXED))

    def test_an_empty_or_short_file_is_not_all_caps(self):
        self.assertFalse(ht.source_is_all_caps_file([]))
        self.assertFalse(ht.source_is_all_caps_file(None))

    def test_caps_dialogue_is_spared_in_a_caps_file(self):
        for text in ("WOMAN: SHOULD NOT WHAT MAKES US UNIQUE",
                     "ADVANCED GENOMIC TESTING"):
            with self.subTest(text=text):
                self.assertFalse(
                    ht.looks_like_on_screen_text(text, False))

    def test_structural_cards_survive_even_in_a_caps_file(self):
        for text in ("CHAPTER 4", "London, 1959", "20 MINUTES"):
            with self.subTest(text=text):
                self.assertTrue(ht.looks_like_on_screen_text(text, False))

    def test_a_mixed_file_keeps_the_caps_signal(self):
        self.assertTrue(
            ht.looks_like_on_screen_text("ADVANCED GENOMIC TESTING", True))

    def test_both_flows_decide_at_file_level(self):
        import inspect
        import subtitle_translator_gui as gui
        self.assertIn("source_is_all_caps_file",
                      inspect.getsource(ht.build_batch_requests))
        self.assertIn("source_is_all_caps_file",
                      inspect.getsource(gui.build_requests))


if __name__ == "__main__":
    unittest.main()
