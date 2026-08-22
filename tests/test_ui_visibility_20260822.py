# -*- coding: utf-8 -*-
"""Görünürlük iyileştirmeleri — veri zaten üretiliyordu, ekranda yoktu."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class ReviewWindowShowsTheWrittenFileTest(unittest.TestCase):
    """Dış denetim madde 18: inceleme penceresi HAM çeviriyi gösteriyordu.

    Critic, Polish, Native, Condense, SDH temizliği, terim normalizasyonu, cue
    birleştirme ve teslim hazırlığı `sorted_blocks`/`_delivery_blocks` üzerinde
    çalışıyor; `file_blocks` güncellenmiyor. Kullanıcı ekranda bir metni
    onaylarken diskte BAŞKA bir final duruyordu.
    """

    def test_the_dialog_reads_the_delivered_srt(self):
        source = inspect.getsource(g.App._write_results)
        marker = source.index("_last_trans = []")
        window = source[marker:marker + 1200]
        self.assertIn("parse_subtitle(", window)
        self.assertIn("_last_written_output", window)

    def test_the_written_path_is_captured_per_file(self):
        source = inspect.getsource(g.App._write_results)
        self.assertIn("_last_written_output = out_path", source)

    def test_it_falls_back_to_the_raw_blocks_when_unreadable(self):
        source = inspect.getsource(g.App._write_results)
        marker = source.index("_last_trans = []")
        window = source[marker:marker + 1400]
        self.assertIn("if not _last_trans:", window)
        self.assertIn("file_blocks[_last_fp]", window)


class PassEfficiencyTableTest(unittest.TestCase):
    """Pahalı ama etkisiz pass ana raporda görünmeli."""

    ROWS = [{
        "pass_trace": {
            "Critic": 0, "Polish": 12, "Native": 3,
            "__guard_events__": [{"pass": "Native", "reason": "structure"}],
        },
        "pass_status": {"Critic": {"report_only": True, "suggested": 31}},
        "timing": {"api_usage": {
            "Critic Pass": {"total_tokens": 480000, "cost_usd": 0.42},
            "Polish Pass": {"total_tokens": 96000, "cost_usd": 0.08},
            "Native Okuyucu": {"total_tokens": 210000, "cost_usd": 0.19},
        }},
    }]

    def test_expensive_passes_are_listed_first(self):
        lines = g.run_pass_efficiency_table(self.ROWS)
        body = [line for line in lines if line.startswith("  ")]
        self.assertTrue(body[0].strip().startswith("Critic"), body)

    def test_a_pass_with_no_effect_is_named_as_such(self):
        rows = [{"pass_trace": {"Condense": 0}, "pass_status": {},
                 "timing": {"api_usage": {
                     "Okuma Hızı Kısaltma": {
                         "total_tokens": 150000, "cost_usd": 0.13}}}}]
        text = "\n".join(g.run_pass_efficiency_table(rows))
        self.assertIn("karşılıksız", text)

    def test_report_only_pass_is_measured_per_suggestion(self):
        text = "\n".join(g.run_pass_efficiency_table(self.ROWS))
        self.assertIn("token/öneri", text)
        # Yalnız-rapor pass'i 'karşılıksız' diye etiketlenmemeli:
        # 31 önerisi var, uygulanmaması tasarım gereği.
        critic_line = next(
            line for line in text.split("\n") if "Critic" in line)
        self.assertNotIn("karşılıksız", critic_line)

    def test_guard_rollbacks_are_counted(self):
        text = "\n".join(g.run_pass_efficiency_table(self.ROWS))
        self.assertIn("guard geri aldı", text)

    def test_empty_input_produces_no_section(self):
        self.assertEqual(g.run_pass_efficiency_table([]), [])

    def test_the_table_is_wired_into_the_main_report(self):
        source = inspect.getsource(g.build_quality_report_text)
        self.assertIn("run_pass_efficiency_table(rows)", source)


class SkipReasonTest(unittest.TestCase):
    """'atlandı' yerine NEDEN atlandığı yazılmalı."""

    def test_known_reasons_are_translated(self):
        self.assertEqual(
            g.pass_skip_explanation({"reason": "analysis_incomplete"}),
            "yardımcı analiz eksik/bozuk kaldı")
        self.assertEqual(
            g.pass_skip_explanation({"reason": "not_series"}),
            "dosya bir dizi bölümü olarak tanınmadı")

    def test_unknown_reason_is_shown_raw(self):
        self.assertEqual(
            g.pass_skip_explanation({"reason": "yeni_sebep"}), "yeni_sebep")

    def test_missing_reason_is_empty(self):
        self.assertEqual(g.pass_skip_explanation({}), "")
        self.assertEqual(g.pass_skip_explanation(None), "")

    def test_the_skipped_line_uses_the_explanation(self):
        source = inspect.getsource(g)
        marker = source.index('state = \'atlandı\' if enabled else \'kapalı\'')
        window = source[marker:marker + 400]
        self.assertIn("pass_skip_explanation(status_info)", window)


class StageTimelineTest(unittest.TestCase):
    """Zamanın nereye gittiği ana raporda tek bakışta görünmeli."""

    ROW = {"timing": {"duration_seconds": 734.0, "stage_timings": [
        {"name": "Analiz", "duration_seconds": 121.0},
        {"name": "Ana Çeviri", "duration_seconds": 402.5},
        {"name": "Critic", "duration_seconds": 166.0},
        {"name": "Teslim", "duration_seconds": 9.0},
    ]}}

    def test_slowest_stages_come_first(self):
        line = g.file_stage_summary_line(self.ROW)
        self.assertIn("toplam", line)
        self.assertLess(line.index("Ana Çeviri"), line.index("Critic"))
        self.assertLess(line.index("Critic"), line.index("Analiz"))

    def test_only_the_top_stages_are_shown(self):
        line = g.file_stage_summary_line(self.ROW, top=2)
        self.assertIn("Ana Çeviri", line)
        self.assertNotIn("Teslim", line)

    def test_zero_duration_stages_are_skipped(self):
        row = {"timing": {"stage_timings": [
            {"name": "Bekleyen", "duration_seconds": 0}]}}
        self.assertEqual(g.file_stage_summary_line(row), "")

    def test_missing_timing_is_empty(self):
        self.assertEqual(g.file_stage_summary_line({}), "")

    def test_the_line_is_wired_into_the_main_report(self):
        source = inspect.getsource(g.build_quality_report_text)
        self.assertIn("file_stage_summary_line(r)", source)


if __name__ == "__main__":
    unittest.main()
