# -*- coding: utf-8 -*-
"""Etiket geri yükleme kaynağı cue NUMARASIYLA arıyordu.

Numara teslimde kayarsa (yeniden numaralama, cue birleştirme) arama boşa
düşüyor ve biçim etiketi sessizce geri konmuyor. Arşivde ölçüldü: kaynağı
tam sarmalı olduğu hâlde teslimi italiksiz kalan 32 cue'nun tamamı bu
yüzdendi — `restore_format_tags` o cue'lara DOĞRUDAN çağrıldığında etiketi
doğru geri koyuyordu, yani kusur fonksiyonda değil aramadaydı.

Zaman damgası artık yedek anahtar.
"""
import unittest

import subtitle_translator_gui as gui


class _Cue:
    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


class TimestampFallbackTest(unittest.TestCase):
    SRC = [_Cue("10", "00:00:01,000", "00:00:02,000", "<i>A whisper.</i>"),
           _Cue("11", "00:00:03,000", "00:00:04,000", "Plain line.")]

    def test_id_lookup_still_wins(self):
        blocks = [("10", "00:00:01,000 --> 00:00:02,000", "Bir fısıltı.")]
        got = gui._restore_tags_blocks(
            blocks, {"10": "<i>A whisper.</i>"}, self.SRC)
        self.assertEqual(got[0][2], "<i>Bir fısıltı.</i>")

    def test_renumbered_delivery_falls_back_to_timestamp(self):
        """Teslim numarası kaymış; zaman damgası tutuyor."""
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bir fısıltı.")]
        got = gui._restore_tags_blocks(
            blocks, {"10": "<i>A whisper.</i>"}, self.SRC)
        self.assertEqual(got[0][2], "<i>Bir fısıltı.</i>")

    def test_without_source_cues_behaviour_is_unchanged(self):
        """Kaynak cue'ları verilmezse eski davranış: numara tutmazsa yok."""
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bir fısıltı.")]
        got = gui._restore_tags_blocks(blocks, {"10": "<i>A whisper.</i>"})
        self.assertEqual(got[0][2], "Bir fısıltı.")

    def test_unmatched_timestamp_invents_nothing(self):
        blocks = [("1", "00:09:09,000 --> 00:09:10,000", "Alakasız.")]
        got = gui._restore_tags_blocks(
            blocks, {"10": "<i>A whisper.</i>"}, self.SRC)
        self.assertEqual(got[0][2], "Alakasız.")

    def test_plain_source_stays_plain(self):
        blocks = [("1", "00:00:03,000 --> 00:00:04,000", "Düz satır.")]
        got = gui._restore_tags_blocks(blocks, {"99": "x"}, self.SRC)
        self.assertEqual(got[0][2], "Düz satır.")

    def test_tuple_cues_are_accepted_too(self):
        src = [("10", "00:00:01,000 --> 00:00:02,000", "<i>A whisper.</i>")]
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bir fısıltı.")]
        got = gui._restore_tags_blocks(blocks, {"10": ""}, src)
        self.assertEqual(got[0][2], "<i>Bir fısıltı.</i>")


class MissingCueLogTest(unittest.TestCase):
    """Eksik cue log satırı kırpılmalı ve kaynağı da göstermeli.

    Kırpma yokken sağlayıcı çökmesinde tek satır ~30 KB oluyordu
    (4.473 eksik cue). Kutu açıklaması ayrıca "kaynak ve mevcut metni loga
    yazar" diyordu ama loga yalnız kimlik gidiyordu.
    """

    def test_shortener_collapses_and_trims(self):
        self.assertEqual(gui._shorten_for_log("kısa metin"), "kısa metin")
        self.assertEqual(
            gui._shorten_for_log("iki\nsatırlı   boşluklu  metin"),
            "iki satırlı boşluklu metin")
        long_value = gui._shorten_for_log("A" * 200)
        self.assertLessEqual(len(long_value), 60)
        self.assertTrue(long_value.endswith("…"))

    def test_empty_is_safe(self):
        self.assertEqual(gui._shorten_for_log(""), "")
        self.assertEqual(gui._shorten_for_log(None), "")

    def test_repair_log_truncates_the_id_list(self):
        import inspect
        source = inspect.getsource(gui._repair_untranslated_sync)
        self.assertIn("hata_indices[:12]", source)
        self.assertIn("_shorten_for_log", source)


if __name__ == "__main__":
    unittest.main()
