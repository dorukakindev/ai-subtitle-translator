# -*- coding: utf-8 -*-
"""Yalnız-rapor tutarlılık adayları dört akışta da 'öneri' diye etiketlenir."""
import inspect
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class ReportOnlyConsistencyIsLabelledTest(unittest.TestCase):
    """Etiket pass_status['Consistency']['report_only']'ye bağlı.

    Bunu yalnız batch ve hybrid-batch kuruyordu; düz sync ve sync-hybrid
    (kullanıcının kullandığı akış) yalnız-rapor modunda aday sayısını
    'Tutarlılık düzeltmesi' diye yazıyor ve uygulanan-düzeltme toplamına
    ekliyordu.
    """

    def test_a_report_only_row_is_labelled_as_a_suggestion(self):
        row = {"name": "x.srt", "total": 10, "cons": 7,
               "pass_status": {"Consistency": {"report_only": True,
                                               "suggested": 7, "changed": 0}}}
        text = g.build_quality_report_text(
            [row], "gpt-5.4", "Türkçe", "sync", 0)
        self.assertIn("Tutarlılık önerisi (uygulanmadı)", text)
        self.assertNotIn("Tutarlılık düzeltmesi", text)

    def test_a_report_only_row_does_not_count_as_an_applied_fix(self):
        row = {"cons": 7,
               "pass_status": {"Consistency": {"report_only": True,
                                               "suggested": 7}}}
        self.assertEqual(g._quality_report_applied_fix_count([row]), 0)

    def test_an_applied_row_still_counts(self):
        row = {"cons": 7,
               "pass_status": {"Consistency": {"report_only": False,
                                               "changed": 7}}}
        self.assertEqual(g._quality_report_applied_fix_count([row]), 7)

    def test_every_flow_records_the_consistency_pass_status(self):
        """Her consistency_sweep çağrısını bir pass_status ataması izlemeli."""
        src = inspect.getsource(g)
        calls = [m.start() for m in re.finditer(r"ht\.consistency_sweep\(", src)]
        self.assertGreaterEqual(len(calls), 4)
        for start in calls:
            window = src[start:start + 2000]
            with self.subTest(line=src[:start].count(chr(10)) + 1):
                self.assertIn('_pass_status["Consistency"]', window)
                self.assertIn('"report_only"', window)


if __name__ == "__main__":
    unittest.main()
