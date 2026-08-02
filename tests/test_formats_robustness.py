"""
Format ayrıştırıcı dayanıklılık regresyonları (denetim bulguları):
- VTT boş-satır ayracı olmadan / başlıktan hemen sonra cue'ları kaybetmemeli (#7, #14)
- restore_format_tags çeviride düz '<' geçince <i>/<b>'yi düşürmemeli (#21)
"""
import os
import tempfile
import unittest

from subtitle_formats import get_subtitle_files, parse_ass, parse_vtt, restore_format_tags


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

    def test_cue_ids_do_not_leak_without_blank_separator(self):
        vtt = ("WEBVTT\n\n"
               "first\n00:00:01.000 --> 00:00:02.000\nMerhaba\n"
               "NOTE-1\n00:00:02.000 --> 00:00:03.000\nDunya\n")
        b = parse_vtt(_w(self.d, "ids.vtt", vtt))
        self.assertEqual([x[2] for x in b], ["Merhaba", "Dunya"])

    def test_digitless_cue_ids_do_not_leak_without_blank_separator(self):
        vtt = ("WEBVTT\n\n"
               "first-cue\n00:00:01.000 --> 00:00:02.000\nAlpha\n"
               "second-cue\n00:00:02.000 --> 00:00:03.000\nBravo\n")
        b = parse_vtt(_w(self.d, "word-ids.vtt", vtt))
        self.assertEqual([x[2] for x in b], ["Alpha", "Bravo"])

    def test_numeric_and_short_alphanumeric_text_survive_without_separator(self):
        for text in ("1984", "T-800", "A1"):
            vtt = (
                "WEBVTT\n\n"
                "00:00:01.000 --> 00:00:02.000\n" + text + "\n"
                "00:00:02.000 --> 00:00:03.000\nDunya\n"
            )
            b = parse_vtt(_w(self.d, f"{text}.vtt", vtt))
            self.assertEqual([x[2] for x in b], [text, "Dunya"])

    def test_note_metadata_is_skipped_but_note_prefixed_id_is_kept(self):
        vtt = ("WEBVTT\n\nNOTE ignored metadata\nline\n\n"
               "NOTE-1\n00:00:01.000 --> 00:00:02.000\nGercek cue\n")
        b = parse_vtt(_w(self.d, "note-id.vtt", vtt))
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0][2], "Gercek cue")


class AssAndDiscoveryRobustnessTest(unittest.TestCase):
    def test_dialogue_outside_events_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            ass = ("[Script Info]\nDialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,Yanlis\n"
                   "[Events]\n"
                   "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
                   "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Dogru\n")
            blocks = parse_ass(_w(d, "a.ass", ass))
            self.assertEqual([b[2] for b in blocks], ["Dogru"])

    def test_brackets_in_directory_name_are_literal(self):
        with tempfile.TemporaryDirectory() as d:
            nested = os.path.join(d, "Film [1080p]")
            os.makedirs(nested)
            wanted = _w(nested, "film.srt", "1\n00:00:00,000 --> 00:00:01,000\nHi\n")
            self.assertEqual(get_subtitle_files(d), [wanted])


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
