import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class _InlineThread:
    def __init__(self, target, daemon=True):
        self.target = target

    def start(self):
        self.target()


class ResumeLifecycleTest(unittest.TestCase):
    def _app(self):
        running = []
        stats = [MagicMock() for _ in range(4)]
        tm = MagicMock()
        app = SimpleNamespace(
            _is_running=False,
            _validate=lambda: "sk-test",
            _save_settings=MagicMock(),
            _stop_flag=True,
            _active_snapshot=None,
            _take_run_snapshot=lambda: {"run": "resume"},
            _pause_btw_files=threading.Event(),
            _batch_lock=threading.RLock(),
            _active_batches={"old": ("key", "")},
            _tm=tm,
            stat_tokens_var=stats[0],
            stat_done_var=stats[1],
            stat_fail_var=stats[2],
            stat_tm_var=stats[3],
            _set_eta=MagicMock(),
            _set_running=lambda value: running.append(value),
            _resume_batches=MagicMock(),
            _log=MagicMock(),
            _log_exc=MagicMock(),
        )
        return app, running, stats, tm

    def test_valid_resume_resets_accounting_and_enters_running_before_worker(self):
        app, running, stats, tm = self._app()
        with TemporaryDirectory() as td:
            bid_path = Path(td) / "batch_id.txt"
            bid_path.write_text("batch_ABC123\n", encoding="utf-8")

            def resume_batches(key, batch_ids):
                self.assertEqual(running, [True])
                self.assertEqual(key, "sk-test")
                self.assertEqual(batch_ids, ["batch_ABC123"])

            app._resume_batches.side_effect = resume_batches
            with patch.object(gui, "_batch_id_path", return_value=bid_path), \
                 patch.object(gui.threading, "Thread", _InlineThread):
                gui.App._resume(app)

        self.assertEqual(running, [True])
        self.assertEqual(app._token_total, 0)
        self.assertEqual(app._token_cached, 0)
        self.assertEqual(app._cost_total, 0.0)
        tm.reset_session_hits.assert_called_once_with()
        for stat in stats:
            stat.set.assert_called_once_with("0")
        app._set_eta.assert_called_once_with("")

    def test_invalid_batch_file_never_enters_running_or_resets_accounting(self):
        app, running, _stats, tm = self._app()
        with TemporaryDirectory() as td:
            bid_path = Path(td) / "batch_id.txt"
            bid_path.write_text("\n", encoding="utf-8")
            with patch.object(gui, "_batch_id_path", return_value=bid_path), \
                 patch.object(gui.messagebox, "showerror"):
                gui.App._resume(app)

        self.assertEqual(running, [])
        tm.reset_session_hits.assert_not_called()
        app._resume_batches.assert_not_called()


class BatchOwnerCancellationTest(unittest.TestCase):
    def test_clearing_active_batches_updates_owner_before_remote_cancel(self):
        events = []
        app = SimpleNamespace(
            _batch_lock=threading.RLock(),
            _active_batches={"batch_A": ("sk-test", "")},
            _write_batch_owner=lambda: events.append("owner"),
            _clear_batch_recovery=lambda ids: events.append(("recovery", tuple(ids))),
            _log=MagicMock(),
        )
        client = MagicMock()
        client.batches.cancel.side_effect = lambda bid: events.append(("cancel", bid))

        with patch.object(gui, "OpenAI", return_value=client):
            gui.App._cancel_active_batches(app)

        self.assertEqual(events[0], "owner")
        self.assertEqual(app._active_batches, {})
        self.assertIn(("cancel", "batch_A"), events)
        self.assertIn(("recovery", ("batch_A",)), events)


if __name__ == "__main__":
    unittest.main()
