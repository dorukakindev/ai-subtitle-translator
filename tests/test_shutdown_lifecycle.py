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

    def test_finish_close_locks_log_and_closes_tm(self):
        log_file = io.StringIO()
        tm = MagicMock()
        destroyed = MagicMock()
        stub = SimpleNamespace(
            _tm=tm,
            _log_lock=threading.Lock(),
            _log_file=log_file,
            destroy=destroyed,
        )

        gui.App._finish_close(stub)

        tm.close.assert_called_once()
        self.assertTrue(log_file.closed)
        self.assertIsNone(stub._log_file)
        destroyed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
