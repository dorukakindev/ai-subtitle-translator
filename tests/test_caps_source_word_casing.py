# -*- coding: utf-8 -*-
"""BÜYÜK HARF kaynakta İngilizce sözcüğe Türkçe I→ı uygulanması."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class SourceWordsKeepTheirOwnCasingTest(unittest.TestCase):
    """The Cruise-eng.srt: kaynak baştan sona BÜYÜK HARF closed-caption.
    Cümle düzenine indirirken 'VILLAGE' → 'vıllage', 'PAINE' → 'paıne',
    'TWAIN' → 'twaın' oluyordu; teslim denetimi 11 cue'yu bozuk token diye
    işaretledi ve dosya yapısal denetimden geçemedi. Kaynaktan taşınan
    sözcük hedef dilin değil KENDİ dilinin küçültme kuralına tabidir.
    """

    def test_an_english_place_name_is_not_dotless(self):
        self.assertEqual(
            g._tr_sentence_case("GREENWICH VILLAGE, İNSANLIK TARİHİNDE",
                                "GREENWICH VILLAGE, ONE OF THOSE RARE"),
            "Greenwich village, insanlık tarihinde")

    def test_an_english_surname_with_a_turkish_suffix(self):
        self.assertEqual(
            g._tr_sentence_case("THOMAS PAINE'İN ÖLDÜĞÜ YERDEN",
                                "FROM WHERE THOMAS PAINE DIES."),
            "Thomas paine'in öldüğü yerden")

    def test_a_hyphenated_compound_splits_by_origin(self):
        # 'ANTI' kaynaktaki 'ANTI-CRUISE'tan, 'GEZINTI' Türkçe.
        self.assertEqual(
            g._tr_sentence_case("ANTI-GEZINTI NEDEN BU KADAR",
                                "WHY IS THE ANTI-CRUISE SO AVARICIOUS"),
            "Anti-gezinti neden bu kadar")

    def test_a_turkish_word_still_gets_the_turkish_rule(self):
        # Kaynakta geçmeyen sözcükte I→ı korunmalı; yoksa 'kiz' çıkar.
        self.assertEqual(
            g._tr_sentence_case("KIZ KARDEŞİM GELDİ", "MY SISTER ARRIVED"),
            "Kız kardeşim geldi")
        self.assertEqual(
            g._tr_sentence_case("IŞIK YANDI", "THE LIGHT CAME ON"),
            "Işık yandı")

    def test_an_abbreviation_keeps_its_upper_case(self):
        self.assertEqual(
            g._tr_sentence_case("ABD'DE YAŞIYOR", "HE LIVES IN THE USA"),
            "ABD'de yaşıyor")

    def test_a_source_token_is_recognised_case_insensitively(self):
        self.assertTrue(g._token_comes_from_source("VILLAGE", {"Village"}))
        self.assertFalse(g._token_comes_from_source("KIZ", {"SISTER"}))

    def test_a_turkish_lettered_token_is_never_source(self):
        # 'ŞEHIR' ASCII değil: kaynakta görünse bile Türkçe sayılır.
        self.assertFalse(g._token_comes_from_source("ŞEHIR", {"ŞEHIR"}))


if __name__ == "__main__":
    unittest.main()


class LockedTermsRestoreProperNounCasingTest(unittest.TestCase):
    """Kaynağı baştan sona BÜYÜK HARF olan dosyada hangi sözcüğün özel ad
    olduğu metinden anlaşılmaz: 'THE BRAIN WITH DAVID EAGLEMAN' içinde hepsi
    aynı görünür. Kaynaktan gelen sözcük küçük harfe iniyor ve
    'david eagleman' çıkıyordu.

    Dosyanın kilitli terim sözlüğü doğru yazımı zaten taşıyor; geçişe o
    sözlük iletilmiyordu. 386 ham yedeğe geçiş tek başına uygulanarak
    ölçüldü: BÜYÜK HARF indirme 5 dosyada 1.258 cue'ya dokunuyor.
    """

    LOCKED = {"David Eagleman": "David Eagleman",
              "Greenwich Village": "Greenwich Village",
              "Thomas Paine": "Thomas Paine"}

    def _casing(self):
        return g._locked_term_word_casing(self.LOCKED)

    def test_a_person_keeps_both_capitals(self):
        self.assertEqual(
            g._tr_sentence_case('ANONSÇU: "DAVID EAGLEMAN İLE BEYİN"',
                                'ANNOUNCER: "THE BRAIN WITH DAVID EAGLEMAN"',
                                self._casing()),
            'Anonsçu: "David Eagleman ile beyin"')

    def test_a_place_keeps_its_capital(self):
        self.assertEqual(
            g._tr_sentence_case("GREENWICH VILLAGE, İNSANLIK TARİHİNDE",
                                "GREENWICH VILLAGE, ONE OF THOSE RARE",
                                self._casing()),
            "Greenwich Village, insanlık tarihinde")

    def test_a_turkish_suffix_still_attaches(self):
        self.assertEqual(
            g._tr_sentence_case("THOMAS PAINE'İN ÖLDÜĞÜ YERDEN",
                                "FROM WHERE THOMAS PAINE DIES.",
                                self._casing()),
            "Thomas Paine'in öldüğü yerden")

    def test_turkish_words_are_unaffected_by_the_map(self):
        casing = self._casing()
        self.assertEqual(
            g._tr_sentence_case("KIZ KARDEŞİM GELDİ", "MY SISTER ARRIVED",
                                casing), "Kız kardeşim geldi")
        self.assertEqual(
            g._tr_sentence_case("IŞIK YANDI", "THE LIGHT CAME ON", casing),
            "Işık yandı")

    def test_without_locked_terms_the_old_behaviour_stands(self):
        self.assertEqual(
            g._tr_sentence_case("GREENWICH VILLAGE, İNSANLIK TARİHİNDE",
                                "GREENWICH VILLAGE, ONE OF THOSE RARE"),
            "Greenwich village, insanlık tarihinde")

    def test_an_all_caps_source_term_carries_no_casing_information(self):
        # Kilitli terimin KAYNAK yazımı tamamı büyük harfse bilgi taşımaz.
        casing = g._locked_term_word_casing({"GREENWICH VILLAGE": "Greenwich Village"})
        self.assertEqual(casing.get("village"), "Village")

    def test_an_empty_map_is_safe(self):
        self.assertEqual(g._locked_term_word_casing({}), {})
        self.assertEqual(g._locked_term_word_casing(None), {})
