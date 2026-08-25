# -*- coding: utf-8 -*-
"""R1-R5: rapor kırpılmaz, üç dosya üretilir, kapsam doğrulanır."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui

ROWS = [
    {"name": "A.srt", "hata_count": 2,
     "delivery_scan": {"over_width": 105, "over_lines": 133,
                       "partial_echo": 7, "source_residue": 2,
                       "register_mixed": True,
                       "register": {"informal": 122, "formal": 35}}},
    {"name": "B.srt",
     "delivery_scan": {"cue_fill": 1, "syllable_typo": 3}},
]


def _cue_fill(count):
    return [{"id": str(i), "duration": 1.0, "chars": 50, "cps": 50,
             "prev_id": str(i - 1), "prev_cps": 5}
            for i in range(1, count + 1)]


class TheReportIsNeverTruncatedTest(unittest.TestCase):
    """68 dosyada 19.736 cue raporlarda '+N' ile gizlenmişti. Log kırpabilir
    çünkü akışı okunur tutar; rapor dosyası bulgunun tek kalıcı kaydıdır."""

    def test_the_log_path_still_truncates(self):
        lines = gui._cue_fill_report_lines(_cue_fill(20))
        self.assertEqual(len(lines), 9)
        self.assertIn("+12 cue daha", lines[-1])

    def test_the_report_path_does_not(self):
        lines = gui._cue_fill_report_lines(_cue_fill(20), limit=None)
        self.assertEqual(len(lines), 20)
        self.assertFalse(any("cue daha" in line for line in lines))

    def test_the_report_builder_asks_for_no_limit(self):
        source = inspect.getsource(gui.delivery_scan_report_lines)
        self.assertIn("limit=None", source)
        self.assertNotIn("[:8]", source)


class TheDeliveryScanGetsItsOwnFileTest(unittest.TestCase):
    """R2 — bulgular yalnız log'a gidiyordu; log rotasyona giriyor."""

    def test_every_finding_appears(self):
        text = gui.build_delivery_scan_report_text(ROWS, "RUN1")
        for fragment in ("Aşırı uzun satır: 105", "Fazla satırlı cue: 133",
                         "Komşu cue'da kısmi yankı: 7", "Eksik çeviri: 2",
                         "Hece tekrarı yazım hatası: 3"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, text)

    def test_files_are_named(self):
        text = gui.build_delivery_scan_report_text(ROWS, "RUN1")
        self.assertIn("── A.srt ──", text)
        self.assertIn("── B.srt ──", text)

    def test_an_empty_run_says_so(self):
        text = gui.build_delivery_scan_report_text([], "RUN1")
        self.assertIn("bulgu yok", text)


class TheSummaryOrdersByPriorityTest(unittest.TestCase):
    """R3 — tek giriş noktası, sıra KRİTİK → TERİM → BİÇİM."""

    def test_the_groups_are_in_order(self):
        text = gui.build_report_index_text(ROWS, "RUN1")
        critical = text.index("## KRİTİK")
        term = text.index("## TERİM")
        form = text.index("## BİÇİM")
        self.assertLess(critical, term)
        self.assertLess(term, form)

    def test_a_missing_translation_is_critical(self):
        text = gui.build_report_index_text(ROWS, "RUN1")
        critical = text[text.index("## KRİTİK"):text.index("## TERİM")]
        self.assertIn("Eksik çeviri", critical)

    def test_detail_files_are_linked(self):
        text = gui.build_report_index_text(
            ROWS, "RUN1", ["teslim_taramasi.txt", "KARARLAR.md"])
        self.assertIn("[teslim_taramasi.txt](teslim_taramasi.txt)", text)
        self.assertIn("[KARARLAR.md](KARARLAR.md)", text)


class EveryFindingCarriesADecisionFieldTest(unittest.TestCase):
    """R4 — karar izi kaybolmasın: her bulgunun yanında karar alanı ve o
    kararı uygulayan araç durur."""

    def test_the_table_has_a_decision_column(self):
        text = gui.build_decisions_report_text(ROWS, "RUN1")
        self.assertIn("| karar | uygulayan |", text)

    def test_each_finding_names_its_tool(self):
        text = gui.build_decisions_report_text(ROWS, "RUN1")
        self.assertIn("`_repair_untranslated_sync`", text)
        self.assertIn("`apply_line_breaks`", text)

    def test_a_pipe_in_a_filename_does_not_break_the_table(self):
        rows = [{"name": "a|b.srt", "delivery_scan": {"over_width": 1}}]
        text = gui.build_decisions_report_text(rows, "RUN1")
        row_line = [ln for ln in text.splitlines() if "a/b.srt" in ln]
        self.assertEqual(len(row_line), 1)
        self.assertEqual(row_line[0].count("|"), 7)


class FoundEqualsWrittenTest(unittest.TestCase):
    """R5 — değişmez. Bozulursa rapor sessizce kırpılmış demektir."""

    def test_a_complete_write_verifies(self):
        scan = gui.build_delivery_scan_report_text(ROWS, "RUN1")
        decisions = gui.build_decisions_report_text(ROWS, "RUN1")
        result = gui.verify_report_coverage(ROWS, scan, decisions)
        self.assertTrue(result["ok"], result["missing"])
        self.assertEqual(result["found"], result["written"])

    def test_a_truncated_write_is_caught(self):
        scan = gui.build_delivery_scan_report_text(ROWS, "RUN1")
        cut = scan.split("── B.srt ──")[0]
        result = gui.verify_report_coverage(ROWS, cut)
        self.assertFalse(result["ok"])
        self.assertTrue(any(item["file"] == "B.srt"
                            for item in result["missing"]))

    def test_an_empty_run_is_trivially_ok(self):
        self.assertTrue(gui.verify_report_coverage([], "")["ok"])

    def test_the_writer_runs_the_check(self):
        source = inspect.getsource(gui.App._save_quality_report)
        self.assertIn("verify_report_coverage(", source)
        self.assertIn("teslim_taramasi.txt", source)
        self.assertIn("00-OZET.md", source)
        self.assertIn("KARARLAR.md", source)


if __name__ == "__main__":
    unittest.main()
