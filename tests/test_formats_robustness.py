"""
Format ayrıştırıcı dayanıklılık regresyonları (denetim bulguları):
- VTT boş-satır ayracı olmadan / başlıktan hemen sonra cue'ları kaybetmemeli (#7, #14)
- restore_format_tags çeviride düz '<' geçince <i>/<b>'yi düşürmemeli (#21)
"""
import os
import tempfile
import unittest

from subtitle_formats import parse_vtt, restore_format_tags


def _w(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


class VttRobustnessTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_no_blank_separator_between_cues(self):
        # Cue'lar arasında boş satır YOK — eskiden hepsi tek cue'ya çökerdi
        vtt = ("WEBVTT\n\n"
               "00:00:01.000 --> 00:00:02.000\nMerhaba\n"
               "00:00:02.000 --> 00:00:03.000\nDünya\n")
        b = parse_vtt(_w(self.d, "a.vtt", vtt))
        self.assertEqual(len(b), 2)
        self.assertEqual(b[0][2], "Merhaba")
        self.assertEqual(b[1][2], "Dünya")

    def test_no_blank_after_header(self):
        # WEBVTT başlığından sonra boş satır YOK — eskiden cue düşerdi
        vtt = "WEBVTT\n00:00:01.000 --> 00:00:02.000\nMerhaba\n"
        b = parse_vtt(_w(self.d, "b.vtt", vtt))
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0][2], "Merhaba")

    def test_normal_vtt_still_works(self):
        vtt = ("WEBVTT\n\n"
               "1\n00:00:01.000 --> 00:00:02.000\nMerhaba\n\n"
               "2\n00:00:02.000 --> 00:00:03.000\nDünya\n")
        b = parse_vtt(_w(self.d, "c.vtt", vtt))
        self.assertEqual(len(b), 2)


class RestoreTagsTest(unittest.TestCase):
    def test_literal_lt_in_translation_keeps_italics(self):
        # Çeviride düz '<' var ama BAŞTA etiket yok → italik yine de geri gelmeli
        out = restore_format_tags("<i>He said x</i>", "O dedi ki x < y")
        self.assertTrue(out.startswith("<i>"))
        self.assertTrue(out.endswith("</i>"))
        self.assertIn("< y", out)

    def test_already_tagged_translation_untouched(self):
        out = restore_format_tags("<i>Hello</i>", "<i>Merhaba</i>")
        self.assertEqual(out.count("<i>"), 1)


if __name__ == "__main__":
    unittest.main()
