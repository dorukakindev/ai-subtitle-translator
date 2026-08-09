import inspect
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui
from app_state import STATE_DIR_ENV


class BatchOwnerFailClosedTest(unittest.TestCase):
    def test_owner_marker_write_failure_is_visible(self):
        logs = []
        app = SimpleNamespace(
            _batch_lock=threading.RLock(),
            _active_batches={"batch_live": ("key", "")},
            _log=lambda *args: logs.append(args),
        )
        with patch.object(gui, "atomic_write_json", side_effect=OSError("disk full")):
            self.assertFalse(gui.App._write_batch_owner(app))

        self.assertTrue(app._batch_owner_marker_failed)
        self.assertTrue(any("sahiplik işareti" in message for message, *_ in logs))

    def test_other_live_translation_owner_suppresses_pending_actions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {STATE_DIR_ENV: tmp}):
            owner = gui._translation_run_owner_path()
            owner.write_text('{"pid": %d}' % os.getpid(), encoding="utf-8")
            with patch("os.getpid", return_value=os.getpid() + 1):
                self.assertTrue(gui._translation_run_owned_by_other_process())


class CachedFolderOutputExclusionTest(unittest.TestCase):
    def test_cached_scan_is_refiltered_when_nested_output_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "translated"
            source = root / "source.srt"
            generated = output / "episode.srt"
            app = SimpleNamespace(
                _selected_files=[],
                _input_folder_explicitly_selected=True,
                input_var=SimpleNamespace(get=lambda: str(root)),
                output_var=SimpleNamespace(get=lambda: str(output)),
                same_folder_var=SimpleNamespace(get=lambda: False),
                _file_list_root=str(root),
                _file_list_files=[str(source), str(generated)],
            )

            self.assertEqual(gui.App._get_srt_files(app), [str(source)])


class SourceDriftLifecycleTest(unittest.TestCase):
    def test_source_drift_is_a_failed_report_row_and_not_full_success(self):
        row = gui._source_drift_report_row(r"C:\\input\\episode.srt")
        summary = gui.summarize_file_outcomes(
            [r"C:\\input\\good.srt"], [row["source_path"]], total_files=2)

        self.assertEqual(row["run_status"], "error")
        self.assertFalse(summary["is_full_success"])
        self.assertEqual(summary["failed_count"], 1)

    def test_all_translation_flows_keep_drift_in_terminal_accounting(self):
        source = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("source_drift_files.append(fp)"), 2)
        self.assertIn("source_drift_files=source_drift_files", source)
        hybrid = source[source.index("def _run_hybrid"):]
        self.assertIn("_record_batch_terminal_state(\n                        ht, session, filepath, \"failed\")", hybrid)


class ResumeAndDeliveryParityTest(unittest.TestCase):
    def test_hybrid_resume_writes_required_source_fingerprint(self):
        source = inspect.getsource(gui.App._wait_batch_hybrid)
        write_at = source.index("write_srt(_write_path, _delivery_blocks, tgt)")
        fingerprint_at = source.index("_write_output_source_fingerprint", write_at)
        self.assertLess(write_at, fingerprint_at)
        self.assertIn("_delivery_scan_failed = not _fingerprint_ok", source)

    def test_completed_hybrid_session_reuses_stored_output_path(self):
        source = inspect.getsource(gui.App._run_hybrid)
        completed_at = source.index('if file_status == "completed":')
        stored_at = source.index("stored_output =", completed_at)
        audit_at = source.index("existing_audit = _subtitle_delivery_audit", completed_at)
        self.assertLess(stored_at, audit_at)

    def test_jsonl_flow_audits_written_disk_output_before_success(self):
        source = inspect.getsource(gui.App._import_jsonl)
        write_at = source.index("write_srt(_write_path, _delivery_blocks, tgt)")
        audit_at = source.index("_subtitle_delivery_audit", write_at)
        self.assertLess(write_at, audit_at)
        self.assertIn("Teslim Denetimi Başarısız", source)


if __name__ == "__main__":
    unittest.main()
