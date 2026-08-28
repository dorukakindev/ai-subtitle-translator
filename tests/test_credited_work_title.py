# -*- coding: utf-8 -*-
"""Parantezli künye + yabancı eser adı 'çevrilmemiş' sayılmamalı.

Canlı koşu kanıtı (2026-08-28, Monitor S08E15 The Debussy Film):
`(I DEBUSSY: "Jardins sous la pluie")` gibi cue'lar `identical_source`
diye reddedildi, onarıma sokuldu, onarım aynı metni üretti, yine reddedildi
ve cue `[ÇEVİRİ EKSİK]` olarak kaldı. Aynı koşunun logunda sözlük guard'ı
"kaynakta tırnak içinde geçen eser adları çevrilmeyecek" diyordu — sistemin
iki yanı çelişiyordu. Karar tek kaynakta kalsın diye başlıklar
`ht.quoted_work_titles` ile bulunur.

KURALIN DAR OLMASI ÖLÇÜMLE ZORUNLU:
Parantez şartı olmayan ilk sürüm 268.186 kaynak cue'da 225 cue'yu muaf
tutuyordu ve içlerinde çevrilmesi ŞART olan tırnaklı diyaloglar vardı
("Good morning.", "Cut. Take six.", "Hey, bud, let's party."). Bu yüzden
reddedildi. Parantez şartıyla muafiyet 11 cue'ya iniyor; beşi ayrı metin,
hepsi besteci künyesi, arşivde tek yanlış muafiyet yok.
"""
import unittest

import subtitle_translator_gui as gui


class CreditedWorkTitleTest(unittest.TestCase):
    KUNYE = (
        '(I DEBUSSY: "Jardins sous la pluie")',
        '(I "La demoiselle élue")',
        '(I DEBUSSY:\n"images - Gigues")',
        '(P DEBUSSY: "La Mer")',
        '[MUSIC: "La Marseillaise"]',
    )

    # Ölçümde yanlış muafiyet veren, MUTLAKA çevrilmesi gereken metinler.
    CEVRILMELI = (
        '"Good morning."',
        '"Cut. Take six."',
        "'and put American horror back on the map.'",
        '"Hey, bud, let\'s party."',
        '"Death doesn\'t exist".',
        '(He read "War and Peace" today.)',
        'I told you, I want to talk.',
        '♪ The Angel of the Lord came down',
    )

    def test_credit_lines_are_exempt(self):
        for text in self.KUNYE:
            with self.subTest(text=text[:34]):
                self.assertTrue(gui._src_is_credited_work_title(text))

    def test_translatable_lines_are_not_exempt(self):
        for text in self.CEVRILMELI:
            with self.subTest(text=text[:34]):
                self.assertFalse(gui._src_is_credited_work_title(text))

    def test_identical_credit_line_is_no_longer_flagged(self):
        for text in self.KUNYE:
            with self.subTest(text=text[:34]):
                self.assertEqual(gui._untranslated_reason(text, text), "")

    def test_identical_dialogue_is_still_flagged(self):
        """Guard gevşemedi: tırnaklı İngilizce diyalog hâlâ yakalanıyor."""
        for text in ('"Good morning."', '"Cut. Take six."',
                     'I told you, I want to talk.'):
            with self.subTest(text=text[:34]):
                self.assertTrue(gui._untranslated_reason(text, text))

    def test_parenthesis_is_required(self):
        """Parantezsiz aynı içerik muaf DEĞİL — kuralın dar kalması şart."""
        self.assertTrue(
            gui._src_is_credited_work_title('(I DEBUSSY: "La Mer")'))
        self.assertFalse(
            gui._src_is_credited_work_title('I DEBUSSY: "La Mer"'))

    def test_source_language_title_is_not_exempt(self):
        """Tırnak içi başlık kaynak dildeyse çevrilmeli."""
        self.assertFalse(
            gui._src_is_credited_work_title('(I DEBUSSY: "The Sea and Me")'))

    def test_lowercase_prose_outside_quotes_blocks_it(self):
        self.assertFalse(
            gui._src_is_credited_work_title('(he wrote "La Mer" here)'))

    def test_garbage_input_is_safe(self):
        for text in ("", None, "()", "( )", "[]"):
            with self.subTest(text=text):
                self.assertFalse(gui._src_is_credited_work_title(text))


if __name__ == "__main__":
    unittest.main()
