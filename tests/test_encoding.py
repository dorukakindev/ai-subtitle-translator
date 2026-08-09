"""
Toleranslı encoding çözümleme testleri — cp1254 (Windows-Türkçe) ve UTF-8 BOM.
"""
import os
import tempfile
import unittest
from pathlib import Path

from subtitle_formats import read_subtitle_text
import subtitle_translator_gui as gui

SRT_BODY = (
    "1\n"
    "00:00:01,000 --> 00:00:03,000\n"
    "Şöyle ığdır çiçeği güzeldir.\n\n"
    "2\n"
    "00:00:03,000 --> 00:00:05,000\n"
    "Öğründü, çünkü üşüdü.\n"
)


class ReadSubtitleTextTest(unittest.TestCase):
    def _write(self, encoding, bom=b""):
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        Path(fp).write_bytes(bom + SRT_BODY.encode(encoding))
        return fp

    def test_cp1254_decoded_correctly(self):
        fp = self._write("cp1254")
        try:
            text = read_subtitle_text(fp)
            self.assertIn("ığdır çiçeği", text)
            self.assertIn("Öğründü", text)
        finally:
            os.unlink(fp)

    def test_utf8_bom_roundtrip(self):
        fp = self._write("utf-8", bom=b"\xef\xbb\xbf")
        try:
            text = read_subtitle_text(fp)
            self.assertIn("Şöyle ığdır çiçeği", text)
            self.assertFalse(text.startswith("﻿"), "BOM sökülmedi")
        finally:
            os.unlink(fp)

    def test_plain_utf8(self):
        fp = self._write("utf-8")
        try:
            self.assertIn("Öğründü, çünkü üşüdü", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_latin1_fallback_never_raises(self):
        # cp1254'ün reddedeceği bir bayt yok; latin-1 son çare yine de patlamamalı
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(b"\xff\xfe\x00rastgele bayt")
        try:
            self.assertIsInstance(read_subtitle_text(fp), str)
        finally:
            os.unlink(fp)


    def test_utf16le_bom_decoded_correctly(self):
        fp = self._write("utf-16-le", bom=b"\xff\xfe")
        try:
            text = read_subtitle_text(fp)
            self.assertIn("ığdır çiçeği", text)
        finally:
            os.unlink(fp)

    def test_utf16be_bom_decoded_correctly(self):
        fp = self._write("utf-16-be", bom=b"\xfe\xff")
        try:
            text = read_subtitle_text(fp)
            self.assertIn("ığdır çiçeği", text)
        finally:
            os.unlink(fp)

    def test_cp1254_not_mistaken_for_utf16(self):
        # cp1254 bytes without BOM must NOT be decoded as UTF-16 garbage
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(SRT_BODY.encode("cp1254"))
        try:
            text = read_subtitle_text(fp)
            self.assertIn("ığdır çiçeği", text)
            self.assertNotIn("\u0000", text)  # no null bytes from mis-decoded UTF-16
        finally:
            os.unlink(fp)

    def test_bomless_utf16_detection_uses_initial_sample(self):
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        prefix = ("Header line\n" * 500 + SRT_BODY).encode("utf-16-le")
        Path(fp).write_bytes(prefix + (b"A" * 50000))
        try:
            text = read_subtitle_text(fp)
            self.assertIn("ığdır çiçeği", text)
        finally:
            os.unlink(fp)

    def test_shift_jis_detected_before_cp1254_fallback(self):
        body = (
            "1\n00:00:01,000 --> 00:00:03,000\n"
            "こんにちは、世界。これは字幕のテストです。\n\n"
        ) * 12
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("shift_jis"))
        try:
            self.assertIn("こんにちは、世界", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_gb18030_detected_before_cp1254_fallback(self):
        body = (
            "1\n00:00:01,000 --> 00:00:03,000\n"
            "你好，世界。这是一个字幕编码测试，今天开始翻译。\n\n"
        ) * 12
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("gb18030"))
        try:
            self.assertIn("你好，世界", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_cp1251_detected_before_cp1254_fallback(self):
        body = (
            "1\n00:00:01,000 --> 00:00:03,000\n"
            "Привет, мир. Это проверка кодировки субтитров.\n\n"
        ) * 12
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("cp1251"))
        try:
            self.assertIn("Привет, мир", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_short_cp1251_detected_before_cp1254_fallback(self):
        body = "1\n00:00:01,000 --> 00:00:03,000\n\u041f\u0440\u0438\u0432\u0435\u0442\n"
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("cp1251"))
        try:
            self.assertIn("\u041f\u0440\u0438\u0432\u0435\u0442", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_short_cp1254_still_uses_cp1254(self):
        body = "1\n00:00:01,000 --> 00:00:03,000\n\u015e\u00f6yle\n"
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("cp1254"))
        try:
            self.assertIn("\u015e\u00f6yle", read_subtitle_text(fp))
        finally:
            os.unlink(fp)

    def test_short_cp1250_is_not_misread_as_cp1252(self):
        body = "1\n00:00:01,000 --> 00:00:03,000\nZa\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144\n"
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(body.encode("cp1250"))
        try:
            self.assertIn("Za\u017c\u00f3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144", read_subtitle_text(fp))
        finally:
            os.unlink(fp)


class ParseSubtitleEncodingTest(unittest.TestCase):
    def test_parse_srt_cp1254(self):
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        Path(fp).write_bytes(SRT_BODY.encode("cp1254"))
        try:
            blocks = gui.parse_subtitle(fp)
            self.assertEqual(len(blocks), 2)
            self.assertIn("ığdır çiçeği", blocks[0][2])
        finally:
            os.unlink(fp)


if __name__ == "__main__":
    unittest.main()
