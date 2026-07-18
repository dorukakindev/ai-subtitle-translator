"""_has_word_merge / validate_polish_candidate — Görev 4 (future-quality-guards-brief.md).

Gerçek olay: Göbekli 2 (Portal) #183, polish geçişi 'ya törensel' iki kelimesini
'yatörensel' diye birleştirdi; _has_introduced_typo (çift-ilk-harf deseni) bunu
yakalamadı çünkü bu bir bitişme, çift-harf hatası değil.
"""
import unittest

import hybrid_translate as ht


class HasWordMergeTest(unittest.TestCase):
    def test_two_adjacent_words_merged_detected(self):
        self.assertTrue(ht._has_word_merge(
            "Burası ya törensel ya da bir alan.",
            "Burası yatörensel ya da bir alan.",
        ))

    def test_no_merge_when_new_word_already_in_old(self):
        self.assertFalse(ht._has_word_merge(
            "Çok uzun bir cümle burada duruyor.",
            "Uzun bir cümle burada.",
        ))

    def test_no_merge_for_unrelated_new_word(self):
        self.assertFalse(ht._has_word_merge(
            "Bu iyi bir örnektir.",
            "Bu harika bir örnektir.",
        ))

    def test_short_new_token_not_flagged(self):
        # 7 harften kısa token'lar kasıtlı muaf (yanlış-pozitif riskini azaltır).
        self.assertFalse(ht._has_word_merge("bir de öyle", "birde öyle"))

    def test_empty_inputs_safe(self):
        self.assertFalse(ht._has_word_merge("", "yeni metin"))
        self.assertFalse(ht._has_word_merge("eski metin", ""))


class ValidatePolishCandidateWordMergeTest(unittest.TestCase):
    def test_word_merge_suggestion_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Burası ya törensel ya da bir alandı.",
            "Burası yatörensel ya da bir alandı.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "word_merge")

    def test_ordinary_clean_polish_still_accepted(self):
        # Regresyon: kelime-birleştirme guard'ı sıradan, meşru düzeltmeleri
        # reddetmemeli.
        ok, reason = ht.validate_polish_candidate(
            "Bu arheologik bir buluntu.",
            "Bu arkeolojik bir buluntu.",
        )
        self.assertTrue(ok, msg=reason)


if __name__ == "__main__":
    unittest.main()
