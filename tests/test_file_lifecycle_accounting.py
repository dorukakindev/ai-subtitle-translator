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

    def test_diff_preview_uses_last_written_file(self):
        """Verify _write_results selects the last written file for diff preview instead of unwritten files."""
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("_written_files[-1]", src,
                      "Diff preview must select from _written_files[-1] rather than file_blocks.keys()")

    def test_source_code_inspection_for_outcome_summary_integration(self):
        """Verify summarize_file_outcomes is integrated across _run_sync_hybrid and _write_results."""
        methods_to_check = [
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
            ("_write_results", gui.App._write_results),
        ]

        for name, method in methods_to_check:
            src = inspect.getsource(method)
            self.assertIn("summarize_file_outcomes", src,
                          f"Missing summarize_file_outcomes call in {name}")


if __name__ == "__main__":
    unittest.main()
