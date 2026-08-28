# -*- coding: utf-8 -*-
"""Sözlük hedefi AÇIKLAMA ise altyazı metnine yazılamaz.

Zincir (2026-08-28 denetimi, her halkası ölçüldü):
Yardımcı Analiz `recurring_terms` üretiyor → önbellekteki 11.894 terimin
247'sinde noktalı virgüllü gloss var (`hubris → "hybris; ilk kullanımda
'kibir' açıklanmalı"`) → `merge_glossary_from_analysis` proje hafızasına
yazıyor → `get_locked_glossary` kilitli terim olarak veriyor →
`_locked_term_residue_plan` (yanlış, DOĞRU=gloss) çifti kuruyor → yardımcı
model satırı yeniden yazıyor → `_validate_term_normalize_candidate` GEÇİRİYOR,
çünkü kuralı "terim DIŞINDAKİ metin aynı kalmalı" ve gloss zaten terimin
yerine geçen metin.

İki katman düzeltildi:
  1. Sanitizasyon TIRNAKLI gloss'u kırpıyordu (`'Stronsiyum'; …` →
     `Stronsiyum`) ama TIRNAKSIZ olanı geçiriyordu (`Demos; …`).
  2. Kilitli terim yolu hiç sanitize etmiyordu.
"""
import unittest

import hybrid_translate as ht
import subtitle_translator_gui as gui


class UsableTargetTest(unittest.TestCase):
    def test_unquoted_gloss_is_trimmed_to_the_term(self):
        for target, expected in (
                ("hybris; ilk kullanımda kibir açıklanmalı", "hybris"),
                ("pentangle; beş köşeli yıldız sembolü", "pentangle"),
                ("Demos; oyunda halkı temsil eden kişileştirme", "Demos"),
                ("kan parası; imparatorluk sömürüsünden gelen para",
                 "kan parası"),
                ("The Wicker Man; özel kültürel gönderme", "The Wicker Man")):
            with self.subTest(target=target[:28]):
                self.assertEqual(ht.glossary_usable_target(target), expected)

    def test_prose_target_yields_nothing(self):
        for target in ("Özel ad olarak 'Thales'",
                       "Bağlama göre evren",
                       "kâse (Kutsal Kâse anlamında kullanılmalı)",
                       "beş yatak odalı şehir evi ve bahçesi",
                       "Genel kullanımda kardeşler",
                       ""):
            with self.subTest(target=target[:28]):
                self.assertIsNone(ht.glossary_usable_target(target))

    def test_real_terms_pass_through_unchanged(self):
        for target in ("Truva", "Aristoteles", "kan parası", "zar oyunu",
                       "Gotik", "masal anlatıcısı", "Väinö", "pentangle"):
            with self.subTest(target=target):
                self.assertEqual(ht.glossary_usable_target(target), target)


class SanitizerTrimsUnquotedGlossTest(unittest.TestCase):
    def test_semicolon_gloss_no_longer_survives(self):
        got = ht.sanitize_glossary_for_turkish(
            {"pentangle": "pentangle; beş köşeli yıldız sembolü",
             "Demos": "Demos; oyunda halkı temsil eden kişileştirme"},
            target_language="Turkish")
        self.assertEqual(got.get("pentangle"), "pentangle")
        self.assertEqual(got.get("Demos"), "Demos")

    def test_quoted_gloss_still_trimmed(self):
        """Var olan davranış korunmalı."""
        got = ht.sanitize_glossary_for_turkish(
            {"strontium": "'Stronsiyum'; kemik ve diş minesindeki element"},
            target_language="Turkish")
        self.assertEqual(got.get("strontium"), "Stronsiyum")

    def test_prose_target_is_dropped_not_written(self):
        got = ht.sanitize_glossary_for_turkish(
            {"the universe": "Bağlama göre 'evren'; anlatının ana kavramı"},
            target_language="Turkish")
        self.assertNotIn("the universe", got)

    def test_clean_glossary_is_untouched(self):
        clean = {"Troy": "Truva", "Aristotle": "Aristoteles"}
        self.assertEqual(
            ht.sanitize_glossary_for_turkish(dict(clean),
                                             target_language="Turkish"),
            clean)


class LockedTermPlanRejectsProseTest(unittest.TestCase):
    """Kilitli terim yolu artık kendi kapısını taşıyor."""

    BLOCKS = [("1", "00:00:01,000 --> 00:00:02,000", "Bu bir hubris örneği.")]
    SRC = {"1": "This is a case of hubris."}

    def test_gloss_target_is_trimmed_before_use(self):
        plan = gui._locked_term_residue_plan(
            self.BLOCKS, self.SRC,
            {"hubris": "hybris; ilk kullanımda kibir açıklanmalı"})
        for fixes in plan.values():
            for _wrong, correct in fixes:
                self.assertEqual(correct, "hybris")

    def test_prose_target_produces_no_plan(self):
        plan = gui._locked_term_residue_plan(
            self.BLOCKS, self.SRC,
            {"hubris": "Bağlama göre 'kibir'; ölçüsüz gurur anlamında"})
        self.assertEqual(plan, {})

    def test_clean_term_still_planned(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Troy şehrine gitti.")]
        plan = gui._locked_term_residue_plan(
            blocks, {"1": "He went to Troy."}, {"Troy": "Truva"})
        self.assertTrue(plan)
        for fixes in plan.values():
            for _wrong, correct in fixes:
                self.assertEqual(correct, "Truva")


class ValidatorWouldHavePassedTheGlossTest(unittest.TestCase):
    """Doğrulayıcı bu sınıfı YAKALAMIYOR — kapı yukarıda olmak zorunda.

    Bu test kaydı tutuyor: aday doğrulayıcısına güvenip yukarıdaki
    guard'ları kaldırmak, gloss'un metne yazılmasına geri döner.
    """

    def test_validator_accepts_a_gloss_substitution(self):
        ok, _reason = gui._validate_term_normalize_candidate(
            "Bu bir hubris örneğidir.",
            "Bu bir hybris; ilk kullanımda kibir açıklanmalı örneğidir.",
            [("hubris", "hybris; ilk kullanımda kibir açıklanmalı")])
        self.assertTrue(ok)

    def test_validator_still_rejects_unrelated_rewrites(self):
        ok, reason = gui._validate_term_normalize_candidate(
            "Troy şehrine gitti.", "Truva kentine vardı.", [("Troy", "Truva")])
        self.assertFalse(ok)
        self.assertEqual(reason, "unrelated_text_changed")


if __name__ == "__main__":
    unittest.main()
