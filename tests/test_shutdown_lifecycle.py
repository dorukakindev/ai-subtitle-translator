import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import subtitle_translator_gui as gui
from translation_memory import TranslationMemory


class TranslationMemoryCloseTest(unittest.TestCase):
    def test_close_serializes_with_active_transaction_and_prevents_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            tm = TranslationMemory(Path(td) / "tm.db")
            tm._lock.acquire()
            closer = threading.Thread(target=tm.close)
            closer.start()
            time.sleep(0.03)
            self.assertTrue(closer.is_alive())
            tm._lock.release()
            closer.join(timeout=1)
            self.assertFalse(closer.is_alive())
            self.assertIsNone(tm._conn)
            with self.assertRaisesRegex(RuntimeError, "closed"):
                tm._get_conn()
            self.assertFalse(tm.store("source", "target"))


class WorkerDrainTest(unittest.TestCase):
    def _stub(self):
        stub = SimpleNamespace(
            _worker_lock=threading.Lock(),
            _worker_threads=set(),
        )
        stub._start_worker = lambda target, args=(), daemon=True: (
            gui.App._start_worker(stub, target, args, daemon)
        )
        stub._drain_workers_for_close = lambda deadline: (
            gui.App._drain_workers_for_close(stub, deadline)
        )
        return stub

    def test_tracked_worker_unregisters_after_completion(self):
        stub = self._stub()
        ran = threading.Event()
        thread = gui.App._start_worker(stub, ran.set)
        thread.join(timeout=1)
        self.assertTrue(ran.is_set())
        self.assertEqual(stub._worker_threads, set())

    def test_close_drain_uses_after_without_blocking_ui(self):
        stub = self._stub()
        release = threading.Event()
        thread = gui.App._start_worker(stub, release.wait)
        for _ in range(20):
            if thread.is_alive():
                break
            time.sleep(0.005)
        self.assertTrue(thread.is_alive())
        scheduled = []
        finished = MagicMock()
        stub.after = lambda delay, callback, deadline: scheduled.append(
            (delay, callback, deadline)
        )
        stub._finish_close = finished

        gui.App._drain_workers_for_close(stub, time.monotonic() + 1)

        self.assertEqual(len(scheduled), 1)
        self.assertEqual(scheduled[0][0], 50)
        finished.assert_not_called()
        release.set()
        thread.join(timeout=1)
        _, callback, deadline = scheduled.pop()
        callback(deadline)
        finished.assert_called_once()

    def test_close_drain_times_out_without_closing_live_worker_resources(self):
        stub = self._stub()
        release = threading.Event()
        thread = gui.App._start_worker(stub, release.wait)
        scheduled = []
        finished = MagicMock()
        stub.after = lambda *args: scheduled.append(args)
        stub._finish_close = finished
        stub._log = MagicMock()

        gui.App._drain_workers_for_close(stub, time.monotonic() - 1)

        self.assertEqual(scheduled, [])
        finished.assert_called_once_with(close_resources=False)
        release.set()
        thread.join(timeout=1)

    def test_close_drain_creates_bounded_deadline_when_not_provided(self):
        stub = self._stub()
        release = threading.Event()
        thread = gui.App._start_worker(stub, release.wait)
        scheduled = []
        stub.after = lambda delay, callback, deadline: scheduled.append(
            (delay, callback, deadline)
        )
        stub._finish_close = MagicMock()

        before = time.monotonic()
        gui.App._drain_workers_for_close(stub)

        self.assertEqual(len(scheduled), 1)
        self.assertGreaterEqual(scheduled[0][2], before + gui.CLOSE_WORKER_DRAIN_SECONDS - 0.1)
        release.set()
        thread.join(timeout=1)

    def test_finish_close_locks_log_and_closes_tm(self):
        log_file = io.StringIO()
        tm = MagicMock()
        destroyed = MagicMock()
        current_value = []
        var = SimpleNamespace(get=lambda: "güncel")
        original_get = var.get
        stub = SimpleNamespace(
            _tm=tm,
            _log_lock=threading.Lock(),
            _log_file=log_file,
            _active_snapshot={"value": "eski"},
            _frozen_run_var_getters=[(var, original_get)],
            _save_settings=lambda: current_value.append(var.get()),
            destroy=destroyed,
        )
        var.get = lambda: "eski"

        gui.App._finish_close(stub)

        self.assertEqual(current_value, ["güncel"])
        self.assertIsNone(stub._active_snapshot)
        tm.close.assert_called_once()
        self.assertTrue(log_file.closed)
        self.assertIsNone(stub._log_file)
        destroyed.assert_called_once()

    def test_forced_finish_keeps_snapshot_and_resources_for_live_worker(self):
        log_file = io.StringIO()
        tm = MagicMock()
        destroyed = MagicMock()
        var = SimpleNamespace(get=lambda: "canli")
        original_get = var.get
        stub = SimpleNamespace(
            _tm=tm,
            _log_lock=threading.Lock(),
            _log_file=log_file,
            _active_snapshot={"value": "anlik"},
            _frozen_run_var_getters=[(var, original_get)],
            destroy=destroyed,
        )
        var.get = lambda: "anlik"

        gui.App._finish_close(stub, close_resources=False)

        self.assertEqual(var.get(), "anlik")
        self.assertEqual(stub._active_snapshot, {"value": "anlik"})
        tm.close.assert_not_called()
        self.assertFalse(log_file.closed)
        destroyed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
