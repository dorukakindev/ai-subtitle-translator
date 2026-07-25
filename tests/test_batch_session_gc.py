import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import hybrid_translate as ht
from app_state import STATE_DIR_ENV


class BatchSessionGarbageCollectionTest(unittest.TestCase):
    def setUp(self):
        self._td = TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._td.name})
        self._env.start()
        self.root = ht._session_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.now = time.time()

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def _session(self, name, statuses, input_dir, age_days=120):
        path = self.root / f"{name}_session.json"
        data = {
            "input_dir": str(input_dir),
            "files": {
                f"file_{i}": {"status": status}
                for i, status in enumerate(statuses)
            },
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        old = self.now - age_days * 86400
        os.utime(path, (old, old))
        return path

    def test_only_old_safe_terminal_sessions_are_removed(self):
        existing_input = Path(self._td.name) / "input"
        existing_input.mkdir()
        missing_input = Path(self._td.name) / "gone"

        completed = self._session(
            "completed", ["completed"], existing_input)
        failed_missing = self._session(
            "failed_missing", ["failed"], missing_input)
        failed_live = self._session(
            "failed_live", ["failed"], existing_input)
        submitted = self._session(
            "submitted", ["submitted"], missing_input)
        pending = self._session(
            "pending", ["pending"], missing_input)
        recent = self._session(
            "recent", ["completed"], existing_input, age_days=2)

        removed = ht.prune_batch_sessions(now=self.now)

        self.assertEqual(removed, 2)
        self.assertFalse(completed.exists())
        self.assertFalse(failed_missing.exists())
        self.assertTrue(failed_live.exists())
        self.assertTrue(submitted.exists())
        self.assertTrue(pending.exists())
        self.assertTrue(recent.exists())

    def test_old_corrupt_file_is_isolated_from_live_sessions(self):
        corrupt = self.root / "corrupt_session.json"
        corrupt.write_text("{broken", encoding="utf-8")
        old = self.now - 120 * 86400
        os.utime(corrupt, (old, old))
        live = self._session(
            "live", ["submitted"], Path(self._td.name) / "gone")

        removed = ht.prune_batch_sessions(now=self.now)

        self.assertEqual(removed, 1)
        self.assertFalse(corrupt.exists())
        self.assertTrue(live.exists())


if __name__ == "__main__":
    unittest.main()
