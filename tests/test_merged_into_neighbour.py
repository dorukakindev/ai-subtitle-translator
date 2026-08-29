# -*- coding: utf-8 -*-
"""Cümle kuyruğu cue'su "eksik çeviri" diye kör işaretlenmemeli.

Yayın altyazısı bir cümleyi iki cue'ya böler (`...listen to` / `him?`).
Türkçe SOV olduğu için model cümlenin tamamını ilk cue'ya yazıp ikincisini
boş bırakabiliyor; boru hattı ikinciyi eksik çeviri sayıp dosyayı
karantinaya alıyor. Onarım da kısmi cümle grubunu bilerek erteliyor, yani
cue eksik kalıyor.

Arşiv ölçümü (552 çevrilmemiş cue, 340 kaynak/teslim çifti):
  - küçük harf şartı YOKKEN 109 cue işaretleniyordu ve `Buenas noches!`
    gibi bağımsız replikler de giriyordu;
  - şartla 46 cue / 24 dosya kalıyor, elle bakılan örneklerin tamamı
    gerçek cümle kuyruğu.

Sınıf `bilgi` düzeyinde: yalnız "önce önceki cue'ya bak" der. Cue
düşürmez, sert hata kapısını gevşetmez — testler ikisini de kilitliyor.
"""
import unittest

import subtitle_translator_gui as gui


def _rows(*triples):
    return [(str(i), f"00:00:{i:02d},000 --> 00:00:{i + 1:02d},000", t)
            for i, t in triples]


class MergedIntoNeighbourTest(unittest.TestCase):
    def test_sentence_tail_is_flagged(self):
        src = _rows((1, ">> We can find shelter in the"), (2, "forest."))
        out = _rows((1, "Ormanda sığınak bulabiliriz."), (2, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), ["2"])

    def test_hata_marker_counts_too(self):
        src = _rows((1, "choose a leader and listen to"), (2, "him?"))
        out = _rows((1, "onu dinlediğinizde ne olur?"), (2, "[HATA]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), ["2"])

    def test_independent_line_is_not_flagged(self):
        """Ölçümdeki tek gerçek yanlış pozitif sınıfı."""
        src = _rows((1, "<i>are the first people of the</i>"),
                    (2, "Buenas noches!"))
        out = _rows((1, "<i>ilk insanları</i>"), (2, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])

    def test_finished_source_sentence_is_not_flagged(self):
        src = _rows((1, "Cümle burada bitti."), (2, "yeni parça."))
        out = _rows((1, "Cümle burada bitti."), (2, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])

    def test_neighbour_also_missing_is_not_flagged(self):
        src = _rows((1, "training well and do not try to"),
                    (2, "do everything on your own."))
        out = _rows((1, "[ÇEVİRİ EKSİK]"), (2, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])

    def test_neighbour_left_half_finished_is_not_flagged(self):
        """Komşu da yarım bittiyse birleşme iddiası yok."""
        src = _rows((1, "people find meaning in the"),
                    (2, "transition between life and death."))
        out = _rows((1, "insanların anlam bulmasına"), (2, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])

    def test_first_cue_is_never_flagged(self):
        src = _rows((1, "boundaries."))
        out = _rows((1, "[ÇEVİRİ EKSİK]"))
        self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])

    def test_empty_input_is_safe(self):
        for src, out in (([], []), (None, None), (_rows((1, "x")), [])):
            with self.subTest(src=src):
                self.assertEqual(gui._merged_into_neighbour_ids(src, out), [])


class TailDetectorTest(unittest.TestCase):
    def test_lowercase_start_is_a_tail(self):
        for text in ("him?", "forest.", "majesty?", "between life and death.",
                     '"hoptite kalos", "menino bonito".',
                     "<i>for another metaphorical system.</i>"):
            with self.subTest(text=text[:28]):
                self.assertTrue(gui._starts_like_a_sentence_tail(text))

    def test_uppercase_start_is_not_a_tail(self):
        for text in ("Buenas noches!", "In 1930, 80 million Americans",
                     "How We Got to Now", "NARRATOR: Listen."):
            with self.subTest(text=text[:28]):
                self.assertFalse(gui._starts_like_a_sentence_tail(text))

    def test_letterless_text_is_not_a_tail(self):
        for text in ("", None, "...", "♪♪♪", "123"):
            with self.subTest(text=text):
                self.assertFalse(gui._starts_like_a_sentence_tail(text))


class GateIsUntouchedTest(unittest.TestCase):
    """Sınıf bilgi düzeyinde: teslim kapısını sertleştirmez."""

    def test_class_is_registered_as_info(self):
        confidence, _title, _fix = gui._FINDING_CLASSES[
            "merged_into_neighbour_ids"]
        self.assertEqual(confidence, "bilgi")

    def test_hard_error_gate_ignores_it(self):
        self.assertFalse(gui._delivery_scan_has_hard_error(
            {"merged_into_neighbour_ids": ["1", "2", "3"]}))


if __name__ == "__main__":
    unittest.main()
