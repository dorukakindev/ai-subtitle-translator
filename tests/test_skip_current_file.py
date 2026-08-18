import inspect
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui
from request_cancellation import RunRequestCanceller


class _Canceller:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class SkipCurrentFileTest(unittest.TestCase):
    def test_skip_cancels_active_request_without_stopping_run(self):
        canceller = _Canceller()
        logs = []
        stub = SimpleNamespace(
            _is_running=True,
            _stop_flag=False,
            _current_file_path=r"C:\subs\episode01.srt",
            _skip_current_file_path="",
            _helper_request_canceller=canceller,
            _log=lambda message, level: logs.append((message, level)),
            _set_status=lambda _message: None,
        )
        gui.App._skip_current_file(stub)
        self.assertTrue(canceller.cancelled)
        self.assertFalse(stub._stop_flag)
        self.assertEqual(
            stub._skip_current_file_path, r"C:\subs\episode01.srt")
        self.assertIn("nihai yazım yapılmayacak", logs[-1][0])

    def test_completing_skip_creates_fresh_request_scope(self):
        recorded = []
        progress = []
        filepath = r"C:\subs\episode01.srt"
        stub = SimpleNamespace(
            _is_running=True,
            _stop_flag=False,
            _current_file_path=filepath,
            _skip_current_file_path=filepath,
            _helper_request_canceller=_Canceller(),
            _record_file_status=lambda *args: recorded.append(args),
            _update_file_progress=lambda *args: progress.append(args),
        )
        self.assertTrue(gui.App._complete_file_skip(stub, filepath))
        self.assertEqual(recorded[-1], (filepath, "Kullanıcı atladı", "skip"))
        self.assertEqual(progress[-1][-1], "skip")
        self.assertIsInstance(stub._helper_request_canceller, RunRequestCanceller)
        self.assertEqual(stub._current_file_path, "")

    def test_different_file_does_not_consume_skip(self):
        stub = SimpleNamespace(
            _skip_current_file_path=r"C:\subs\episode01.srt")
        self.assertFalse(gui.App._file_skip_requested(
            stub, r"C:\subs\episode02.srt"))

    def test_sync_writers_consume_skip_before_final_write(self):
        for method in (gui.App._run_sync_hybrid, gui.App._write_results):
            source = inspect.getsource(method)
            self.assertIn("_complete_file_skip", source)
            self.assertLess(
                source.rfind("_complete_file_skip"),
                source.find("write_srt", source.rfind("_complete_file_skip")))


if __name__ == "__main__":
    unittest.main()
