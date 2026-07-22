"""_has_turkish_negation genişletmesi — bkz. plans/olumsuzluk-validator-brief.md.

İki boşluk kapatılıyor:
  1) cıplak olumsuz emir kipi (`bakma`, `yaklaşma`, `Sevinme,` ...) tümce/dize
     sonunda durur (Türkçe SOV) — isimlerden (`elma`, `sinema`, `krema`) ayırt
     etmek için konum (noktalama/satır sonu) şart.
  2) `yok` + koşaç ekleri (`yoktur`, `yoksa`, `yokmuş`, ...) — `yokuş`, `yoksul`,
     `yokluk` gibi alakasız kelimelere taşmaması için SINIRLI alternasyon.

En kritik testler: test_noun_ending_in_ma_not_negation (tuzak) ve
test_genuine_negation_drop_still_caught (guard hâlâ çalışıyor mu).
"""
import unittest

import hybrid_translate as ht


class BareImperativeNegationTest(unittest.TestCase):
    def test_bare_imperative_negation(self):
        self.assertTrue(ht._has_turkish_negation("Ona bakma."))

    def test_bare_imperative_before_comma(self):
        self.assertTrue(ht._has_turkish_negation("Sevinme, ey Filistin toprağı,"))

    def test_bare_imperative_multiline(self):
        self.assertTrue(ht._has_turkish_negation("Ona bakma,\nyalvarırım."))

    def test_noun_ending_in_ma_not_negation(self):
        # TUZAK TESTİ: "elma" -ma ile bitiyor ama isim, olumsuzluk değil.
        self.assertFalse(ht._has_turkish_negation("Elma ye."))

    def test_noun_sinema_not_negation(self):
        # TUZAK TESTİ: "sinema" -ma ile bitiyor ama isim, olumsuzluk değil.
        self.assertFalse(ht._has_turkish_negation("Sinema iyiydi."))

    def test_krema_not_negation(self):
        self.assertFalse(ht._has_turkish_negation("Kremayı getir."))


class YokCopulaNegationTest(unittest.TestCase):
    def test_yoktur_is_negation(self):
        # ASIL REGRESYON — Salome dosyasındaki 8x "yoktur" vakası.
        self.assertTrue(ht._has_turkish_negation("Başka aşk yoktur."))

    def test_yoksa_is_negation(self):
        self.assertTrue(ht._has_turkish_negation("Yoksa gelme."))

    def test_yokmus_is_negation(self):
        self.assertTrue(ht._has_turkish_negation("Kimse yokmuş."))

    def test_yokus_not_negation(self):
        # TUZAK TESTİ: "yokuş" (uphill) — yok'un koşaç eki değil.
        self.assertFalse(ht._has_turkish_negation("Yokuş çıktık."))

    def test_yoksul_not_negation(self):
        # TUZAK TESTİ: "yoksul" (poor) — yok'un koşaç eki değil.
        self.assertFalse(ht._has_turkish_negation("Yoksul bir ülke."))

    def test_yokluk_not_negation(self):
        self.assertFalse(ht._has_turkish_negation("Yokluğunda geldi."))


class PolishValidatorEndToEndTest(unittest.TestCase):
    def test_french_oui_to_hayir_is_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Evet, Paul, mümkün.",
            "Hayır, Paul, mümkün.",
            source_text="Oui, Paul, c'est possible.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_polarity")

    def test_french_oui_to_hayir_is_flagged_for_critic(self):
        reasons = ht._common_term_mistranslation_reasons(
            "Oui, Paul, c'est possible.",
            "Hayır, Paul, mümkün.",
        )
        self.assertIn("EXPLICIT_ANSWER_POLARITY_FLIP", reasons)

    def test_do_not_look_suggestion_accepted(self):
        # Polish "Ona bak." -> "Ona bakma." önerisini artık source_negation ile
        # reddetmemeli — çıplak emir artık tanınıyor.
        ok, reason = ht.validate_polish_candidate(
            "Ona bak.",
            "Ona bakma.",
            source_text="Do not look at her.",
        )
        self.assertTrue(ok, msg=reason)

    def test_genuine_negation_drop_still_caught(self):
        # Guard hâlâ çalışıyor mu: gerçek bir olumsuzluk kaybı hâlâ reddedilmeli.
        ok, reason = ht.validate_polish_candidate(
            "Ona bakma.",
            "Ona bak.",
            source_text="Do not look at her.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_negation")


if __name__ == "__main__":
    unittest.main()
