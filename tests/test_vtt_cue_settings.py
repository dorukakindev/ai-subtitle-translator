# -*- coding: utf-8 -*-
"""WebVTT cue ayarları zaman satırında kalmasın.

`align:left position:0%,start line:86,67% size:100%` WebVTT'de zaman
satırının sonunda gelir; SRT'de böyle bir alan YOKTUR ve katı oynatıcılar
satırı reddedebilir. Gerçek vaka: `Marjoe.srt` kaynağında 551 satır böyle.

Kuyruk normalleştirmeden sağ çıkıyordu. Teslime sızmıyordu çünkü
`parse_any` zaman damgasını bileşenlerden yeniden kuruyor (2.221 SRT
tarandı, canlı teslimde kalıntı yok) — ama normalleştirilmiş METNİ
doğrudan yazan herhangi bir yol onu taşırdı.
"""
import unittest

from subtitle_formats import normalize_srt_timestamp_separators as normalize


class VttCueSettingsTest(unittest.TestCase):
    def test_full_cue_settings_are_dropped(self):
        line = ("1:01:37,694 --> 1:01:40,763 align:left "
                "position:0%,start line:86,67% size:100%")
        self.assertEqual(normalize(line),
                         "01:01:37,694 --> 01:01:40,763")

    def test_single_setting_is_dropped(self):
        self.assertEqual(
            normalize("00:00:01,000 --> 00:00:03,000 align:middle"),
            "00:00:01,000 --> 00:00:03,000")

    def test_plain_timestamp_is_unchanged(self):
        line = "00:00:01,000 --> 00:00:03,000"
        self.assertEqual(normalize(line), line)

    def test_unknown_trailing_text_is_kept(self):
        # Bozuk ama anlamlı olabilecek bir kuyruğu sessizce kırpma.
        line = "0:01:23,456 --> 0:01:25,000  önemli olabilecek bir not"
        self.assertEqual(
            normalize(line),
            "00:01:23,456 --> 00:01:25,000  önemli olabilecek bir not")

    def test_hour_padding_still_applies(self):
        self.assertEqual(
            normalize("1:02:03,004 --> 1:02:05,006"),
            "01:02:03,004 --> 01:02:05,006")


if __name__ == "__main__":
    unittest.main()
