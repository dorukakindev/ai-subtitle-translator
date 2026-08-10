import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui


class _FailingTemp:
    def __init__(self, path):
        self.name = str(path)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def write(self, _value):
        raise OSError("disk full")


class BatchTempCleanupTest(unittest.TestCase):
    def test_write_failure_removes_created_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            created = root / "batch_input_leftover.jsonl"
            created.touch()
            recovery_files = [
                root / "batch_id.txt",
                root / "batch_intent_run_0.json",
                root / "active_run.json",
            ]
            for recovery_file in recovery_files:
                recovery_file.write_text("keep", encoding="utf-8")
            with patch.object(gui, "state_dir", return_value=root), \
                    patch("tempfile.NamedTemporaryFile", return_value=_FailingTemp(created)):
                with self.assertRaisesRegex(OSError, "disk full"):
                    gui._write_batch_jsonl_temp([{"custom_id": "x"}], "batch_input_")
            self.assertFalse(created.exists())
            for recovery_file in recovery_files:
                self.assertEqual(recovery_file.read_text(encoding="utf-8"), "keep")

    def test_successful_write_returns_uploadable_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with patch.object(gui, "state_dir", return_value=root):
                path = gui._write_batch_jsonl_temp(
                    [{"custom_id": "x"}], "batch_input_")
            try:
                self.assertEqual(path.read_text(encoding="utf-8"), '{"custom_id": "x"}\n')
            finally:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
