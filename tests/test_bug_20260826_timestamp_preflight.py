# -*- coding: utf-8 -*-
"""Ön kontrol zaman damgası bütünlüğüne hiç bakmıyordu."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


def _cues(*stamps):
    return [(str(i + 1), ts, "metin") for i, ts in enumerate(stamps)]


class TimestampDefectsAreCountedTest(unittest.TestCase):
    """Ön kontrol dosyanın okunabilirliğine bakıyordu (boş, kodlama,
    ayrıştırma, cue yok) ama zamanların tutarlılığına hiç bakmıyordu. Bozuk
    zamanlı kaynak sessizce çevriliyor, API parası harcıyor ve kusur teslime
    taşınıyor.

    290 gerçek kaynakta ölçüldü: 23 dosyada 540 çakışan cue, 4 dosyada 161
    birebir aynı zaman damgası, 1 dosyada 35 sırasız cue.
    """

    def test_a_clean_file_reports_nothing(self):
        stats = g.scan_timestamp_integrity(
            _cues("00:00:01,000 --> 00:00:02,000",
                  "00:00:03,000 --> 00:00:04,000"))
        self.assertEqual(
            {k: v for k, v in stats.items() if k != "first_id"},
            {"overlap": 0, "duplicate": 0, "out_of_order": 0,
             "zero": 0, "reversed": 0})

    def test_an_overlap_is_counted(self):
        stats = g.scan_timestamp_integrity(
            _cues("00:00:01,000 --> 00:00:05,000",
                  "00:00:03,000 --> 00:00:06,000"))
        self.assertEqual(stats["overlap"], 1)
        self.assertEqual(stats["first_id"]["overlap"], "2")

    def test_an_out_of_order_cue_is_counted(self):
        stats = g.scan_timestamp_integrity(
            _cues("00:00:05,000 --> 00:00:06,000",
                  "00:00:01,000 --> 00:00:02,000"))
        self.assertEqual(stats["out_of_order"], 1)

    def test_a_repeated_stamp_is_counted(self):
        stats = g.scan_timestamp_integrity(
            _cues("00:00:01,000 --> 00:00:02,000",
                  "00:00:01,000 --> 00:00:02,000"))
        self.assertEqual(stats["duplicate"], 1)

    def test_a_reversed_and_a_zero_length_cue(self):
        self.assertEqual(
            g.scan_timestamp_integrity(
                _cues("00:00:05,000 --> 00:00:02,000"))["reversed"], 1)
        self.assertEqual(
            g.scan_timestamp_integrity(
                _cues("00:00:02,000 --> 00:00:02,000"))["zero"], 1)

    def test_empty_input_is_safe(self):
        stats = g.scan_timestamp_integrity([])
        self.assertEqual(stats["overlap"], 0)
        self.assertEqual(g.scan_timestamp_integrity(None)["overlap"], 0)

    def test_an_unparsable_stamp_is_skipped_not_crashed(self):
        stats = g.scan_timestamp_integrity([("1", "bozuk", "metin")])
        self.assertEqual(stats["overlap"], 0)


class ThePreflightWarnsBeforeSpendingMoneyTest(unittest.TestCase):
    """Uyarı; hata değil. Kaynağın kendi kusuru çeviriyi engellemez ama
    kullanıcı bilerek başlasın."""

    SRT = (
        "1\n00:00:01,000 --> 00:00:05,000\nBirinci satır\n\n"
        "2\n00:00:03,000 --> 00:00:06,000\nİkinci satır\n\n"
    )
    CLEAN = (
        "1\n00:00:01,000 --> 00:00:02,000\nBirinci satır\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nİkinci satır\n\n"
    )

    def _scan(self, body):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "film.srt")
            path.write_text(body, encoding="utf-8")
            return g.scan_subtitle_preflight(
                [str(path)], expected_source_language="English")

    def test_an_overlapping_file_is_flagged(self):
        issues = self._scan(self.SRT)
        found = [i for i in issues if i["code"] == "timestamp_integrity"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["severity"], "warning")
        self.assertIn("çakışıyor", found[0]["message"])
        self.assertIn("#2", found[0]["message"])

    def test_a_clean_file_is_not_flagged(self):
        issues = self._scan(self.CLEAN)
        self.assertEqual(
            [i for i in issues if i["code"] == "timestamp_integrity"], [])

    def test_the_warning_says_translation_will_not_fix_it(self):
        found = [i for i in self._scan(self.SRT)
                 if i["code"] == "timestamp_integrity"]
        self.assertIn("Çeviri bunu düzeltmez", found[0]["message"])


if __name__ == "__main__":
    unittest.main()
