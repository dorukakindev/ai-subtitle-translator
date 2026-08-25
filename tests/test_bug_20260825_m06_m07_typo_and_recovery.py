# -*- coding: utf-8 -*-
"""Madde 6 ve 7: hece tekrarı kuralı ve kurtarma türü adlandırması."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui

TS = "00:00:01,000 --> 00:00:03,000"


def _findings(word, vocabulary):
    blocks = [("1", TS, word)]
    blocks += [(str(i + 2), TS, other) for i, other in enumerate(vocabulary)]
    return gui._repeated_head_typo_ids(blocks)


class ARepeatedSyllableIsNotAlwaysATypoTest(unittest.TestCase):
    """Kural 7+ harfli sözcükte ilk 2-3 harfin tekrarına bakıyordu ve
    kırpılmış biçim dosyada geçiyorsa yazım hatası sayıyordu.

    377 gerçek teslimde ürettiği 9 bulgunun 9'u da yanlıştı: 'birbirinden'
    karşılıklılık zamiri, 'durdur-' ise ettirgen çatı. Daraltmadan sonra
    aynı arşivde bulgu 0, sentetik gerçek hatalar hâlâ yakalanıyor.
    """

    def test_the_reciprocal_pronoun_is_left_alone(self):
        self.assertEqual(_findings("birbirinden", ["birinden"]), [])

    def test_the_causative_stem_is_left_alone(self):
        for word, trimmed in (("durduruyoruz", "duruyoruz"),
                              ("durduramıyorum", "duramıyorum"),
                              ("durdururlar", "dururlar"),
                              ("durduruyorsun", "duruyorsun"),
                              ("durduracağım", "duracağım")):
            with self.subTest(word=word):
                self.assertEqual(_findings(word, [trimmed]), [])

    def test_a_real_typo_is_still_caught(self):
        self.assertEqual(_findings("neneredeyse", ["neredeyse"]),
                         [("1", "neneredeyse", "neredeyse")])
        self.assertEqual(_findings("kokorkunçtu", ["korkunçtu"]),
                         [("1", "kokorkunçtu", "korkunçtu")])

    def test_a_typo_whose_target_is_absent_is_not_reported(self):
        # Dosya bazlı ölçüt korunur: kırpılmış biçim geçmiyorsa susulur.
        self.assertEqual(_findings("neneredeyse", ["başka"]), [])


class TheRecoveryIsNamedByWhatActuallyHappenedTest(unittest.TestCase):
    """Etiket her kısmi eksikte 'kesilme' diyordu ve yanıtın token sınırına
    takıldığı sanılıyordu. Ölçüm bütçeyi suçsuz buldu: 284.076 cue'da cue
    başına en yüksek çıktı 103 token (bütçe 120) ve 6.917 chunk'ın hiçbiri
    5.300'lük bütçeyi aşmıyor; en dolu chunk bütçenin %47'si.

    Gerçek kesilmede eksikler dizinin sonunda toplanır; dağınıksa model cue
    atlamıştır. İkisi ayrı sorundur ve ayrı adlandırılır.
    """

    ITEMS = [{"i": str(i)} for i in range(1, 11)]

    def test_a_missing_tail_is_truncation(self):
        self.assertEqual(
            gui._missing_recovery_kind(self.ITEMS, self.ITEMS[7:]),
            "kesilme kurtarması")

    def test_a_single_missing_last_cue_is_truncation(self):
        self.assertEqual(
            gui._missing_recovery_kind(self.ITEMS, self.ITEMS[-1:]),
            "kesilme kurtarması")

    def test_scattered_gaps_are_skipped_cues(self):
        self.assertEqual(
            gui._missing_recovery_kind(
                self.ITEMS, [self.ITEMS[2], self.ITEMS[7]]),
            "atlanan cue kurtarması")

    def test_a_missing_head_is_not_truncation(self):
        self.assertEqual(
            gui._missing_recovery_kind(self.ITEMS, self.ITEMS[:3]),
            "atlanan cue kurtarması")

    def test_everything_missing_is_still_the_provider(self):
        self.assertEqual(
            gui._missing_recovery_kind(self.ITEMS, self.ITEMS),
            "sağlayıcı kurtarması")

    def test_empty_input_does_not_crash(self):
        self.assertEqual(gui._missing_recovery_kind([], []), "kurtarma")


if __name__ == "__main__":
    unittest.main()
