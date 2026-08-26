# -*- coding: utf-8 -*-
"""Aynı dosya bir yeri hem 'Troy' hem 'Truva' diye yazıyor mu.

`detect_mixed_term_renderings` bunu göremiyor: kümeleyicisi hedefteki
biçimi kaynak sözcüğe BENZERLİĞİNDEN buluyor. İki yazım da kaynağa
benziyorsa (Incas/İnka) çalışıyor; doğru çeviri kaynağa hiç benzemiyorsa
(Troy→Truva) ikinci küme kurulamıyor ve "≥2 küme" koşulu sağlanmıyor.
Gerçek arşivde altı Truva bölümünün hepsinde iki biçim yan yanaydı ve
mevcut dedektör altısında da sıfır bulgu veriyordu.

Ölçüm (288 gerçek kaynak/teslim çifti): 6 bulgu, 5 dosya, gözle
doğrulanan precision 6/6. Elenen bilinen yanlış alarmlar: 'Egyptian
Sonics' (kitap adı), 'New England' (ABD bölgesi).
"""
import unittest

import subtitle_translator_gui as g


def _blocks(lines):
    return [(str(i), "00:00:%02d,000 --> 00:00:%02d,500" % (i, i), text)
            for i, text in enumerate(lines, 1)]


def _src(lines):
    return {str(i): text for i, text in enumerate(lines, 1)}


class UntranslatedExonymTest(unittest.TestCase):
    def test_both_forms_present_is_reported(self):
        source = ["Troy was besieged.", "The walls of Troy fell.",
                  "Troy burned for days.", "They remembered Troy."]
        target = ["Truva kuşatıldı.", "Troy surları düştü.",
                  "Truva günlerce yandı.", "Troy'u hatırladılar."]
        findings = g.detect_untranslated_exonyms(_blocks(target), _src(source))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["term"], "Troy")
        self.assertEqual(findings[0]["renderings"], {"Troy": 2, "Truva": 2})

    def test_consistent_translation_is_not_reported(self):
        source = ["Troy was besieged.", "The walls of Troy fell.",
                  "Troy burned.", "They remembered Troy."]
        target = ["Truva kuşatıldı.", "Truva surları düştü.",
                  "Truva yandı.", "Truva'yı hatırladılar."]
        self.assertEqual(
            g.detect_untranslated_exonyms(_blocks(target), _src(source)), [])

    def test_consistently_untranslated_is_not_reported(self):
        # Tek biçim kullanılıyorsa bu bir TUTARSIZLIK değil; bu dedektörün
        # ölçütü iki biçimin de metinde AÇIKÇA bulunmasıdır.
        source = ["Troy was besieged.", "The walls of Troy fell."]
        target = ["Troy kuşatıldı.", "Troy surları düştü."]
        self.assertEqual(
            g.detect_untranslated_exonyms(_blocks(target), _src(source)), [])

    def test_longer_proper_name_is_not_a_leak(self):
        # 'Egyptian Sonics' kitap adı, 'New England' ABD bölgesi.
        source = ["He mentions Egyptian Sonics.", "Egyptian Sonics again.",
                  "The Egyptian pyramids are old.", "Egyptian sand."]
        target = ["Egyptian Sonics'ten söz ediyor.", "Yine Egyptian Sonics.",
                  "Mısır piramitleri eskidir.", "Mısır kumu."]
        self.assertEqual(
            g.detect_untranslated_exonyms(_blocks(target), _src(source)), [])

        source = ["New England is cold.", "Ice from New England."]
        target = ["New England soğuktur.", "New England buzu.",
                  "İngiltere ayrı bir yer.", "İngiltere'de yağmur var."]
        self.assertEqual(
            g.detect_untranslated_exonyms(_blocks(target), _src(source)), [])

    def test_roman_numeral_qualifier_still_counts_as_a_leak(self):
        # 'Troy VI' uzun bir ad değil, roma rakamlı nitelemedir; ilk filtre
        # bunu eleyince üç gerçek bulgu düşüyordu.
        source = ["Troy VI was destroyed.", "Troy VIIa followed.",
                  "Troy is a city.", "Troy again."]
        target = ["Troy VI yıkıldı.", "Troy VIIa onu izledi.",
                  "Truva bir şehirdir.", "Truva yine."]
        findings = g.detect_untranslated_exonyms(_blocks(target), _src(source))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["renderings"]["Troy"], 2)

    def test_term_not_in_source_is_ignored(self):
        source = ["A quiet evening.", "Nothing happened.",
                  "The room was dark.", "They slept."]
        target = ["Troy sessizdi.", "Truva karanlıktı.",
                  "Troy uyudu.", "Truva bekledi."]
        self.assertEqual(
            g.detect_untranslated_exonyms(_blocks(target), _src(source)), [])

    def test_identity_exonyms_are_not_in_the_table(self):
        # Türkçesi AYNI olan adlar tabloya girerse her geçişleri bulgu olur;
        # ilk ölçümde girmişlerdi ve 70 sahte bulgu ürettiler.
        for name, turkish in g._EXONYM_TR.items():
            with self.subTest(name=name):
                self.assertNotEqual(name.casefold(), turkish.casefold())


if __name__ == "__main__":
    unittest.main()
