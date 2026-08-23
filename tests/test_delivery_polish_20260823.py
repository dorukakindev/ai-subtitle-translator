# -*- coding: utf-8 -*-
"""Teslim cilası: binlik ayracı ve sözcük değiştirmeyen yeniden sarma."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)
TS = "00:00:01,000 --> 00:00:06,000"


class ThousandsSeparatorTest(unittest.TestCase):
    """İngilizce binlik ayracı Türkçe biçime çevrilir — KAYNAĞA bakarak.

    202 gerçek teslimde ölçüldü: kaynak penceresi ±2 cue ile 19 gerçek
    binlik dönüşüyor, 15 gerçek ondalık (altın oran cue'ları) korunuyor,
    belirsiz vaka kalmıyor.
    """

    def test_an_english_thousands_group_becomes_turkish(self):
        out, changed = g._normalize_thousands_separators(
            [("49", TS, "1,200 yıldan uzun süredir")],
            {"49": "FOR OVER 1,200 YEARS"})
        self.assertEqual(out[0][2], "1.200 yıldan uzun süredir")
        self.assertEqual(changed, 1)

    def test_a_real_decimal_is_never_touched(self):
        # Altın oran: kaynakta '1.618', Türkçede '1,618' DOĞRU.
        out, changed = g._normalize_thousands_separators(
            [("491", TS, "oranı 1,618 olduğunu")],
            {"491": "the ratio is 1.618"})
        self.assertEqual(out[0][2], "oranı 1,618 olduğunu")
        self.assertEqual(changed, 0)

    def test_without_source_evidence_nothing_changes(self):
        out, changed = g._normalize_thousands_separators(
            [("900", TS, "kanıtsız 5,000 sayı")], {"900": "no number here"})
        self.assertEqual(out[0][2], "kanıtsız 5,000 sayı")
        self.assertEqual(changed, 0)

    def test_the_source_window_spans_neighbouring_cues(self):
        # Türkçe SOV sayıyı komşu cue'ya taşıyabilir.
        out, changed = g._normalize_thousands_separators(
            [("50", TS, "2,000 yıl sonra bile")],
            {"48": "So impressive that nearly 2,000 years later,"})
        self.assertEqual(out[0][2], "2.000 yıl sonra bile")
        self.assertEqual(changed, 1)

    def test_it_runs_in_the_turkish_delivery_path(self):
        source = inspect.getsource(g._prepare_upload_ready_blocks)
        self.assertIn("_normalize_thousands_separators(", source)
        marker = source.index("_normalize_thousands_separators(")
        self.assertIn("if is_turkish:", source[max(0, marker - 400):marker])


class RewrapKeepsEveryWordTest(unittest.TestCase):
    """Bütçe dolu ama satırlar kötü dağılmışsa kırılma noktası taşınır.

    139 gerçek teslim dosyasında (90.102 cue) 42 karakteri aşan satır
    13.527 -> 5.263; sözcük dizisi değişen cue sayısı 0.
    """

    LONG = ("Bu cümle oldukça uzun bir birinci satır taşıyor ve ikincisi kısa")

    def test_a_lopsided_pair_is_rebalanced(self):
        text = self.LONG + NL + "kalıyor."
        out = g.apply_line_breaks([("1", TS, text)])[0][2]
        self.assertLessEqual(
            max(g._visible_len(line) for line in out.split(NL)),
            max(g._visible_len(line) for line in text.split(NL)))

    def test_no_word_is_added_or_lost(self):
        text = self.LONG + NL + "kalıyor."
        out = g.apply_line_breaks([("1", TS, text)])[0][2]
        self.assertEqual(out.split(), text.split())

    def test_the_line_count_is_preserved(self):
        text = self.LONG + NL + "kalıyor."
        out = g.apply_line_breaks([("1", TS, text)])[0][2]
        self.assertEqual(len(out.split(NL)), 2)

    def test_dialogue_structure_is_never_rebalanced(self):
        text = ("- Bu birinci konuşmacının oldukça uzun olan repliğidir efendim"
                + NL + "- Kısa.")
        self.assertEqual(g._rebalanced_two_lines(text.split(NL)),
                         text.split(NL))

    def test_an_already_balanced_pair_is_left_alone(self):
        lines = ["Kısa bir satır.", "Bir diğeri."]
        self.assertEqual(g._rebalanced_two_lines(lines), lines)

    def test_a_rebalance_that_does_not_help_is_refused(self):
        # Tek sözcük 42'yi aşıyorsa hiçbir bölüm kurtarmaz.
        lines = ["A" * 60, "kısa"]
        self.assertEqual(g._rebalanced_two_lines(lines), lines)



class ConditionalSecondPersonTest(unittest.TestCase):
    """Koşul kipi -sAn hiç tanınmıyordu.

    `is_turkish_second_person_token` yalnız -sIn ve -DIn biçimlerini
    biliyordu; 'diyorsan', 'istiyorsan', 'gidersen' 2. tekil sayılmıyor ve
    hitap karışımı bu biçimi taşıyan röportajlarda görünmüyordu. 14 gerçek
    teslim dosyasında blok bazlı ölçüm: bilinen 6 hitap kaymasının
    yakalananı 3 -> 4, yanlış alarm %0,77 -> %0,79.
    """

    import subtitle_formats as _sf

    CONDITIONAL = ("diyorsan", "istiyorsan", "gidersen", "bakarsan",
                   "geliyorsan", "yaparsan")
    ORDINARY = ("insan", "Hasan", "susan", "kısan", "asan", "Ahsen",
                "ehven", "desen", "resen", "hasen")

    def test_analytic_conditionals_are_second_person(self):
        for word in self.CONDITIONAL:
            with self.subTest(word=word):
                self.assertTrue(self._sf.is_turkish_second_person_token(word))

    def test_ordinary_words_are_not(self):
        for word in self.ORDINARY:
            with self.subTest(word=word):
                self.assertFalse(self._sf.is_turkish_second_person_token(word))

    def test_the_existing_forms_still_work(self):
        for word in ("geliyorsun", "kazandın", "yaptın"):
            with self.subTest(word=word):
                self.assertTrue(self._sf.is_turkish_second_person_token(word))

    def test_the_bare_stem_trade_off_is_documented(self):
        # 'gelsen'/'olsan' bilinçli olarak DIŞARIDA: gevşetmek 'insan',
        # 'desen', 'Hasan' gibi sözcükleri yanlış pozitif yapıyor.
        self.assertFalse(self._sf.is_turkish_second_person_token("gelsen"))
        self.assertIn("takas kabul edildi",
                      inspect.getsource(self._sf))

    def test_both_consumers_read_the_shared_helper(self):
        import hybrid_translate as ht
        import subtitle_translator_gui as gui
        self.assertIs(gui._address_informal_suffix_token,
                      self._sf.is_turkish_second_person_token)
        self.assertIn("_sf_is_tr_second_person", inspect.getsource(ht))

if __name__ == "__main__":
    unittest.main()
