"""
_vtt_ts_to_srt: WebVTT zaman damgalarını geçerli SRT'ye çevirir.
Milisaniye kısmı 3 haneye tamamlanmalı (yetersiz haneli VTT → bozuk SRT üretiyordu).
"""
import unittest

from subtitle_formats import _vtt_ts_to_srt


class VttTimestampTest(unittest.TestCase):
    def test_full_ms_preserved(self):
        self.assertEqual(_vtt_ts_to_srt("00:00:01.500"), "00:00:01,500")

    def test_short_ms_padded(self):
        # ,5 → ,500 ; ,12 → ,120  (eskiden geçersiz SRT üretiyordu)
        self.assertEqual(_vtt_ts_to_srt("00:00:01.5"), "00:00:01,500")
        self.assertEqual(_vtt_ts_to_srt("00:00:01.12"), "00:00:01,120")

    def test_minute_form_expanded_and_padded(self):
        self.assertEqual(_vtt_ts_to_srt("01:02.5"), "00:01:02,500")

    def test_excess_ms_truncated_to_three(self):
        self.assertEqual(_vtt_ts_to_srt("00:00:01.123456"), "00:00:01,123")

    def test_three_digit_hour_preserved(self):
        self.assertEqual(_vtt_ts_to_srt("100:00:01.500"), "100:00:01,500")

    def test_all_outputs_have_three_ms_digits(self):
        for ts in ("00:00:00.0", "00:00:09.99", "10:20:30.7", "5:00.4"):
            out = _vtt_ts_to_srt(ts)
            self.assertRegex(out, r",\d{3}$", f"{ts} → {out} 3 haneli ms değil")


if __name__ == "__main__":
    unittest.main()
