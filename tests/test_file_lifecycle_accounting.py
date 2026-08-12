"""
Deterministic unit tests for file lifecycle accounting and outcome summarization.
Directly tests gui.summarize_file_outcomes and production completion logic using stub objects.
Does NOT instantiate App() or open GUI windows.
"""
import inspect
import unittest

import subtitle_translator_gui as gui


class FileLifecycleAccountingTest(unittest.TestCase):

    def test_scenario_1_full_success_three_of_three(self):
        """Scenario 1: 3 completed out of 3 total -> full success."""
        summary = gui.summarize_file_outcomes(
            completed_files=["f1.srt", "f2.srt", "f3.srt"],
            failed_files=[],
            skipped_files=[],
            total_files=3,
            stop_flag=False,
        )
        self.assertTrue(summary["is_full_success"])
        self.assertFalse(summary["is_partial_success"])
        self.assertFalse(summary["is_failure"])
        self.assertEqual(summary["completed_count"], 3)
        self.assertEqual(summary["summary_text"], "3 dosya çevrildi")
        self.assertEqual(summary["title_text"], "Çeviri Tamamlandı ✓")

    def test_scenario_2_partial_success_two_completed_one_removed(self):
        """Scenario 2: 2 completed + 1 removed -> partial success, '2/3 dosya çevrildi'."""
        summary = gui.summarize_file_outcomes(
            completed_files=["f1.srt", "f2.srt"],
            failed_files=[],
            skipped_files=["f3.srt"],
            total_files=3,
            stop_flag=False,
        )
        self.assertFalse(summary["is_full_success"], "Must not be full success when 1 file was removed")
        self.assertTrue(summary["is_partial_success"])
        self.assertFalse(summary["is_failure"])
        self.assertEqual(summary["completed_count"], 2)
        self.assertEqual(summary["skipped_count"], 1)
        self.assertIn("2/3 dosya çevrildi", summary["summary_text"])
        self.assertIn("1 atlandı/silindi", summary["summary_text"])
        self.assertEqual(summary["title_text"], "Çeviri Kısmen Tamamlandı ⚠️")
        self.assertTrue(summary["is_recovery_complete"],
                        "Intentionally removed files must not keep recovery state alive")

    def test_scenario_3_partial_success_one_completed_one_failed_one_skipped(self):
        """Scenario 3: 1 completed + 1 failed + 1 skipped -> partial success."""
        summary = gui.summarize_file_outcomes(
            completed_files=["f1.srt"],
            failed_files=["f2.srt"],
            skipped_files=["f3.srt"],
            total_files=3,
            stop_flag=False,
        )
        self.assertFalse(summary["is_full_success"])
        self.assertTrue(summary["is_partial_success"])
        self.assertEqual(summary["completed_count"], 1)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["skipped_count"], 1)
        self.assertIn("1/3 dosya çevrildi", summary["summary_text"])
        self.assertIn("1 hata", summary["summary_text"])
        self.assertIn("1 atlandı/silindi", summary["summary_text"])
        self.assertEqual(summary["title_text"], "Çeviri Kısmen Tamamlandı ⚠️")
        self.assertFalse(summary["is_recovery_complete"])

    def test_scenario_4_stopped_run_no_full_success(self):
        """Scenario 4: 1 completed, then stopped by user -> not full success, stop summary."""
        summary = gui.summarize_file_outcomes(
            completed_files=["f1.srt"],
            failed_files=[],
            skipped_files=[],
            total_files=3,
            stop_flag=True,
        )
        self.assertFalse(summary["is_full_success"], "Stopped run must never be full success")
        self.assertFalse(summary["is_partial_success"])
        self.assertIn("Durduruldu", summary["summary_text"])
        self.assertEqual(summary["title_text"], "İşlem Durduruldu")
        self.assertFalse(summary["is_recovery_complete"])

    def test_scenario_5_all_failed_run(self):
        """Scenario 5: 0 completed + 3 failed -> failure."""
        summary = gui.summarize_file_outcomes(
            completed_files=[],
            failed_files=["f1.srt", "f2.srt", "f3.srt"],
            skipped_files=[],
            total_files=3,
            stop_flag=False,
        )
        self.assertFalse(summary["is_full_success"])
        self.assertFalse(summary["is_partial_success"])
        self.assertTrue(summary["is_failure"])
        self.assertIn("Çeviri başarısız", summary["summary_text"])
        self.assertEqual(summary["title_text"], "Çeviri Başarısız ❌")
        self.assertFalse(summary["is_recovery_complete"])

    def test_all_intentionally_removed_is_not_failure_and_can_clear_recovery(self):
        summary = gui.summarize_file_outcomes(
            completed_files=[],
            failed_files=[],
            skipped_files=["f1.srt", "f2.srt"],
            total_files=2,
            stop_flag=False,
        )
        self.assertFalse(summary["is_failure"])
        self.assertTrue(summary["is_recovery_complete"])
        self.assertEqual(summary["pending_count"], 0)
        self.assertEqual(summary["title_text"], "İşlem Tamamlandı")

    def test_unaccounted_file_is_pending_and_preserves_recovery(self):
        summary = gui.summarize_file_outcomes(
            completed_files=["f1.srt"],
            failed_files=[],
            skipped_files=[],
            total_files=2,
            stop_flag=False,
        )
        self.assertEqual(summary["pending_count"], 1)
        self.assertFalse(summary["is_recovery_complete"])
        self.assertIn("1 bekliyor", summary["summary_text"])

    def test_diff_preview_uses_last_written_file(self):
        """Verify _write_results selects the last written file for diff preview instead of unwritten files."""
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("_written_files[-1]", src,
                      "Diff preview must select from _written_files[-1] rather than file_blocks.keys()")

    def test_source_code_inspection_for_outcome_summary_integration(self):
        """Verify outcome accounting is integrated across every final write flow."""
        methods_to_check = [
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
            ("_write_results", gui.App._write_results),
            ("_run_hybrid", gui.App._run_hybrid),
        ]

        for name, method in methods_to_check:
            src = inspect.getsource(method)
            self.assertIn("summarize_file_outcomes", src,
                          f"Missing summarize_file_outcomes call in {name}")
            self.assertIn('is_recovery_complete', src,
                          f"Recovery cleanup is not tied to terminal outcomes in {name}")

    def test_write_results_marks_unresolved_output_failed_and_partial(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("_partial_output_path(out_path)", src)
        self.assertIn("_failed_files.append(fp)", src)
        self.assertIn("if _has_missing:", src)
        self.assertLess(
            src.index("_failed_files.append(fp)"),
            src.index("_written_files.append(fp)"),
        )

    def test_write_results_uses_its_captured_target_language(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn(
            "self._maybe_merge_cues(sorted_blocks, file_path=fp), _tgt_lang, self._log",
            src,
        )
        self.assertIn(
            "write_srt(_write_path, _delivery_blocks, _tgt_lang)",
            src,
        )
        self.assertIn(
            "out_path, _raw_backup_blocks, _raw_map, _tgt_lang",
            src,
        )


if __name__ == "__main__":
    unittest.main()
