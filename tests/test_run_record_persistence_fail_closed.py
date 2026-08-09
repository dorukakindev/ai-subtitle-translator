import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class RunRecordPersistenceFailClosedTest(unittest.TestCase):
    def test_failed_update_removes_stale_record_and_warns_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = root / f"active_run.{gui.os.getpid()}.json"
            state.write_text('{"status":"stale"}', encoding="utf-8")
            owner = SimpleNamespace()

            with patch.object(
                    gui, "state_path",
                    side_effect=lambda _file, *parts: root.joinpath(*parts)), \
                    patch.object(gui, "atomic_write_json",
                                 side_effect=OSError("disk unavailable")):
                persisted, message = gui._persist_active_run_record(
                    owner, {"status": "running"})
                persisted_again, second_message = gui._persist_active_run_record(
                    owner, {"status": "running"})

            self.assertFalse(persisted)
            self.assertFalse(persisted_again)
            self.assertIn("kurtarma devre dışı", message)
            self.assertEqual(second_message, "")
            self.assertFalse(state.exists())
            self.assertTrue(owner._run_record_persistence_failed)

    def test_later_success_restores_recovery_and_reports_it(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            owner = SimpleNamespace(_run_record_persistence_failed=True)

            with patch.object(
                    gui, "state_path",
                    side_effect=lambda _file, *parts: root.joinpath(*parts)):
                persisted, message = gui._persist_active_run_record(
                    owner, {"status": "running"})

            self.assertTrue(persisted)
            self.assertIn("yeniden etkinleştirildi", message)
            self.assertFalse(owner._run_record_persistence_failed)
            saved = root / f"active_run.{gui.os.getpid()}.json"
            self.assertTrue(saved.is_file())


if __name__ == "__main__":
    unittest.main()
