import inspect
import re
import tempfile
import threading
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class QualityFlowFailClosedTests(unittest.TestCase):
    def test_invalid_minute_and_second_values_are_rejected(self):
        for value in ("00:60:00,000", "00:00:60,000", "01:99:99.999"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    gui._srt_timestamp_ms(value)

    def test_delivery_audit_flags_out_of_range_timestamp(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.srt"
            output = Path(td) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello.\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:60:01,000 --> 00:60:02,000\nMerhaba.\n",
                encoding="utf-8")
            audit = gui._subtitle_delivery_audit(
                str(source), str(output), "English", "English")
            self.assertEqual(audit["invalid_timestamp_ids"], ["1"])
            self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_partial_orchestration_exception_is_a_hard_failure(self):
        self.assertTrue(gui._quality_pass_has_hard_failure({
            "Post-processing": {"status": "partial"},
        }))
        self.assertFalse(gui._quality_pass_has_hard_failure({
            "Critic": {"status": "partial"},
        }))

    def test_plain_result_flow_records_caught_quality_pass_failures(self):
        source = inspect.getsource(gui.App._write_results)
        for name in ("Critic", "Polish", "Native", "QC", "Post-processing"):
            with self.subTest(name=name):
                self.assertIn(f'_pass_status["{name}"]', source)
        self.assertGreaterEqual(source.count('"status": "failed"'), 5)

    def test_hybrid_review_failures_are_recorded(self):
        for method in (gui.App._wait_batch_hybrid, gui.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                review_catch = source.index('f"Bağlam incelemesi hatası: {e}"')
                status_write = source.rfind('_pass_status["Review"]', 0, review_catch)
                self.assertGreater(status_write, -1)

    def test_resume_without_source_cannot_be_completed(self):
        source = inspect.getsource(gui.App._wait_batch_hybrid)
        missing_source = source.index("if _orig_cues is None:")
        partial_move = source.index("_move_stage_to_partial", missing_source)
        failed_status = source.index('result_out["status"] = "failed"', partial_move)
        stop_branch = source.index("break", failed_status)
        consistency = source.index("ht.consistency_sweep", stop_branch)
        self.assertLess(missing_source, partial_move)
        self.assertLess(partial_move, failed_status)
        self.assertLess(failed_status, stop_branch)
        self.assertLess(stop_branch, consistency)

    def test_sync_hybrid_clears_checkpoint_after_quality_gate(self):
        source = inspect.getsource(gui.App._run_sync_hybrid)
        gate = source.index("if _has_missing or _delivery_scan_failed or _quality_pass_failed:")
        clear = source.index("_clear_sync_stage_ckpt(filepath)", gate)
        self.assertLess(gate, clear)

    def test_all_output_flows_audit_written_file_before_completion(self):
        methods_and_completion = (
            (gui.App._run_sync_hybrid, "_clear_sync_stage_ckpt(filepath)"),
            (gui.App._wait_batch_hybrid, '_resume_quality_failed = ('),
            (gui.App._write_results, "_quality_pass_failed ="),
            (gui.App._run_hybrid, "_hybrid_quality_failed ="),
        )
        for method, completion_marker in methods_and_completion:
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                write = source.index("write_srt(")
                audit = source.index("_subtitle_delivery_audit(", write)
                completion = source.index(completion_marker, audit)
                self.assertLess(write, audit)
                self.assertLess(audit, completion)

    def test_manual_quality_passes_are_structure_guarded_before_write(self):
        source = inspect.getsource(gui.App._run_post_process)
        guard = source.index("_pass_structure_guard_reason")
        final_write = source.index("write_srt(fp, _delivery_blocks", guard)
        self.assertGreaterEqual(source.count("_pass_structure_guard_reason"), 2)
        self.assertLess(guard, final_write)

    def test_report_fix_count_is_recomputed_after_final_passes(self):
        for method in (
                gui.App._run_sync_hybrid,
                gui.App._write_results,
                gui.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                report = source.rindex('"pass_fix": _pass_fix')
                recompute = source.rfind("_pass_fix = sum(", 0, report)
                semantic = source.rfind("_run_final_semantic_checks(", 0, report)
                self.assertGreater(recompute, semantic)

    def test_quality_callbacks_use_explicit_pass_and_file_attribution(self):
        methods = (
            gui.App._run_post_process,
            gui.App._run_quality_check_inline,
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        )
        unsafe = re.compile(
            r'_token_callback_for_model\(\s*self\._helper_api_model\('
            r'"(?:critic|qc|polish)"\)')
        for method in methods:
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertIsNone(unsafe.search(source))
                self.assertIn("_token_callback_for_pass", source)
                self.assertIn("file_path=", source)
        for method in (
                gui.App._maybe_backtranslation_check,
                gui.App._maybe_semantic_reconciliation):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertIn("base_url=", source)
                self.assertIn("file_path=", source)

    def test_multi_file_usage_is_recorded_only_on_explicit_target(self):
        class Owner:
            pass

        owner = Owner()
        owner._run_record_lock = threading.RLock()
        owner._active_run_record = {
            "api": {},
            "files": {
                "first.srt": {"active_stage": "Critic Pass"},
                "second.srt": {"active_stage": "Native Okuyucu"},
            },
        }
        gui.App._record_api_usage(
            owner, 125, 10, 0.0, 125, "gpt-test",
            100, 25, "Native Okuyucu", "second.srt", True)
        files = owner._active_run_record["files"]
        self.assertNotIn("api_usage", files["first.srt"])
        usage = files["second.srt"]["api_usage"]["Native Okuyucu"]
        self.assertEqual(usage["total_tokens"], 125)
        self.assertEqual(usage["cached_tokens"], 10)
        global_usage = owner._active_run_record["api"]["usage_by_pass"]
        self.assertIn("Native Okuyucu", global_usage)


if __name__ == "__main__":
    unittest.main()
