"""
build_quality_report_text, _count_hata_cps ve rotate_logs testleri.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class CountHataCpsTest(unittest.TestCase):
    TS_OK   = "00:00:01,000 --> 00:00:06,000"   # 5 sn — rahat
    TS_FAST = "00:00:01,000 --> 00:00:02,000"   # 1 sn — 60 karakter sığmaz

    def test_counts(self):
        blocks = [
            ("1", self.TS_OK,   "Normal satır."),
            ("2", self.TS_FAST, "A" * 60),        # CPS aşımı
            ("3", self.TS_OK,   "[HATA]"),
            ("4", self.TS_OK,   "[HATA: timeout]"),
            ("5", self.TS_OK,   "[ÇEVİRİ EKSİK]"),
        ]
        hata, cps = gui._count_hata_cps(blocks)
        self.assertEqual(hata, 3)
        self.assertEqual(cps, 1)


class FileTranslationChunkCountTest(unittest.TestCase):
    def test_counts_only_chunks_belonging_to_requested_file(self):
        file_map = {
            "chunk_0": [(1, "ts", "C:/subs/a.srt")],
            "chunk_1": [(2, "ts", "C:/subs/a.srt"),
                        (3, "ts", "C:/subs/a.srt")],
            "chunk_2": [(1, "ts", "C:/subs/b.srt")],
            "empty": [],
        }

        self.assertEqual(
            gui._file_translation_chunk_count(file_map, "C:/subs/a.srt"), 2)
        self.assertEqual(
            gui._file_translation_chunk_count(file_map, "C:/subs/b.srt"), 1)
        self.assertEqual(
            gui._file_translation_chunk_count(file_map, "C:/subs/c.srt"), 0)


class PassTraceTest(unittest.TestCase):
    def test_counts_text_changes_ignoring_restored_tags(self):
        before = [
            ("1", "00:00:01,000 --> 00:00:02,000", "<i>Merhaba.</i>"),
            ("2", "00:00:02,000 --> 00:00:03,000", "Eski satir."),
        ]
        after = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Yeni satir."),
        ]
        self.assertEqual(gui._count_text_changes(before, after), 1)

    def test_record_pass_change_adds_only_real_changes(self):
        trace = {}
        history = {}
        before = [("1", "00:00:01,000 --> 00:00:02,000", "A")]
        after = [("1", "00:00:01,000 --> 00:00:02,000", "B")]
        self.assertEqual(gui._record_pass_change(trace, "Critic", before, after, history), 1)
        self.assertEqual(trace, {"Critic": 1})
        self.assertEqual(history["1"][0]["pass"], "Critic")
        self.assertEqual(history["1"][0]["before"], "A")
        self.assertEqual(history["1"][0]["after"], "B")

    def test_record_pass_change_keeps_zero_change_execution(self):
        trace = {}
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "A")]

        self.assertEqual(
            gui._record_pass_change(trace, "Native", blocks, list(blocks)), 0)
        self.assertEqual(trace, {"Native": 0})

    def test_multi_pass_history_summary(self):
        history = {
            "5": [{"pass": "Critic"}, {"pass": "Native"}],
            "6": [{"pass": "Polish"}],
        }
        count, summary = gui._multi_pass_history(history)
        self.assertEqual(count, 1)
        self.assertIn("#5: Critic -> Native", summary)

    def test_detect_pass_overrides(self):
        history = {
            "5": [
                {"pass": "Critic", "before": "A", "after": "B"},
                {"pass": "Native", "before": "B", "after": "C"},
            ],
            "6": [
                {"pass": "Critic", "before": "X", "after": "Y"},
                {"pass": "Native", "before": "Y", "after": "X"},
            ],
            "7": [
                {"pass": "Polish", "before": "M", "after": "N"},
            ],
        }
        count, summary = gui._detect_pass_overrides(history)
        self.assertEqual(count, 2)
        self.assertIn("#5: Critic -> Native (override)", summary)
        self.assertIn("#6: Critic -> Native (revert)", summary)

    def test_detects_middle_pass_revert_even_if_last_output_restores(self):
        history = {
            "5": [
                {"pass": "Critic", "before": "A", "after": "B"},
                {"pass": "Polish", "before": "B", "after": "A"},
                {"pass": "Native", "before": "A", "after": "B"},
            ],
        }
        count, summary = gui._detect_pass_overrides(history)
        self.assertEqual(count, 2)
        self.assertIn("#5: Critic -> Polish (revert)", summary)
        self.assertIn("#5: Polish -> Native (revert)", summary)

    def test_detects_refinement_for_minor_punctuation(self):
        history = {
            "5": [
                {"pass": "Critic", "before": "Hello", "after": "Merhaba"},
                {"pass": "Native", "before": "Merhaba", "after": "Merhaba!"},
            ],
        }
        count, summary = gui._detect_pass_overrides(history)
        self.assertEqual(count, 1)
        self.assertIn("#5: Critic -> Native (refinement)", summary)

    def test_question_punctuation_change_is_not_refinement(self):
        history = {
            "5": [
                {"pass": "Critic", "before": "No", "after": "Hayır."},
                {"pass": "Native", "before": "Hayır.", "after": "Hayır?"},
            ],
        }
        count, summary = gui._detect_pass_overrides(history)
        self.assertEqual(count, 1)
        self.assertIn("#5: Critic -> Native (override)", summary)

    def test_pass_interaction_counts(self):
        history = {
            "5": [
                {"pass": "Critic", "before": "A", "after": "B"},
                {"pass": "Polish", "before": "B", "after": "C"},
            ],
            "6": [
                {"pass": "Critic", "before": "X", "after": "Y"},
                {"pass": "Native", "before": "Y", "after": "X"},
            ],
            "7": [
                {"pass": "Critic", "before": "Hello", "after": "Merhaba"},
                {"pass": "Native", "before": "Merhaba", "after": "Merhaba!"},
            ],
        }
        self.assertEqual(
            gui._pass_interaction_counts(history),
            {"override": 1, "revert": 1, "refinement": 1},
        )


class BuildQualityReportTextTest(unittest.TestCase):
    def test_mixed_rows_render_only_present_fields(self):
        rows = [
            {"name": "a.srt", "total": 100, "hata": 1, "cps": 2,
             "cons": 3, "rev": 4, "warn": 5},                       # düz mod satırı
            {"name": "b.srt", "total": 50, "hata": 0, "cps": 1,
             "pass_fix": 7, "qc_auto": 1, "qc": 2},                  # hybrid satırı
        ]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "batch", 123_456)
        self.assertIn("a.srt", txt)
        self.assertIn("b.srt", txt)
        self.assertIn("İnceleme düzeltmesi", txt)        # düz mod alanı
        self.assertIn("Kalite geçişi düzeltmesi", txt)   # hybrid alanı
        self.assertIn("QC otomatik düzeltmesi", txt)
        self.assertIn("TOPLAM: 2 dosya, 150 satır", txt)
        self.assertIn("123,456", txt)
        # b.srt bloğunda 'rev' alanı olmamalı — alan bazlı yazım
        # (TOPLAM özeti hariç: yalnızca dosyanın kendi bloğuna bak)
        b_section = txt.split("b.srt")[1].split("=" * 72)[0]
        self.assertNotIn("İnceleme düzeltmesi", b_section)

    def test_empty_optional_fields_do_not_crash_totals(self):
        rows = [{"name": "x.srt", "total": 10, "hata": 0, "cps": 0}]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "sync", 0)
        self.assertIn("TOPLAM: 1 dosya, 10 satır", txt)


    def test_pass_trace_breakdown_is_rendered_and_summed(self):
        rows = [
            {"name": "a.srt", "total": 10, "pass_trace": {"Critic": 2, "Polish": 1}},
            {"name": "b.srt", "total": 5, "pass_trace": {"Critic": 3}},
        ]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "hybrid", 0)
        self.assertIn("Critic: 2", txt)
        self.assertIn("Polish: 1", txt)
        self.assertIn("Pass breakdown total: Critic: 5, Polish: 1", txt)

    def test_feature_audit_distinguishes_ran_zero_changed_and_skipped(self):
        row = {
            "name": "a.srt",
            "total": 10,
            "run_status": "done",
            "helper_analysis": True,
            "analysis_status": "kısmi",
            "chain_ctx": True,
            "translation_chunks": 4,
            "pass_trace": {"Consistency": 0, "Native": 0, "Critic": 2},
        }
        snapshot = {
            "critic": True,
            "native": True,
            "semantic_reconcile": True,
            "clean_sdh": False,
        }

        audit = gui._quality_feature_audit(row, snapshot)

        self.assertIn("Yardımcı Analiz: kısmi", audit)
        self.assertIn("Zincirleme Bağlam: çalıştı, 4 chunk", audit)
        self.assertIn("Critic Pass: çalıştı, 2 cue değiştirdi", audit)
        self.assertIn("Native Okuyucu: çalıştı, 0 cue değiştirdi", audit)
        self.assertIn(
            "Nihai Anlam Mutabakatı: açık, çalışma kaydı yok", audit)
        self.assertIn("SDH temizleme: kapalı", audit)

        row["feature_audit"] = audit
        txt = gui.build_quality_report_text(
            [row], "gpt-5.4", "Turkish", "sync", 0)
        self.assertIn("İşlem dökümü:", txt)
        self.assertIn("Native Okuyucu: çalıştı, 0 cue değiştirdi", txt)

    def test_native_failure_is_not_reported_as_successful_zero_change(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_trace": {},
            "pass_status": {"Native": {
                "status": "failed", "successful_chunks": 0,
                "failed_chunks": 3, "total_chunks": 3,
            }},
        }, {"native": True})

        self.assertIn("Native Okuyucu: başarısız, 0/3 paket başarılı", audit)
        self.assertFalse(any(
            line.startswith("Native Okuyucu: çalıştı") for line in audit))

    def test_repair_only_audit_marks_every_quality_pass_skipped(self):
        audit = gui._quality_feature_audit({
            "repair_only": True,
            "repair_missing_before": 7,
            "repair_missing_after": 0,
            "pass_trace": {"Repair": 7},
            "run_status": "done",
        }, {
            "critic": True,
            "polish": True,
            "native": True,
            "qc": True,
            "semantic_reconcile": True,
        })

        self.assertIn(
            "Yalnız Eksik Cue Onarımı: çalıştı, 7 eksikten 7 cue onarıldı, 0 eksik kaldı",
            audit)
        self.assertIn(
            "Yardımcı Analiz: kısmi onarım gereği atlandı", audit)
        self.assertIn(
            "Critic Pass: kısmi onarım gereği atlandı", audit)
        self.assertIn(
            "Nihai Anlam Mutabakatı: kısmi onarım gereği atlandı", audit)

    def test_delivery_audit_compares_real_source_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\n[MUSIC]\n\n"
                "3\n00:00:03,000 --> 00:00:04,000\nGoodbye\n",
                encoding="utf-8")
            output.write_text(
                "0\n00:00:00,000 --> 00:00:00,999\ndiscord: ceviri2\n\n"
                "1\n00:00:01,000 --> 00:00:02,000\nMerhaba\n\n"
                "3\n00:00:03,100 --> 00:00:04,000\n{\\pos(10,20)}kâğıt\n\n"
                "4\n00:00:04,000 --> 00:00:05,000\nTranslation by X\n\n"
                "5\n00:00:05,001 --> 00:00:07,000\ndiscord: ceviri2\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(str(source), str(output))

        self.assertEqual(audit["status"], "review")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["2"])
        self.assertEqual(audit["timestamp_mismatch_ids"], ["3"])
        self.assertEqual(audit["extra_dialogue_ids"], ["4"])
        self.assertEqual(audit["residual_credit_cues"], 1)
        self.assertEqual(audit["residual_position_tags"], 1)
        self.assertEqual(audit["hatted_letters"], 1)
        self.assertEqual(audit["delivery_signatures"], 2)

    def test_file_process_report_contains_full_pass_history(self):
        row = {
            "name": "episode.srt",
            "source_path": "source.srt",
            "output_path": "output.srt",
            "feature_audit": ["Native Okuyucu: çalıştı, 1 cue değiştirdi"],
            "delivery_audit": {
                "status": "ok", "source_cues": 1, "output_cues": 3,
                "missing_dialogue_ids": [], "timestamp_mismatch_ids": [],
            },
            "pass_history": {
                "7": [{"pass": "Native", "before": "Eski", "after": "Yeni"}],
            },
        }

        text = gui._file_process_report_text(row, "run-1")

        self.assertIn("ALTYAZI İŞLEM VE TESLİM DÖKÜMÜ", text)
        self.assertIn("Native Okuyucu: çalıştı, 1 cue değiştirdi", text)
        self.assertIn("#7", text)
        self.assertIn("Önce: Eski", text)
        self.assertIn("Sonra: Yeni", text)

    def test_pass_history_multi_pass_lines_are_reported(self):
        rows = [{
            "name": "a.srt",
            "total": 2,
            "pass_history": {
                "5": [{"pass": "Critic"}, {"pass": "Native"}],
                "6": [{"pass": "Polish"}],
            },
        }]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "hybrid", 0)
        self.assertIn("Çoklu-pass", txt)
        self.assertIn("#5: Critic -> Native", txt)

    def test_pass_override_lines_are_reported(self):
        rows = [{
            "name": "a.srt",
            "total": 2,
            "pass_history": {
                "5": [
                    {"pass": "Critic", "before": "A", "after": "B"},
                    {"pass": "Native", "before": "B", "after": "C"},
                ],
            },
        }]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "hybrid", 0)
        self.assertIn("Pass etkileşimi", txt)
        self.assertIn("#5: Critic -> Native (override)", txt)
        self.assertIn("Pass etkileşimleri: 1; override: 1", txt)


class RotateLogsTest(unittest.TestCase):
    def test_keeps_newest_n(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(10):
                p = d / f"log_{i:02d}.log"
                p.write_text("x", encoding="utf-8")
                ts = time.time() - (10 - i) * 60
                os.utime(p, (ts, ts))
            removed = gui.rotate_logs(d, keep=4)
            self.assertEqual(removed, 6)
            kept = sorted(p.name for p in d.glob("*.log"))
            self.assertEqual(kept, ["log_06.log", "log_07.log",
                                    "log_08.log", "log_09.log"])

    def test_fewer_than_keep_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(3):
                (d / f"l{i}.log").write_text("x", encoding="utf-8")
            self.assertEqual(gui.rotate_logs(d, keep=30), 0)
            self.assertEqual(len(list(d.glob("*.log"))), 3)

    def test_non_log_files_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "batch_errors.txt").write_text("x", encoding="utf-8")
            for i in range(5):
                (d / f"l{i}.log").write_text("x", encoding="utf-8")
            gui.rotate_logs(d, keep=2)
            self.assertTrue((d / "batch_errors.txt").exists())


if __name__ == "__main__":
    unittest.main()
