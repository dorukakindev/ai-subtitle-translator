import datetime
import inspect
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class RunTraceabilityTest(unittest.TestCase):
    def test_begin_run_record_builds_nested_log_path_with_two_arg_state_path(self):
        stub = SimpleNamespace(
            _active_snapshot={},
            _log_lock=threading.Lock(),
            _log_file=None,
            _run_record_lock=threading.RLock(),
            _active_run_record=None,
            _quality_issues={},
            _quality_issue_seq=0,
            _diagnostic_run_settings=lambda _snapshot: {},
            _log=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            def strict_state_path(_anchor, name):
                return root / name

            with patch.object(gui, "state_path", side_effect=strict_state_path), \
                    patch.object(gui, "_new_run_id", return_value="run-test"):
                run_id = gui.App._begin_run_record(stub, ["a.srt"])
            try:
                expected = root / "logs" / f"run_run-test.pid{gui.os.getpid()}.log"
                self.assertEqual(Path(stub._active_run_record["log_path"]), expected)
                self.assertTrue(expected.exists())
                self.assertEqual(run_id, "run-test")
                self.assertEqual(
                    stub._active_snapshot["resume_origin_run_id"], "run-test")
                self.assertEqual(
                    stub._active_run_record["settings"]["resume_origin_run_id"],
                    "run-test")
            finally:
                stub._log_file.close()

    def test_run_id_is_timestamped_and_unique_suffix_is_preserved(self):
        now = datetime.datetime(2026, 7, 28, 14, 5, 9)
        self.assertEqual(
            gui._new_run_id(now=now, suffix="abc12345"),
            "20260728-140509-abc12345")

    def test_summary_counts_files_fixes_rejections_and_artifacts(self):
        record = {
            "run_id": "run-1",
            "started_at": "2026-07-28T14:00:00",
            "ended_at": "2026-07-28T14:10:00",
            "status": "kısmen tamamlandı",
            "files": {
                "a.srt": {"status": "done"},
                "b.srt": {"status": "error"},
                "c.srt": {"status": "skip"},
            },
            "fixes_applied": 17,
            "suggestions_rejected": 4,
            "warnings": 2,
            "errors": 1,
            "outputs": ["a.tr.srt"],
            "reports": ["ceviri_raporu_run-1.txt"],
            "log_path": "run_run-1.log",
        }
        text = gui.build_run_summary_text(record)
        self.assertIn("Çalışma kimliği : run-1", text)
        self.assertIn("Tamamlanan       : 1", text)
        self.assertIn("Başarısız        : 1", text)
        self.assertIn("Düzeltme         : 17", text)
        self.assertIn("Reddedilen öneri : 4", text)
        self.assertIn("a.tr.srt", text)
        self.assertIn("b.srt", text)

    def test_api_events_are_counted_and_rendered_in_run_summary(self):
        record = {
            "run_id": "api-run", "files": {},
            "api": {
                "attempts": 2, "successes": 1, "failures": 1,
                "terminal_failures": 0, "retries": 1,
                "provider_pauses": 0, "duration_seconds": 12.5,
                "operations": {
                    "Critic Pass": {
                        "attempts": 2, "successes": 1,
                        "failures": 1, "retries": 1,
                    },
                },
            },
        }
        text = gui.build_run_summary_text(record)
        self.assertIn("API SÜRECİ", text)
        self.assertIn("Gerçek istek   : 2", text)
        self.assertIn("Yeniden deneme : 1", text)
        self.assertIn("Critic Pass: 2 istek | 1 başarılı | 1 hata | 1 tekrar", text)
        self.assertIn("başarı %50.0", text)

    def test_api_operation_renders_latency_distribution_and_fingerprint(self):
        record = {
            "run_id": "api-run", "files": {},
            "settings_fingerprint": "settings123",
            "checkpoint_origin_run_id": "origin123",
            "api": {"operations": {"Native Okuyucu": {
                "attempts": 3, "successes": 3, "failures": 0,
                "latencies": [1.0, 2.0, 9.0],
                "request_fingerprints": ["prompt123"],
            }}},
        }
        text = gui.build_run_summary_text(record)
        self.assertIn("p50 2.0 sn", text)
        self.assertIn("p95 9.0 sn", text)
        self.assertIn("max 9.0 sn", text)
        self.assertIn("İstek/prompt parmak izi: prompt123", text)
        self.assertIn("Ayar parmak izi  : settings123", text)
        self.assertIn("Checkpoint kökeni: origin123", text)

    def test_api_diagnostics_flag_only_actionable_accounting_and_retry_anomalies(self):
        findings = gui._api_diagnostic_findings({
            "operations": {
                "Critic Pass": {
                    "attempts": 4, "successes": 2, "failures": 2,
                    "terminal_failures": 1, "retries": 2,
                    "provider_pauses": 1, "duration_seconds": 10.0,
                }
            },
            "events": [{
                "event": "request_failure", "operation": "Critic Pass",
                "will_retry": False, "status_code": 503,
                "reason": "kanal yok", "request_id": "req-123",
            }],
            "usage_by_pass": {
                "Critic Pass": {
                    "total_tokens": 100, "prompt_tokens": 80,
                    "completion_tokens": 30, "cached_tokens": 90,
                    "unknown_cost_tokens": 100,
                }
            },
        })
        codes = {item["code"] for item in findings}
        self.assertTrue({
            "terminal_api_failure", "provider_circuit_pause",
            "high_failure_ratio", "retry_pressure",
            "cached_exceeds_prompt", "token_total_mismatch",
            "unknown_token_price",
        }.issubset(codes))
        terminal = next(
            item for item in findings if item["code"] == "terminal_api_failure")
        self.assertIn("HTTP 503", terminal["evidence"])
        self.assertIn("request_id=req-123", terminal["evidence"])

    def test_api_diagnostics_do_not_flag_healthy_pass(self):
        findings = gui._api_diagnostic_findings({
            "operations": {
                "Polish Pass": {
                    "attempts": 5, "successes": 5, "failures": 0,
                    "terminal_failures": 0, "retries": 0,
                    "provider_pauses": 0, "duration_seconds": 8.0,
                }
            },
            "usage_by_pass": {
                "Polish Pass": {
                    "total_tokens": 1000, "prompt_tokens": 800,
                    "completion_tokens": 200, "cached_tokens": 300,
                    "unknown_cost_tokens": 0,
                }
            },
        })
        self.assertEqual(findings, [])

    def test_api_diagnostics_reconcile_pass_ledger_and_stall_events(self):
        findings = gui._api_diagnostic_findings({
            "usage_by_pass": {"Polish Pass": {
                "total_tokens": 100, "cached_tokens": 10, "cost_usd": 0.01,
            }},
            "session_usage_delta": {
                "total_tokens": 120, "cached_tokens": 10,
                "unknown_cost_tokens": 0, "cost_usd": 0.02,
            },
            "events": [{
                "event": "request_stalled", "operation": "Polish Pass",
                "duration_seconds": 240,
            }],
        })
        codes = {item["code"] for item in findings}
        self.assertIn("usage_ledger_mismatch", codes)
        self.assertIn("cost_ledger_mismatch", codes)
        self.assertIn("slow_api_request", codes)

    def test_api_event_upgrades_legacy_operation_shape(self):
        app = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record={"api": {"operations": {
                "Polish Pass": {"attempts": 1},
            }}},
        )
        summary = gui.App._record_api_event(app, "request_success", 0, 0, {
            "checkpoint_label": "polish", "duration_seconds": 3.0,
            "request_fingerprint": "fp1", "model": "gpt-5.4",
        })
        operation = summary["operations"]["Polish Pass"]
        self.assertEqual(operation["latencies"], [3.0])
        self.assertEqual(operation["request_fingerprints"], ["fp1"])
        self.assertEqual(operation["models"], ["gpt-5.4"])

    def test_stall_thresholds_are_bounded_and_monotonic(self):
        self.assertEqual(gui._api_stall_thresholds(119), ())
        self.assertEqual(gui._api_stall_thresholds(120), (120,))
        self.assertEqual(gui._api_stall_thresholds(241), (120, 240))

    def test_record_api_event_tracks_terminal_failure_without_storing_error_body(self):
        app = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record={"api": {}},
        )
        details = {
            "checkpoint_label": "polish", "model": "gpt-5.4",
            "provider": "api.example", "attempt": 1, "max_attempts": 4,
            "duration_seconds": 2.25, "status_code": 401,
            "reason": "kimlik doğrulama", "will_retry": False,
            "raw_error": "sk-secret-must-not-be-recorded",
            "request_id": "req_support_123",
        }
        gui.App._record_api_event(app, "request_start", 0, 1, details)
        summary = gui.App._record_api_event(
            app, "request_failure", 0, 0, details)

        self.assertEqual(summary["attempts"], 1)
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["terminal_failures"], 1)
        self.assertEqual(summary["operations"]["Polish Pass"]["failures"], 1)
        self.assertEqual(
            summary["operations"]["Polish Pass"]["terminal_failures"], 1)
        self.assertEqual(
            summary["operations"]["Polish Pass"]["duration_seconds"], 2.25)
        self.assertNotIn("sk-secret", json.dumps(summary))
        self.assertEqual(summary["events"][-1]["request_id"], "req_support_123")
        self.assertFalse(summary["events"][-1]["will_retry"])

    def test_repair_retry_wait_reports_logical_retry_to_dashboard_record(self):
        statuses = []
        phases = []
        app = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record={"api": {}},
            _record_api_event=lambda *args: gui.App._record_api_event(app, *args),
            _set_status=statuses.append,
            _set_phase=lambda *args: phases.append(args),
            _motion_activity_text="",
        )
        result = gui.App._repair_retry_wait(app, 0, lambda: False)

        self.assertTrue(result)
        self.assertEqual(app._active_run_record["api"]["retries"], 1)
        self.assertEqual(phases[0][0], "Eksik Çeviri Onarımı")
        self.assertIn("gönderiliyor", statuses[-1])

    def test_file_timing_tracks_each_stage_and_renders_in_reports(self):
        item = {
            "status": "pending",
            "phase": "Bekliyor",
            "queued_at": gui._timing_iso(90),
            "queued_epoch": 90.0,
            "stage_timings": [],
        }
        gui._advance_file_timing(
            item, "Yardımcı Analiz 1/2", "running", now=100)
        gui._advance_file_timing(
            item, "Ana Çeviri 1/20", "running", now=130)
        finished = gui._advance_file_timing(
            item, "Tamamlandı", "done", now=190)

        self.assertTrue(finished)
        self.assertEqual(item["duration_seconds"], 90.0)
        self.assertEqual(
            [(stage["name"], stage["duration_seconds"])
             for stage in item["stage_timings"]],
            [("Yardımcı Analiz", 30.0), ("Ana Çeviri", 60.0)],
        )

        record = {
            "run_id": "timed-run",
            "started_at": gui._timing_iso(90),
            "ended_at": gui._timing_iso(190),
            "duration_seconds": 100.0,
            "status": "tamamlandı",
            "files": {"episode.srt": {**item, "status": "done"}},
            "fixes_applied": 0,
            "suggestions_rejected": 0,
            "warnings": 0,
            "errors": 0,
            "outputs": [],
            "reports": [],
        }
        summary = gui.build_run_summary_text(record)
        self.assertIn("DOSYA BAZLI SÜRELER", summary)
        self.assertIn("Toplam süre   : 1 dk 30 sn", summary)
        self.assertIn("Yardımcı Analiz=30.0 sn", summary)
        self.assertIn("Ana Çeviri=1 dk 00 sn", summary)

        detail = gui._file_process_report_text({
            "name": "episode.srt",
            "timing": item,
            "feature_audit": [],
        })
        self.assertIn("SÜRE ZAMAN ÇİZELGESİ", detail)
        self.assertIn("Yardımcı Analiz", detail)
        self.assertIn("Ana Çeviri", detail)

    def test_stage_timing_captures_nested_pass_api_usage_deltas(self):
        item = {
            "status": "pending", "phase": "Bekliyor",
            "queued_at": gui._timing_iso(90), "queued_epoch": 90.0,
            "stage_timings": [], "api_usage": {},
        }
        gui._advance_file_timing(
            item, "Nihai Anlam Mutabakatı", "running", now=100)
        item["api_usage"] = {
            "Geri Çeviri": {
                "total_tokens": 1200, "prompt_tokens": 900,
                "completion_tokens": 300, "cached_tokens": 100,
                "cost_usd": 0.012, "models": ["gpt-5.4"],
            },
            "Nihai Anlam Mutabakatı": {
                "total_tokens": 800, "prompt_tokens": 600,
                "completion_tokens": 200, "cached_tokens": 0,
                "cost_usd": 0.008, "models": ["gpt-5.4"],
            },
        }
        gui._advance_file_timing(item, "Dosya Yazımı", "running", now=130)

        stage = item["stage_timings"][0]
        self.assertEqual(
            set(stage["api_usage_by_pass"]),
            {"Geri Çeviri", "Nihai Anlam Mutabakatı"})
        text = gui._file_process_report_text({
            "name": "episode.srt", "timing": item, "feature_audit": [],
        })
        self.assertIn("Geri Çeviri: 1,200 token", text)
        self.assertIn("giriş 900", text)
        self.assertIn("~$0.0120", text)

    def test_phase_aliases_do_not_split_semantic_or_mislabel_tm(self):
        self.assertEqual(
            gui._timing_phase_label("Nihai Mutabakat"),
            "Nihai Anlam Mutabakatı",
        )
        self.assertEqual(
            gui._timing_phase_label("Çeviri Hafızası"),
            "Çeviri Hafızası",
        )

    def test_file_status_logs_stage_and_terminal_durations(self):
        record = {
            "files": {
                "episode.srt": {
                    "status": "pending",
                    "phase": "Bekliyor",
                    "queued_at": gui._timing_iso(90),
                    "queued_epoch": 90.0,
                    "stage_timings": [],
                }
            }
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record,
            _log=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as td, \
                patch.object(
                    gui, "_active_run_state_path",
                    return_value=Path(td) / "active.json"), \
                patch.object(gui.time, "time", side_effect=[100, 130, 190]):
            gui.App._record_file_status(
                stub, "episode.srt", "Yardımcı Analiz 1/2", "running")
            gui.App._record_file_status(
                stub, "episode.srt", "Ana Çeviri 1/20", "running")
            gui.App._record_file_status(
                stub, "episode.srt", "Tamamlandı", "done")

        messages = [call.args[0] for call in stub._log.call_args_list]
        self.assertTrue(any("Aşama tamamlandı" in msg for msg in messages))
        self.assertTrue(any("toplam 1 dk 30 sn" in msg for msg in messages))

    def test_file_status_logs_api_spend_when_stage_closes(self):
        record = {
            "files": {"episode.srt": {
                "status": "pending", "phase": "Bekliyor",
                "queued_at": gui._timing_iso(90), "queued_epoch": 90.0,
                "stage_timings": [], "api_usage": {},
            }}
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record, _log=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as td, \
                patch.object(gui, "_active_run_state_path",
                             return_value=Path(td) / "active.json"), \
                patch.object(gui.time, "time", side_effect=[100, 130]):
            gui.App._record_file_status(
                stub, "episode.srt", "Critic Pass", "running")
            record["files"]["episode.srt"]["api_usage"] = {
                "Critic Pass": {
                    "total_tokens": 2500, "cached_tokens": 500,
                    "cost_usd": 0.025, "models": ["gpt-5.4"],
                }
            }
            gui.App._record_file_status(
                stub, "episode.srt", "Polish Pass", "running")

        messages = [call.args[0] for call in stub._log.call_args_list]
        self.assertTrue(any(
            "Critic Pass: 2,500 token" in msg and "~$0.0250" in msg
            for msg in messages))

    def test_file_status_logs_per_pass_request_health_when_stage_closes(self):
        record = {
            "files": {"episode.srt": {
                "status": "pending", "phase": "Bekliyor",
                "queued_at": gui._timing_iso(90), "queued_epoch": 90.0,
                "stage_timings": [],
            }},
            "api": {"operations": {}},
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record, _log=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as td, \
                patch.object(gui, "_active_run_state_path",
                             return_value=Path(td) / "active.json"), \
                patch.object(gui.time, "time", side_effect=[100, 130]):
            gui.App._record_file_status(
                stub, "episode.srt", "Critic Pass", "running")
            record["api"]["operations"] = {
                "Critic Pass": {
                    "attempts": 2, "successes": 1, "failures": 1,
                    "terminal_failures": 0, "retries": 1,
                    "provider_pauses": 0, "duration_seconds": 12.0,
                }
            }
            gui.App._record_file_status(
                stub, "episode.srt", "Polish Pass", "running")

        messages = [call.args[0] for call in stub._log.call_args_list]
        self.assertTrue(any(
            "Critic Pass: 2 istek" in msg
            and "ort. 6.0 sn" in msg and "başarı %50.0" in msg
            for msg in messages))

    def test_all_translation_flows_feed_file_timing(self):
        expected = {
            gui.App._run_sync: ("Yardımcı Analiz", "Ana Çeviri"),
            gui.App._run_sync_hybrid: (
                "Critic Pass", "Polish Pass", "Native Okuyucu",
                "Nihai Anlam Mutabakatı", "Auto-Glossary"),
            gui.App._run_batch: ("Yardımcı Analiz", "Batch Ana Çeviri"),
            gui.App._write_results: (
                "Critic Pass", "Polish Pass", "Native Okuyucu",
                "Nihai Anlam Mutabakatı", "Auto-Glossary"),
            gui.App._run_hybrid: (
                "Yardımcı Analiz", "Batch Ana Çeviri", "Critic Pass",
                "Polish Pass", "Native Okuyucu", "Nihai Anlam Mutabakatı",
                "Auto-Glossary"),
        }
        for method, labels in expected.items():
            source = inspect.getsource(method)
            for label in labels:
                if label == "Nihai Anlam Mutabakatı":
                    self.assertIn(
                        "self._run_final_semantic_checks(", source,
                        f"{method.__name__}: {label}")
                    continue
                self.assertIn(label, source, f"{method.__name__}: {label}")

        report_source = inspect.getsource(gui.App._save_quality_report)
        self.assertIn("_file_timing_snapshot", report_source)

    def test_diagnostic_settings_never_include_api_keys(self):
        snapshot = {
            "input_dir": "C:/in",
            "output_dir": "C:/out",
            "main_model_name": "gpt-5.4",
            "main_api_key": "sk-secret-main",
            "helper_keys": {"critic": "sk-secret-helper"},
            "helper_models": {"critic": "gpt-5.4-mini"},
            "helper_urls": {"critic": "https://example.test/v1"},
        }
        result = gui.App._diagnostic_run_settings(SimpleNamespace(), snapshot)
        serialized = str(result)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("main_api_key", result)
        self.assertNotIn("helper_keys", result)
        self.assertEqual(result["main_model_name"], "gpt-5.4")

    def test_diagnostic_settings_preserve_recovery_build_parameters(self):
        snapshot = {
            "chunk_size": 25,
            "context_lines": 20,
            "lookahead_lines": 10,
            "max_workers": 2,
            "temperature": 0.2,
            "max_retry": 3,
            "scene_gap_seconds": 3.0,
            "crash_resume": True,
            "resume_origin_run_id": "run-original",
        }

        result = gui.App._diagnostic_run_settings(SimpleNamespace(), snapshot)

        for key, value in snapshot.items():
            self.assertEqual(result[key], value)

    def test_quality_warning_carries_source_and_translation_for_click(self):
        issues = []
        log_calls = []
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Hello there")]
        warnings = gui.scan_translation_quality(
            "sample.srt", blocks,
            src_clean_map={"1": "Hello there"},
            issue_fn=lambda issue: issues.append(issue) or "issue-1",
            log_fn=lambda message, tag, **kwargs:
                log_calls.append((message, tag, kwargs)))
        self.assertGreaterEqual(warnings, 1)
        self.assertEqual(issues[0]["items"][0]["id"], "1")
        self.assertEqual(issues[0]["items"][0]["source"], "Hello there")
        self.assertEqual(issues[0]["items"][0]["translation"], "Hello there")
        self.assertEqual(log_calls[0][2]["issue_id"], "issue-1")

    def test_rejected_suggestion_count_is_collected_from_logs(self):
        record = {
            "suggestions_rejected": 0, "warnings": 0, "errors": 0,
            "outputs": [], "reports": [],
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record)
        gui.App._record_log_metadata(
            stub, "109 küme güvenlik filtresinden döndü", "warn")
        self.assertEqual(record["suggestions_rejected"], 109)
        self.assertEqual(record["warnings"], 1)

    def test_finalize_persists_id_linked_text_json_and_last_record(self):
        record = {
            "run_id": "20260728-140509-abc12345",
            "started_at": "2026-07-28T14:05:09",
            "ended_at": "",
            "status": "çalışıyor",
            "settings": {"input_dir": "C:/in", "output_dir": "C:/out"},
            "files": {"a.srt": {"status": "done", "phase": "Tamamlandı"}},
            "fixes_applied": 2,
            "suggestions_rejected": 1,
            "warnings": 0,
            "errors": 0,
            "outputs": ["a.tr.srt"],
            "reports": [],
            "log_path": "run.log",
            "last_traceback": "",
            "api": {
                "operations": {
                    "Critic Pass": {
                        "attempts": 1, "successes": 0, "failures": 1,
                        "terminal_failures": 1, "retries": 0,
                        "provider_pauses": 0, "duration_seconds": 1.0,
                    }
                }
            },
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record,
            _last_run_record=None,
            _stop_flag=False,
            _log=MagicMock(),
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            active_path = root / f"active_run.{os.getpid()}.json"
            active_path.write_text("{}", encoding="utf-8")
            with patch.object(gui, "_resolve_report_dir", return_value=root), \
                    patch.object(
                        gui, "state_path",
                        side_effect=lambda _file, *parts: root.joinpath(*parts)):
                result = gui.App._finalize_run_record(stub)
            txt_path = root / "calistirma_20260728-140509-abc12345_ozet.txt"
            json_path = root / "calistirma_20260728-140509-abc12345_ozet.json"
            last_path = root / "last_run_summary.json"
            self.assertTrue(txt_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(last_path.exists())
            self.assertFalse(active_path.exists())
            self.assertEqual(
                json.loads(last_path.read_text(encoding="utf-8"))["run_id"],
                result["run_id"])
            saved = json.loads(last_path.read_text(encoding="utf-8"))
            self.assertEqual(
                saved["api"]["diagnostics"][0]["code"],
                "terminal_api_failure")
            self.assertTrue(any(
                "API teşhisi" in call.args[0]
                for call in stub._log.call_args_list))
        self.assertIsNone(stub._active_run_record)
        self.assertEqual(stub._last_run_record["status"], "tamamlandı")

    def test_stopped_run_keeps_pending_files_for_next_startup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            done = root / "done.srt"
            pending = root / "pending.srt"
            done.write_text("done", encoding="utf-8")
            pending.write_text("pending", encoding="utf-8")
            record = {
                "run_id": "run-stopped",
                "pid": 123,
                "process_start": "win:old",
                "started_at": "2026-08-01T01:00:00",
                "ended_at": "",
                "status": "çalışıyor",
                "settings": {
                    "input_dir": str(root),
                    "output_dir": str(root / "out"),
                    "mode": "sync",
                },
                "files": {
                    str(done): {"status": "done", "phase": "Tamamlandı"},
                    str(pending): {"status": "running", "phase": "Çeviri"},
                },
                "fixes_applied": 0,
                "suggestions_rejected": 0,
                "warnings": 0,
                "errors": 0,
                "outputs": [],
                "reports": [],
                "completion_markers": [],
                "log_path": "run.log",
                "last_traceback": "",
            }
            stub = SimpleNamespace(
                _run_record_lock=threading.RLock(),
                _active_run_record=record,
                _last_run_record=None,
                _stop_flag=True,
                _log=MagicMock(),
            )
            with patch.object(gui, "_resolve_report_dir", return_value=root), \
                    patch.object(gui, "_write_completion_markers", return_value=[]), \
                    patch.object(
                        gui, "state_path",
                        side_effect=lambda _file, *parts: root.joinpath(*parts)):
                result = gui.App._finalize_run_record(stub)

            active = json.loads(
                (root / f"active_run.{os.getpid()}.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(result["status"], "durduruldu")
            self.assertEqual(result["resume_pending"], [str(pending)])
            self.assertEqual(active["resume_pending"], [str(pending)])
            self.assertEqual(active["files"][str(done)]["status"], "done")

    def test_interrupted_record_ignores_reused_pid_but_not_same_process(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "active_run.json"
            path.write_text(json.dumps({
                "pid": 123,
                "process_start": "win:old",
                "files": {},
            }), encoding="utf-8")
            with patch.object(gui, "_active_run_state_path", return_value=path), \
                    patch.object(gui, "_pid_alive", return_value=True), \
                    patch.object(gui, "_process_start_marker", return_value="win:new"):
                self.assertIsNotNone(gui._load_interrupted_run_record())
            with patch.object(gui, "_active_run_state_path", return_value=path), \
                    patch.object(gui, "_pid_alive", return_value=True), \
                    patch.object(gui, "_process_start_marker", return_value="win:old"):
                self.assertIsNone(gui._load_interrupted_run_record())

    def test_quality_report_embeds_run_id(self):
        text = gui.build_quality_report_text(
            [{"name": "a.srt", "total": 1}],
            "gpt-5.4", "Turkish", "sync", 10,
            run_id="20260728-140509-abc12345")
        self.assertIn(
            "Çalışma kimliği: 20260728-140509-abc12345", text)

    def test_log_header_exposes_summary_and_diagnostic_buttons(self):
        source = inspect.getsource(gui.App._build_main)
        self.assertIn('text="🩺 Tanı Paketi"', source)
        self.assertIn('text="Son Özet"', source)
        self.assertIn("command=self._copy_diagnostic_package", source)


if __name__ == "__main__":
    unittest.main()
