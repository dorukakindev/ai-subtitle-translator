"""
_fill_hata_with_source testleri — [HATA] satırlarının kaynak metne düşmeden
görünür eksik-çeviri işaretine çevrilmesi.
"""
import unittest

import subtitle_translator_gui as gui


class FillHataWithSourceTest(unittest.TestCase):
    def test_marks_hata_lines_without_source_leak(self):
        blocks = [
            ("1", "ts1", "Çevrildi."),
            ("2", "ts2", "[HATA]"),
            ("3", "ts3", "[HATA: timeout]"),
        ]
        raw = {"1": "Translated.", "2": "Second line.", "3": "<i>Third line.</i>"}
        out, marked = gui._fill_hata_with_source(blocks, raw)
        self.assertEqual(marked, 2)
        self.assertEqual(out[1][2], "[ÇEVİRİ EKSİK]")
        self.assertEqual(out[2][2], "[ÇEVİRİ EKSİK]")
        self.assertEqual(out[0][2], "Çevrildi.")           # normal satıra dokunma

    def test_missing_source_keeps_hata(self):
        blocks = [("5", "ts", "[HATA]")]
        out, marked = gui._fill_hata_with_source(blocks, {"9": "var"})
        self.assertEqual(marked, 0)
        self.assertEqual(out[0][2], "[HATA]")  # kaynak yok — olduğu gibi kalır

    def test_empty_map_noop(self):
        blocks = [("1", "ts", "[HATA]")]
        out, marked = gui._fill_hata_with_source(blocks, {})
        self.assertEqual(marked, 0)
        self.assertEqual(out, blocks)

    def test_no_hata_lines(self):
        blocks = [("1", "ts", "Tamam."), ("2", "ts", "İyi.")]
        out, marked = gui._fill_hata_with_source(blocks, {"1": "OK.", "2": "Good."})
        self.assertEqual(marked, 0)
        self.assertEqual(out, blocks)

    def test_marked_line_then_tag_restore_does_not_leak_source(self):
        blocks = [("1", "ts", "[HATA]")]
        raw = {"1": "<i>Inner voice.</i>"}
        out, _ = gui._fill_hata_with_source(blocks, raw)
        restored = gui._restore_tags_blocks(out, raw)
        self.assertEqual(restored[0][2], "[ÇEVİRİ EKSİK]")


if __name__ == "__main__":
    unittest.main()
