"""Tests for is_source_likely_turkish preflight."""
import unittest
import hybrid_translate as ht
from pathlib import Path

_TR_TEXT = (
    "Burası New York'un en büyük mahallelerinden biri. Great Neck'te"
    " bir sürü güzel ev var. Bu akşam oraya gideceğiz ve harika"
    " bir akşam yemeği yiyeceğiz. Sonra da şehir merkezinde"
    " dolaşacağız. Bu arada, dedektif yeni bir ipucu buldu."
    " Ona göre katil çok yakında olabilir. Şimdi harekete geçmeliyiz."
    " Polis her yeri aradı ama hiçbir şey bulamadı."
)

_EN_TEXT = (
    "This is one of the largest neighborhoods in New York. There are"
    " many beautiful houses in Great Neck. Tonight we will go there"
    " and have a wonderful dinner. Then we will walk around downtown."
    " Meanwhile, the detective found a new clue. According to him,"
    " the killer might be very close. We must act now."
    " The police searched everywhere but found nothing."
)


class PreflightTurkishTest(unittest.TestCase):

    def test_filename_tr_srt_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Capturing..._tr.srt")
        )

    def test_filename_dot_tr_srt_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show.S01E01.Tr.srt")
        )

    def test_filename_turkish_word_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show Turkish.srt")
        )

    def test_filename_turkce_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show Türkçe.srt")
        )

    def test_english_content_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text=_EN_TEXT, filename="Show.S01E01.en.srt")
        )

    def test_english_content_no_filename_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text=_EN_TEXT)
        )

    def test_turkish_content_with_place_names_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(text=_TR_TEXT, filename="Show.S01E01.en.srt")
        )

    def test_turkish_content_no_filename_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(text=_TR_TEXT)
        )

    def test_empty_text_not_detected(self):
        self.assertFalse(
            ht.is_source_likely_turkish(filename="Show.S01E01.srt")
        )

    def test_short_text_not_enough_content(self):
        self.assertFalse(
            ht.is_source_likely_turkish(text="Merhaba nasılsın")
        )

    def test_filename_signal_with_empty_text_detected(self):
        self.assertTrue(
            ht.is_source_likely_turkish(filename="Show_turkish.srt")
        )

    def test_mixed_text_more_english_than_turkish_not_detected(self):
        mixed = (
            "This is mostly English text with just a few Turkish words like"
            " merhaba and teşekkürler. The rest of this paragraph is entirely"
            " in English so that the overall ratio of Turkish content stays"
            " very low. We want to make sure that lightweight Turkish token"
            " presence does not accidentally trigger the preflight detector."
            " There is absolutely nothing in this text that suggests a full"
            " Turkish subtitle file. It is just an English sentence with a"
            " couple of Turkish loanwords thrown in for testing purposes."
            " The great majority of the words here are plain English words."
        )
        self.assertFalse(
            ht.is_source_likely_turkish(text=mixed)
        )


if __name__ == "__main__":
    unittest.main()
