"""
build_quality_report_text, _count_hata_cps ve rotate_logs testleri.
"""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

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
        self.assertEqual(trace["Critic"], 1)
        self.assertEqual(trace["__pass_snapshots__"][0]["changed"], 1)
        self.assertFalse(trace["__pass_snapshots__"][0]["rolled_back"])
        self.assertEqual(history["1"][0]["pass"], "Critic")
        self.assertEqual(history["1"][0]["before"], "A")
        self.assertEqual(history["1"][0]["after"], "B")

    def test_record_pass_change_keeps_zero_change_execution(self):
        trace = {}
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "A")]

        self.assertEqual(
            gui._record_pass_change(trace, "Native", blocks, list(blocks)), 0)
        self.assertEqual(trace["Native"], 0)
        self.assertEqual(trace["__pass_snapshots__"][0]["changed"], 0)

    def test_pass_guard_rolls_back_structural_corruption(self):
        trace = {}
        before = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Güle güle."),
        ]
        after = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Selam."),
            ("1", "00:00:02,000 --> 00:00:03,000", "[ÇEVİRİ EKSİK]"),
        ]

        self.assertEqual(
            gui._record_pass_change(trace, "Critic", before, after), 0)
        self.assertEqual(after, before)
        event = trace["__guard_events__"][0]
        self.assertIn("duplicate_cue_id", event["reason"])
        self.assertIn("cue_ids_changed", event["reason"])
        self.assertIn("new_unresolved_marker", event["reason"])
        self.assertTrue(trace["__pass_snapshots__"][0]["rolled_back"])

    def test_pass_efficiency_reports_zero_yield_without_division(self):
        rows = gui._pass_efficiency_rows({
            "pass_trace": {"Native": 0, "Critic": 2},
            "timing": {"api_usage": {
                "Native Okuyucu": {"total_tokens": 900, "cost_usd": 0.09},
                "Critic Pass": {"total_tokens": 400, "cost_usd": 0.04},
            }},
        })
        native = next(item for item in rows if item["pass"] == "Native")
        critic = next(item for item in rows if item["pass"] == "Critic")
        self.assertIsNone(native["tokens_per_change"])
        self.assertEqual(critic["tokens_per_change"], 200.0)

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
    def test_empty_run_replaces_stale_latest_quality_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report_dir = root / "Raporlar"
            report_dir.mkdir()
            latest = report_dir / "ceviri_raporu.txt"
            latest.write_text("OLD RUN", encoding="utf-8")
            recorded = []
            logs = []
            app = SimpleNamespace(
                _run_record_lock=threading.RLock(),
                _active_run_record={"run_id": "run-new"},
                input_var=SimpleNamespace(get=lambda: str(root / "input")),
                _record_quality_report=lambda rows, paths: recorded.append(
                    (rows, paths)),
                _log=lambda message, tag: logs.append((message, tag)),
            )

            result = gui.App._save_quality_report(app, [], str(root))

            self.assertEqual(result, latest)
            self.assertNotIn("OLD RUN", latest.read_text(encoding="utf-8"))
            self.assertIn("run-new", latest.read_text(encoding="utf-8"))
            self.assertEqual(recorded[0][0], [])
            self.assertTrue((report_dir / "ceviri_raporu.json").is_file())

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

    def test_cps_summary_uses_weighted_average_and_real_maximum(self):
        rows = [
            {"name": "a.srt", "total": 100, "cps_avg": 10.0, "cps_max": 20.0},
            {"name": "b.srt", "total": 300, "cps_avg": 20.0, "cps_max": 30.0},
        ]

        txt = gui.build_quality_report_text(
            rows, "gpt-5.4-mini", "Turkish", "sync", 0)

        summary = txt.split("TOPLAM:", 1)[1]
        self.assertIn("Ortalama CPS: 17.5", summary)
        self.assertIn("Maksimum CPS: 30.0", summary)
        self.assertNotIn("Maksimum CPS: 50", summary)


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
            "context_payload_metrics": {"chunks": 4, "prev_tr_chunks": 3},
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
        self.assertIn(
            "Zincirleme Bağlam: çalıştı, 3/4 chunk önceki çeviriyi aldı",
            audit)
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

    def test_consistency_failure_overrides_zero_change_trace(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_trace": {"Consistency": 0},
            "pass_status": {"Consistency": {
                "status": "failed", "successful_chunks": 0,
                "failed_chunks": 1, "total_chunks": 1,
            }},
        }, {})

        self.assertIn(
            "Tutarlılık taraması: başarısız, 0/1 paket başarılı", audit)
        self.assertFalse(any(
            line.startswith("Tutarlılık taraması: çalıştı") for line in audit))

    def test_review_failure_is_not_reported_as_successful_zero_change(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "review_expected": True,
            "pass_trace": {"Review": 0},
            "pass_status": {"Review": {
                "status": "failed", "successful_chunks": 0,
                "failed_chunks": 2, "total_chunks": 2,
            }},
        }, {})

        self.assertIn(
            "Bağlam İncelemesi: başarısız, 0/2 paket başarılı", audit)
        self.assertFalse(any(
            line.startswith("Bağlam İncelemesi: çalıştı") for line in audit))

    def test_auto_glossary_failure_is_not_reported_as_no_suggestions(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_status": {"Auto-Glossary": {
                "status": "failed", "successful_chunks": 0,
                "failed_chunks": 1, "total_chunks": 1,
            }},
        }, {"auto_glossary": True})

        self.assertIn("Auto-Glossary: başarısız", audit)
        self.assertNotIn("Auto-Glossary: çalıştı, 0 öneri, 0 terim eklendi", audit)

    def test_auto_glossary_success_reports_suggestions_and_writes(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_status": {"Auto-Glossary": {
                "status": "completed", "suggested": 4, "written": 2,
            }},
        }, {"auto_glossary": True})

        self.assertIn(
            "Auto-Glossary: çalıştı, 4 öneri, 2 terim eklendi", audit)

    def test_series_memory_save_failure_is_visible(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_status": {"Series-Memory": {"status": "failed"}},
        }, {"series_memory": True})

        self.assertIn("Dizi Hafızası: başarısız", audit)

    def test_non_series_memory_skip_is_not_reported_as_success(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_status": {"Series-Memory": {
                "status": "skipped", "reason": "not_series",
            }},
        }, {"series_memory": True})

        self.assertIn(
            "Dizi Hafızası: atlandı, dizi bölümü algılanmadı", audit)

    def test_expensive_final_pass_failures_are_not_reported_as_zero_change(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_trace": {
                "Condense": 0, "Term-Normalize": 0, "Final-Semantic": 0,
            },
            "pass_status": {
                "Backtranslation": {
                    "status": "failed", "successful_chunks": 0,
                    "failed_chunks": 2, "total_chunks": 2,
                },
                "Condense": {
                    "status": "failed", "successful_chunks": 0,
                    "failed_chunks": 1, "total_chunks": 1,
                },
                "Term-Normalize": {
                    "status": "partial", "successful_chunks": 1,
                    "failed_chunks": 1, "total_chunks": 2,
                },
                "Final-Semantic": {
                    "status": "failed", "successful_chunks": 0,
                    "failed_chunks": 3, "total_chunks": 3,
                },
            },
        }, {
            "backtrans": True,
            "condense": True,
            "term_normalize": True,
            "semantic_reconcile": True,
        })

        self.assertIn(
            "Geri Çeviri: başarısız, 0/2 paket başarılı", audit)
        self.assertIn(
            "Okuma Hızı Kısaltma: başarısız, 0/1 paket başarılı", audit)
        self.assertIn(
            "Terim Normalizasyonu: kısmi tamamlandı, 1/2 paket başarılı", audit)
        self.assertIn(
            "Nihai Anlam Mutabakatı: başarısız, 0/3 paket başarılı", audit)

    def test_successful_qc_with_no_issues_is_reported_as_completed(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_trace": {},
            "pass_status": {"QC": {
                "status": "completed", "successful_chunks": 2,
                "failed_chunks": 0, "total_chunks": 2, "changed": 0,
            }},
        }, {"qc": True})

        self.assertIn("QC: çalıştı, 0 cue değiştirdi", audit)

    def test_disabled_zero_trace_pass_is_not_reported_as_executed(self):
        audit = gui._quality_feature_audit({
            "run_status": "done",
            "pass_trace": {"Final-Semantic": 0, "Condense": 0},
        }, {
            "semantic_reconcile": False,
            "condense": False,
        })

        self.assertIn("Nihai Anlam Mutabakatı: kapalı", audit)
        self.assertIn("Okuma Hızı Kısaltma: kapalı", audit)
        self.assertNotIn(
            "Nihai Anlam Mutabakatı: çalıştı, 0 cue değiştirdi", audit)
        self.assertNotIn(
            "Okuma Hızı Kısaltma: çalıştı, 0 cue değiştirdi", audit)

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
            "Bağlam İncelemesi: kısmi onarım gereği atlandı", audit)
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
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))
        self.assertEqual(audit["residual_credit_cues"], 1)
        self.assertEqual(audit["residual_position_tags"], 1)
        self.assertEqual(audit["hatted_letters"], 1)
        self.assertEqual(audit["delivery_signatures"], 2)

    def test_delivery_audit_accepts_legitimate_merged_cues(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nI do\n\n"
                "2\n00:00:02,100 --> 00:00:03,000\nnot know.\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nBilmiyorum.\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["extra_dialogue_ids"], [])
        self.assertFalse(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_audit_reports_cross_sentence_named_content_swap(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source_blocks = [
                ("1", "00:00:01,000 --> 00:00:02,000", "John arrived."),
                ("2", "00:00:03,000 --> 00:00:04,000", "Mary waited."),
            ]
            translated = [
                ("1", "00:00:01,000 --> 00:00:02,000", "Mary bekledi."),
                ("2", "00:00:03,000 --> 00:00:04,000", "John geldi."),
            ]
            gui.write_srt(source, source_blocks, "English")
            gui.write_srt(
                output,
                gui._prepare_upload_ready_blocks(translated, "Turkish"),
                "Turkish")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="Turkish")

        self.assertEqual(audit["delivery_owner_mismatch_ids"], ["1", "3"])
        self.assertEqual(audit["status"], "review")
        self.assertFalse(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_owner_map_allows_natural_fragment_information_shift(self):
        source_rows = [
            ("1", "00:00:01,000 --> 00:00:02,000", "John did not"),
            ("2", "00:00:02,001 --> 00:00:03,000", "leave Mary."),
        ]

        owner_map = gui._delivery_owner_source_map(
            source_rows, {"1": "1", "2": "2"})
        mismatches = gui._chunk_content_owner_mismatch_ids([
            {"i": "1", "t": "John, Mary'yi"},
            {"i": "2", "t": "terk etmedi."},
        ], owner_map)

        self.assertEqual(mismatches, set())

    def test_delivery_audit_hard_gates_extra_dialogue_without_credit_text(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nMerhaba\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\nKaynakta olmayan satır\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")

        self.assertEqual(audit["extra_dialogue_ids"], ["2"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_audit_hard_gates_shifted_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,100 --> 00:00:02,000\nMerhaba\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")

        self.assertEqual(audit["timestamp_mismatch_ids"], ["1"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_audit_counts_music_stars_as_expected_removal(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n**\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\n[ Speaks indistinctly ]\n\n"
                "3\n00:00:03,000 --> 00:00:04,000\n* [ Chanting ] *\n\n"
                "4\n00:00:04,000 --> 00:00:05,000\n[ Suspenseful chord strikes ]\n\n"
                "5\n00:00:05,000 --> 00:00:06,000\n* [ Rattling ]\n\n"
                "6\n00:00:06,000 --> 00:00:07,000\nHello\n",
                encoding="utf-8")
            output.write_text(
                "6\n00:00:06,000 --> 00:00:07,000\nMerhaba\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2", "3", "4", "5"])

    def test_delivery_audit_treats_wrapped_sound_of_as_expected_sdh(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n(LOUDER SOUND OF CHILDREN)\n\n"
                "2\n00:00:02,000 --> 00:00:03,000\n(SOUND OF HAIR DRYERS)\n\n"
                "3\n00:00:03,000 --> 00:00:04,000\nHello\n",
                encoding="utf-8")
            output.write_text(
                "3\n00:00:03,000 --> 00:00:04,000\nMerhaba\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English")

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2"])

    def test_delivery_audit_treats_verified_bare_french_sdh_as_expected(self):
        descriptions = [
            "Musique d'intrigue", "Il rit", "Smacks",
            "Chants des oiseaux", "On frappe aux carreaux",
            "Elle ouvre le robinet L'eau coule", "Grondement du moteur",
            "Moteurs de machines",
        ]
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text("\n\n".join(
                f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},500\n{text}"
                for i, text in enumerate(descriptions, 1)
            ) + "\n\n9\n00:00:09,000 --> 00:00:09,500\nBonjour\n",
                encoding="utf-8")
            output.write_text(
                "9\n00:00:09,000 --> 00:00:09,500\nMerhaba\n",
                encoding="utf-8")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="English",
                source_language="French")

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], [str(i) for i in range(1, 9)])

    def test_delivery_audit_hard_gates_exact_untranslated_line_fragment(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source_blocks = [(
                "1", "00:00:01,000 --> 00:00:03,000",
                "I'm Allan Jordan,\nMrs. Regnier's lawyer.")]
            translated = [(
                "1", "00:00:01,000 --> 00:00:03,000",
                "Ben Allan Jordan,\nMrs. Regnier's lawyer.")]
            gui.write_srt(source, source_blocks, "English")
            gui.write_srt(
                output, gui._prepare_upload_ready_blocks(translated, "Turkish"),
                "Turkish")

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), target_language="Turkish",
                source_language="English")

        self.assertEqual(audit["untranslated_fragment_ids"], ["1"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_fragment_guard_preserves_proper_names_and_titles(self):
        flagged = gui._delivery_untranslated_fragment_ids(
            [("1", "00:00:01,000 --> 00:00:02,000",
              "Friends' Bar\nAllan Jordan\nSlovenský filmový ústav\nsunar")],
            {"1": "Friends' Bar\nAllan Jordan\nSlovenský filmový ústav\npresents"},
            target_language="Turkish", source_language="English")

        self.assertEqual(flagged, [])

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

    def test_owner_mismatch_ids_are_visible_in_both_delivery_reports(self):
        audit = {
            "status": "review", "source_cues": 2, "output_cues": 2,
            "missing_dialogue_ids": [], "timestamp_mismatch_ids": [],
            "delivery_owner_mismatch_ids": ["4", "5"],
        }
        row = {"name": "episode.srt", "total": 2, "delivery_audit": audit}

        summary = gui.build_quality_report_text(
            [row], "gpt-5.4-mini", "Turkish", "sync", 0)
        detail = gui._file_process_report_text(row, "run-1")

        self.assertIn("Kaynak-cue sahiplik incelemesi (rapor): 2 cue (4, 5)",
                      summary)
        self.assertIn("Kaynak-cue sahiplik inceleme kimlikleri: 4, 5", detail)

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

    def test_unresolved_single_attempt_repair_is_explicit_in_report(self):
        rows = [{
            "name": "a.srt",
            "total": 1,
            "pass_trace": {
                "__repair_advisories__": [{
                    "id": "8",
                    "reason": "identical_source",
                    "source": "Please come here.",
                    "candidate": "Please come here.",
                    "unresolved": True,
                }],
            },
        }]
        txt = gui.build_quality_report_text(
            rows, "gpt-5.4-mini", "Turkish", "hybrid", 0)
        self.assertIn("[ONARILAMADI] #8: identical_source", txt)
        self.assertIn("Please come here.", txt)


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
