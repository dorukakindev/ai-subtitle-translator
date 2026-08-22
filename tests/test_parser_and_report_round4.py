# -*- coding: utf-8 -*-
"""Derin denetim Tur 4 — madde 8, 9, 11, 12.

  8) BOM'suz UTF-16'da toplam NUL oranı eşiği Latin dışı alfabelerde çöküyor;
     CJK/Arapça kaynak sessizce mojibake oluyordu.
  9) WebVTT zaman satırında kesir alanı ZORUNLU tutuluyordu; milisaniyesiz
     cue uyarı bile vermeden düşüyordu.
 11) Rapor "bitişik yineleme" diyordu; dedektör sekiz cue'luk pencerede çalışıyor.
 12) Kısaltma bulgularının sırası PYTHONHASHSEED'e bağlıydı.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_formats as sf
import subtitle_translator_gui as gui

_SRT = "1\n00:00:01,000 --> 00:00:02,000\n{}\n"


def _write(data: bytes, suffix=".srt") -> str:
    handle, path = tempfile.mkstemp(suffix=suffix)
    os.close(handle)
    with open(path, "wb") as stream:
        stream.write(data)
    return path


class BomLessUtf16Test(unittest.TestCase):
    def _read(self, body, encoding):
        path = _write(_SRT.format(body).encode(encoding))
        try:
            return sf.read_subtitle_text(path)
        finally:
            os.unlink(path)

    def test_cjk_source_is_decoded_not_mojibake(self):
        text = self._read("你好世界 " * 200, "utf-16-le")
        self.assertIn("-->", text)
        self.assertIn("你好世界", text)

    def test_big_endian_cjk_too(self):
        self.assertIn("你好世界", self._read("你好世界 " * 200, "utf-16-be"))

    def test_arabic_source_is_decoded(self):
        text = self._read("مرحبا بالعالم " * 100, "utf-16-le")
        self.assertIn("-->", text)

    def test_ascii_utf16_still_works(self):
        self.assertIn("Header line", self._read("Header line", "utf-16-le"))

    def test_utf8_is_untouched(self):
        self.assertIn("Merhaba dünya", self._read("Merhaba dünya", "utf-8"))

    def test_cp1254_turkish_is_untouched(self):
        self.assertIn("Şu ağır işçi", self._read("Şu ağır işçi", "cp1254"))

    def test_lane_signature_needs_a_real_imbalance(self):
        self.assertFalse(sf._bom_less_utf16_lane_signature(b"plain ascii bytes"))
        self.assertTrue(sf._bom_less_utf16_lane_signature(
            "abcdefghij".encode("utf-16-le")))

    def test_a_guess_that_is_not_a_subtitle_is_rejected(self):
        self.assertFalse(sf._looks_like_subtitle_text("rastgele metin"))
        self.assertTrue(sf._looks_like_subtitle_text("00:01 --> 00:02"))
        self.assertTrue(sf._looks_like_subtitle_text("Dialogue: 0,0:00:01"))


class VttFractionlessTest(unittest.TestCase):
    def _parse(self, content):
        path = _write(content.encode("utf-8"), suffix=".vtt")
        try:
            return sf.parse_vtt(path)
        finally:
            os.unlink(path)

    def test_a_cue_without_milliseconds_is_kept(self):
        rows = self._parse(
            "WEBVTT\n\n00:00:01 --> 00:00:02\nFirst\n\n"
            "00:00:03.000 --> 00:00:04.000\nSecond\n")
        self.assertEqual([row[2] for row in rows], ["First", "Second"])

    def test_the_timestamp_is_padded_to_srt_form(self):
        rows = self._parse("WEBVTT\n\n00:00:01 --> 00:00:02\nFirst\n")
        self.assertEqual(rows[0][1], "00:00:01,000 --> 00:00:02,000")

    def test_short_mm_ss_form_without_fraction(self):
        rows = self._parse("WEBVTT\n\n00:05 --> 00:07\nThird\n")
        self.assertEqual(rows[0][1], "00:00:05,000 --> 00:00:07,000")

    def test_fractions_still_parse(self):
        self.assertEqual(sf._vtt_ts_to_srt("00:00:03.5"), "00:00:03,500")
        self.assertEqual(sf._vtt_ts_to_srt("00:00:03"), "00:00:03,000")

    def test_seconds_conversion_accepts_both_forms(self):
        self.assertEqual(sf._vtt_ts_to_seconds("00:00:02"), 2.0)
        self.assertEqual(sf._vtt_ts_to_seconds("00:00:02.500"), 2.5)


class NearDuplicateReportTest(unittest.TestCase):
    def test_pairs_are_reported_not_just_a_count(self):
        blocks = [
            (236, "00:00:01,000 --> 00:00:02,000", "Aynı cümle burada duruyor"),
            (237, "00:00:03,000 --> 00:00:04,000", "Bambaşka bir satır var"),
            (243, "00:00:20,000 --> 00:00:21,000", "Aynı cümle burada duruyor"),
        ]
        sources = [
            (236, "00:00:01,000 --> 00:00:02,000", "The same sentence stands here"),
            (237, "00:00:03,000 --> 00:00:04,000", "A completely different line"),
            (243, "00:00:20,000 --> 00:00:21,000", "Nothing alike whatsoever now"),
        ]
        pairs = gui._delivery_duplicate_pairs(blocks, sources)
        self.assertIn(("236", "243"), pairs)

    def test_the_window_really_is_wider_than_one_cue(self):
        self.assertGreater(gui._DUP_WIN, 1)

    def test_the_label_no_longer_claims_adjacency(self):
        import inspect
        source = inspect.getsource(gui.build_quality_report_text)
        self.assertNotIn("Bitişik yinelen", source)


class AcronymOrderTest(unittest.TestCase):
    def test_findings_come_out_in_a_stable_order(self):
        blocks = [(1, "t", "ABC kaldı"), (2, "t", "XYZ kaldı"),
                  (3, "t", "abece"), (4, "t", "iksiz"),
                  (5, "t", "ABC yine"), (6, "t", "XYZ yine")]
        sources = {"1": "ABC XYZ here", "2": "XYZ ABC here",
                   "3": "ABC XYZ gone", "4": "XYZ ABC gone",
                   "5": "ABC XYZ again", "6": "XYZ ABC again"}
        terms = [row["term"]
                 for row in gui._acronym_mixed_renderings(blocks, sources)]
        self.assertEqual(terms, sorted(terms))


if __name__ == "__main__":
    unittest.main()
