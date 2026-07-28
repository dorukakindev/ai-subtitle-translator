import datetime
import inspect
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class RunTraceabilityTest(unittest.TestCase):
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
            self.assertEqual(
                json.loads(last_path.read_text(encoding="utf-8"))["run_id"],
                result["run_id"])
        self.assertIsNone(stub._active_run_record)
        self.assertEqual(stub._last_run_record["status"], "tamamlandı")

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
