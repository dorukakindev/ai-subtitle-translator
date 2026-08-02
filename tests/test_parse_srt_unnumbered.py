"""
parse_srt: numaralı ve NUMARASIZ (ilk satır doğrudan zaman damgası) SRT'leri ele alır.
Numarasız altyazılarda eskiden tüm cue'lar sessizce düşüyordu (len(lines)<3 elemesi).
"""
import os
import tempfile
import unittest

import subtitle_translator_gui as gui


def _write(tmpdir, name, text):
    p = os.path.join(tmpdir, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


class ParseSrtTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_numbered_srt(self):
        p = _write(self.d, "n.srt",
                   "1\n00:00:01,000 --> 00:00:02,000\nMerhaba\n\n"
                   "2\n00:00:02,000 --> 00:00:03,000\nDünya\n")
        b = gui.parse_srt(p)
        self.assertEqual(len(b), 2)
        self.assertEqual(b[0], ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba"))
        self.assertEqual(b[1][2], "Dünya")

    def test_three_digit_hour_srt(self):
        p = _write(
            self.d, "long.srt",
            "1\n100:00:01,000 --> 100:00:02,000\nCentury line\n")
        self.assertEqual(gui.parse_srt(p), [
            ("1", "100:00:01,000 --> 100:00:02,000", "Century line")])

    def test_unnumbered_srt_recovered(self):
        # İndeks satırı YOK — ilk satır zaman damgası. Eskiden hepsi düşüyordu.
        p = _write(self.d, "u.srt",
                   "00:00:01,000 --> 00:00:02,000\nMerhaba\n\n"
                   "00:00:02,000 --> 00:00:03,000\nDünya\n")
        b = gui.parse_srt(p)
        self.assertEqual(len(b), 2)                       # artık düşmüyor
        self.assertEqual([x[0] for x in b], ["1", "2"])   # sıralı index uyduruldu
        self.assertEqual(b[0][1], "00:00:01,000 --> 00:00:02,000")
        self.assertEqual(b[0][2], "Merhaba")
        self.assertEqual(b[1][2], "Dünya")

    def test_unnumbered_multiline_text(self):
        p = _write(self.d, "m.srt",
                   "00:00:01,000 --> 00:00:02,000\nilk satır\nikinci satır\n")
        b = gui.parse_srt(p)
        self.assertEqual(len(b), 1)
        self.assertEqual(b[0][2], "ilk satır\nikinci satır")

    def test_whitespace_only_separator_starts_new_cue(self):
        p = _write(self.d, "space.srt",
                   "1\n00:00:01,000 --> 00:00:02,000\nMerhaba\n \t\n"
                   "2\n00:00:02,000 --> 00:00:03,000\nDunya\n")
        b = gui.parse_srt(p)
        self.assertEqual(len(b), 2)
        self.assertEqual([x[2] for x in b], ["Merhaba", "Dunya"])

    def test_blank_line_between_timestamp_and_dialogue_is_recovered(self):
        p = _write(
            self.d,
            "broken.srt",
            "1\n00:00:01,000 --> 00:00:02,000\n\nGerçek replik.\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\nSonraki replik.\n",
        )
        b = gui.parse_srt(p)
        self.assertEqual(
            b,
            [
                ("1", "00:00:01,000 --> 00:00:02,000", "Gerçek replik."),
                ("2", "00:00:02,000 --> 00:00:03,000", "Sonraki replik."),
            ],
        )

    def test_empty_cue_before_next_index_stays_empty(self):
        p = _write(
            self.d,
            "empty.srt",
            "1\n00:00:01,000 --> 00:00:02,000\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\nSonraki replik.\n",
        )
        b = gui.parse_srt(p)
        self.assertEqual(b, [("2", "00:00:02,000 --> 00:00:03,000", "Sonraki replik.")])

    def test_garbage_timestamp_block_is_rejected(self):
        p = _write(self.d, "garbage.srt",
                   "1\nnot a timestamp\nYanlis\n\n"
                   "2\n00:00:02,000 --> 00:00:03,000\nDogru\n")
        self.assertEqual(gui.parse_srt(p), [
            ("2", "00:00:02,000 --> 00:00:03,000", "Dogru"),
        ])

    def test_dot_milliseconds_are_normalized(self):
        p = _write(self.d, "dots.srt",
                   "1\n00:00:01.000 --> 00:00:02.250\nMerhaba\n")
        self.assertEqual(gui.parse_srt(p)[0][1],
                         "00:00:01,000 --> 00:00:02,250")


if __name__ == "__main__":
    unittest.main()
