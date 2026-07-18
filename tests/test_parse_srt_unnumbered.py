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


if __name__ == "__main__":
    unittest.main()
