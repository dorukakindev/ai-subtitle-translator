# -*- coding: utf-8 -*-
"""Parantez içi etiketler için dilden bağımsız BİÇİM kuralı.

Beyaz liste (_SDH_KEYWORDS ve arkadaşları) İngilizce sözcüklere dayanıyordu:
Türkçeye çevrilmiş ses/konuşmacı etiketleri hiçbir kurala uymadığı için teslim
dosyasında kalıyordu. Buradaki örneklerin TAMAMI kullanıcının GERÇEK teslim
dosyalarından alındı (274 dosyanın 23'ünde artık etiket vardı).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sdh_cleaner as sc


class TurkishLabelsAreStrippedTest(unittest.TestCase):
    """Gerçek tesliminde kalan Türkçe etiketler artık siliniyor."""

    UPPERCASE = (
        "BIÇAĞI BIRAKIR", "DİŞ EMME", "KEDİ MIRMIRLAR", "MAKİNEYE VURUR",
        "PARMAK ŞAKLATIR", "SEYİRCİ SESSİZLEŞİR", "YAZAR KASA ZİLİ",
        "GÜLME", "HAYVAN ULUMASI", "KEDİ MİYAVLAR", "HAT KESİLİR",
        "KURBAĞA VIRT VIRT EDER", "HOROZ TISLAMASI", "KÖPEK İNLEMESİ",
        "KIKIRDEME", "ÇAN SESLERİ", "TV",
    )
    LOWER_OR_MIXED = (
        "uğultu", "enstrümanlar ısınıyor", "radio", "Keçi melemesi",
        "Burnunu sümkürüyor", "Köpek Laura'yı taklit eder",
        "Hırlama, tükürme", "Il hurle", "Isaac Babel'in eşi",
    )

    def test_uppercase_labels_are_stripped(self):
        for label in self.UPPERCASE:
            with self.subTest(label=label):
                self.assertEqual(sc.strip_sdh_line("[%s]" % label), "")

    def test_lowercase_and_mixed_labels_are_stripped_when_standalone(self):
        for label in self.LOWER_OR_MIXED:
            with self.subTest(label=label):
                self.assertEqual(sc.strip_sdh_line("[%s]" % label), "")

    def test_uppercase_label_prefix_leaves_the_dialogue(self):
        self.assertEqual(
            sc.strip_sdh_line("[KEDİ MİYAVLAR] Gel buraya."), "Gel buraya.")

    def test_italic_wrapped_label_is_still_a_label(self):
        self.assertTrue(sc.is_sdh_only("<i>(Aleksandr İvanoviç'in kızı)</i>"))
        self.assertEqual(
            sc.strip_sdh_descriptors("<i>[uğultu]</i>\nMerhaba."),
            "Merhaba.")

    def test_trailing_colon_marks_a_speaker_label(self):
        self.assertEqual(sc.strip_sdh_line("[Bayan Milagros:]"), "")

    def test_legacy_path_no_longer_needs_the_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ÇAN SESLERİ]")]
        self.assertEqual(sc.clean_sdh_blocks(blocks), [])


class RealContentIsPreservedTest(unittest.TestCase):
    """Aynı biçimdeki GERÇEK içerik korunmalı — hepsi teslim dosyalarından."""

    def _kept(self, text):
        self.assertEqual(sc.strip_sdh_line(text), text)

    def test_screen_cards_and_citations_survive(self):
        self._kept("[I. KSENAKİS, 1978]")
        self._kept("[THE END]")
        # '[BERLIN 1961]' zaten eski konuşmacı-adı sezgisiyle siliniyordu;
        # burada garanti edilen, BİÇİM kuralının ona el atmamasıdır.
        self.assertFalse(sc._bracket_shape_is_label("BERLIN 1961"))

    def test_numeric_screen_text_survives(self):
        self._kept("[404 ERROR]")

    def test_title_case_proper_nouns_survive(self):
        self._kept("[Sesame Street]")

    def test_quoted_and_formula_content_survives(self):
        self._kept('["karşıtların birliği"]')
        self._kept("[G = Giza]")
        self._kept('[Portekizce "non"]')

    def test_sentences_and_clauses_survive(self):
        self._kept("[Vay be.]")
        self._kept("[Beni davet etselerdi...!]")
        self._kept("[çünkü sobama şeker döktüm]")
        self._kept("[Böyle bir şeye izin veren de ne biçim bir Tanrı]")

    def test_bracketed_title_prefix_survives(self):
        self._kept("[Soft Power] A documentary.")
        self._kept("[Latin] title remains")

    def test_song_credits_survive(self):
        self._kept('[# Eddie Warner\'dan "Come"]')

    def test_translation_marker_survives(self):
        self.assertEqual(
            sc.strip_sdh_descriptors("[ÇEVİRİ EKSİK]"), "[ÇEVİRİ EKSİK]")

    def test_non_latin_signs_still_need_positive_evidence(self):
        # Denetim 2026-08-21 madde 38: Latin dışı alfabede parantez tek başına
        # kanıt değil; biçim kuralı oraya karışmamalı.
        for sign in ("東京都庁", "Мэрия Москвы", "서울시청"):
            with self.subTest(sign=sign):
                self.assertFalse(sc._bracket_shape_is_label(sign))


class ShapeRuleUnitTest(unittest.TestCase):
    """Kuralın kendi sınırları."""

    def test_bare_text_is_unaffected(self):
        # Parantez sinyali yoksa kural çalışmaz.
        self.assertFalse(sc.is_sdh_descriptor("Keçi melemesi"))
        self.assertTrue(
            sc.is_sdh_descriptor("Keçi melemesi", bracketed=True))

    def test_standalone_flag_gates_the_mixed_case_branch(self):
        self.assertTrue(sc._bracket_shape_is_label("Keçi melemesi"))
        self.assertFalse(
            sc._bracket_shape_is_label("Keçi melemesi", standalone=False))

    def test_uppercase_branch_ignores_the_standalone_flag(self):
        self.assertTrue(
            sc._bracket_shape_is_label("KEDİ MİYAVLAR", standalone=False))

    def test_long_content_is_never_a_label(self):
        self.assertFalse(sc._bracket_shape_is_label("a " * 40))
        self.assertFalse(sc._bracket_shape_is_label("Bir iki üç dört beş"))


if __name__ == "__main__":
    unittest.main()
