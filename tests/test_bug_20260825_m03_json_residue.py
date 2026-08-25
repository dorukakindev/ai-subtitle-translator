# -*- coding: utf-8 -*-
"""Madde 3: JSON nesne ayracı cue metnine karışıp teslime yazılıyordu."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import response_integrity as ri


class JsonSeparatorNeverReachesTheDeliveryTest(unittest.TestCase):
    """Kesik yanıt kurtarılırken '},{ ' cue metnine giriyordu; bazı cue'lar
    yalnız ondan ibaretti, yani çeviri tamamen kayıptı ama cue dolu göründüğü
    için eksik sayılmıyordu.

    2.083 gerçek .srt / 1.639.230 cue ölçüldü: sanitizer 16 dosyada 18 cue
    değiştiriyor, hepsi gerçek kalıntı, yanlış pozitif yok.
    """

    def test_a_cue_that_is_only_a_separator_becomes_empty(self):
        for text in ("},{", "  } , { ", "}, {"):
            with self.subTest(text=text):
                self.assertEqual(ri.strip_json_structure_residue(text), "")

    def test_the_measured_trailing_cases(self):
        self.assertEqual(
            ri.strip_json_structure_residue("halüsinasyon yapan?},{"),
            "halüsinasyon yapan?")
        self.assertEqual(
            ri.strip_json_structure_residue('ÇEVİRMEN: "Bence Hükümet, "},{'),
            'ÇEVİRMEN: "Bence Hükümet, "')

    def test_residue_inside_markup(self):
        self.assertEqual(
            ri.strip_json_structure_residue("<i>Saydam oluyor,},{</i>"),
            "<i>Saydam oluyor, </i>")


class TheSanitiserLeavesRealSubtitleTextAloneTest(unittest.TestCase):
    """İlk deneme satır sonundaki tek süslü parantezi de kırpıyordu ve
    ölçüm 61 dosyada 736 cue'nun ASS biçim etiketini bozduğunu gösterdi
    ('{\\i0}' -> '{\\i0'). Kural o yüzden yalnız '},{' dizisine daraltıldı."""

    def test_ass_override_tags_survive(self):
        for text in (r"{\an8}Üst yazı", r"Bu günü korkuyla bekledim{\i0}",
                     r"{\an8}", r"Dougram, Işık Savaşçısı{\i0}"):
            with self.subTest(text=text):
                self.assertEqual(ri.strip_json_structure_residue(text), text)

    def test_sdh_brackets_survive(self):
        for text in ("[MÜZİK]", "[ ♪♪♪ ]", "(gülüyor)"):
            with self.subTest(text=text):
                self.assertEqual(ri.strip_json_structure_residue(text), text)

    def test_a_lone_comma_is_not_this_items_business(self):
        self.assertEqual(ri.strip_json_structure_residue(","), ",")

    def test_ordinary_text_is_untouched(self):
        for text in ("Merhaba, nasılsın?", "Fiyat 5,00 TL.", "Metin }",
                     'Şöyle dedi: "Tamam".'):
            with self.subTest(text=text):
                self.assertEqual(ri.strip_json_structure_residue(text), text)


class TheParserRejectsAStructureOnlyTranslationTest(unittest.TestCase):
    """Ayraçtan ibaret metin geçersiz sayılmalı ki cue eksik listesine
    girsin ve onarım yolu devreye girsin — dolu görünüp teslim edilmesin."""

    def test_a_separator_only_translation_is_invalid(self):
        parsed = ri.parse_translation_payload(
            '[{"i":"1","t":"},{"},{"i":"2","t":"Merhaba"}]', {"1", "2"})
        self.assertIn("1", parsed.invalid_text_ids)
        self.assertNotIn("1", parsed.translations)
        self.assertEqual(parsed.translations.get("2"), "Merhaba")
        self.assertIn("1", parsed.missing_ids)

    def test_a_trailing_separator_is_cleaned_not_dropped(self):
        parsed = ri.parse_translation_payload(
            '[{"i":"1","t":"Selam},{"}]', {"1"})
        self.assertEqual(parsed.translations.get("1"), "Selam")
        self.assertEqual(parsed.invalid_text_ids, set())


if __name__ == "__main__":
    unittest.main()
