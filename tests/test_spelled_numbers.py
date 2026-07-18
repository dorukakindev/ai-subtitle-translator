"""Yazıyla yazılmış sayı tespiti (bkz. plans/yaziyla-sayi-tespiti-brief.md).

The Blood of Hussain #384: kaynak "fourteen hundred years ago" -> çeviri
"on dört yüz yıl önce" (doğrusu "bin dört yüz"). Eski _numeric_token_mismatch
yalnızca RAKAM görüyordu; bu satır hiç şüpheli listeye girmiyordu. Bu testler
yeni _en_spelled_numbers / _tr_spelled_numbers / _spelled_number_mismatch
tespit yolunu ve run_validators'a eklenen SPELLED_NUMBER_MISMATCH reason'ını
kilitler. validate_polish_candidate'a (öneri filtresi) DOKUNULMADI.
"""
import unittest
from types import SimpleNamespace

import hybrid_translate as ht


class EnSpelledNumberParserTest(unittest.TestCase):
    def test_en_parser_multiplier(self):
        self.assertEqual(ht._en_spelled_numbers("fourteen hundred years ago"), [1400])

    def test_en_parser_simple(self):
        self.assertEqual(ht._en_spelled_numbers("thirteen wounds"), [13])

    def test_en_parser_hyphen(self):
        self.assertEqual(ht._en_spelled_numbers("twenty-five"), [25])

    def test_en_parser_no_numbers(self):
        self.assertEqual(ht._en_spelled_numbers("scarred your face"), [])

    def test_en_parser_bare_one_skipped(self):
        self.assertEqual(ht._en_spelled_numbers("one of them"), [])


class EnHalfSpelledNumberTest(unittest.TestCase):
    """'half a <çarpan>' -> çarpan/2 (bkz. plans/sozluk-gloss-ve-half-sayi-brief.md,
    Salome #921: 'half a hundred moons' -> 50 iken 'hundred' tek başına 100
    okunuyordu, 'half' tamamen yok sayılıyordu). Diğer tüm 'half' kullanımları
    belirsizdir -> []."""

    def test_half_a_hundred(self):
        # ASIL REGRESYON: bugüne kadar [100] dönüyordu, doğrusu 50.
        self.assertEqual(ht._en_spelled_numbers("half a hundred"), [50])

    def test_half_a_thousand(self):
        self.assertEqual(ht._en_spelled_numbers("half a thousand"), [500])

    def test_half_the_kingdom_ignored(self):
        self.assertEqual(ht._en_spelled_numbers("half the kingdom"), [])

    def test_half_a_dozen_ignored(self):
        # 'dozen' _EN_NUMBER_WORDS'te yok - kasıtlı olarak desteklenmiyor.
        self.assertEqual(ht._en_spelled_numbers("half a dozen"), [])

    def test_half_odd_ordering_ignored(self):
        # 'half a <çarpan>' kalıbına uymayan tuhaf sıralama -> belirsiz, [].
        self.assertEqual(ht._en_spelled_numbers("one and a half hundred"), [])


class TrSpelledNumberParserTest(unittest.TestCase):
    def test_tr_parser_canonical(self):
        self.assertEqual(ht._tr_spelled_numbers("bin dört yüz"), [1400])

    def test_tr_parser_suffixed_yuz_ignored(self):
        self.assertEqual(ht._tr_spelled_numbers("yüzünü yaralamış"), [])

    def test_tr_parser_suffixed_bir_ignored(self):
        self.assertEqual(ht._tr_spelled_numbers("birini gördüm"), [])


class SpelledNumberMismatchTest(unittest.TestCase):
    def test_384_regression(self):
        self.assertTrue(ht._spelled_number_mismatch(
            "The true revolution happened\nfourteen hundred years ago",
            "Gerçek devrim, on dört yüz yıl önce",
        ))

    def test_384_corrected_passes(self):
        self.assertFalse(ht._spelled_number_mismatch(
            "The true revolution happened\nfourteen hundred years ago",
            "Gerçek devrim, bin dört yüz yıl önce",
        ))

    def test_source_gated_no_false_positive(self):
        # TUZAK: "yüz" hem 100 hem "face" - kaynakta yazıyla sayı yoksa hiç taranmaz.
        self.assertFalse(ht._spelled_number_mismatch(
            "The sword of Yazid\nhas scarred your face.",
            "Yezid'in kılıcı\nyüzünü yaralamış.",
        ))

    def test_digit_translation_accepted(self):
        self.assertFalse(ht._spelled_number_mismatch(
            "fourteen hundred", "1400 yıl önce",
        ))

    # Salome #921 (bkz. plans/sozluk-gloss-ve-half-sayi-brief.md): kaynak metin ve
    # çeviriler dosyadan birebir alındı (aşağıdaki iki değeri kesin doğrulamak için).
    _SALOME_921_SRC = "They are even as half a hundred moons\ncaught in a golden net."

    def test_921_correct_translation_passes(self):
        # ASIL REGRESYON: 'half a hundred' eskiden 100 okunuyordu ve doğru çeviri
        # ('Elli' = 50) yanlış alarm alıyordu.
        self.assertFalse(ht._spelled_number_mismatch(
            self._SALOME_921_SRC, "Elli ay gibidir onlar,",
        ))

    def test_921_wrong_translation_caught(self):
        self.assertTrue(ht._spelled_number_mismatch(
            self._SALOME_921_SRC, "Altmış ay gibidir onlar,",
        ))


class RunValidatorsSpelledNumberTest(unittest.TestCase):
    def test_run_validators_flags_384_case(self):
        cues = [SimpleNamespace(
            index=384,
            text="The true revolution happened\nfourteen hundred years ago",
        )]
        blocks = [(384, "00:00:01,000 --> 00:00:02,000", "Gerçek devrim, on dört yüz yıl önce")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertIn("SPELLED_NUMBER_MISMATCH", reasons["384"])

    def test_run_validators_no_false_positive_on_face_trap(self):
        cues = [SimpleNamespace(index=6, text="The sword of Yazid has scarred your face.")]
        blocks = [(6, "00:00:01,000 --> 00:00:02,000", "Yezid'in kılıcı yüzünü yaralamış.")]

        hits = ht.run_validators(blocks, cues)
        reasons = {str(idx): reason for idx, _ts, _text, reason in hits}

        self.assertNotIn("SPELLED_NUMBER_MISMATCH", reasons.get("6", ""))


if __name__ == "__main__":
    unittest.main()
