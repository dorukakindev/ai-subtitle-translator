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
