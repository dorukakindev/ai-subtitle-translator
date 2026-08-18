import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui
from request_cancellation import RunRequestCanceller


class _Canceller:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Button:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


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

    def test_pass_skip_cancels_only_active_pass(self):
        canceller = _Canceller()
        button = _Button()
        logs = []
        filepath = r"C:\subs\episode01.srt"
        stub = SimpleNamespace(
            _is_running=True,
            _stop_flag=False,
            _current_file_path=filepath,
            _current_skippable_pass="Critic Pass",
            _skip_current_pass_request=None,
            _skip_current_file_path="",
            _helper_request_canceller=canceller,
            skip_pass_btn=button,
            _log=lambda message, level: logs.append((message, level)),
            _set_status=lambda _message: None,
        )
        gui.App._skip_current_pass(stub)
        self.assertTrue(canceller.cancelled)
        self.assertEqual(stub._skip_current_file_path, "")
        self.assertEqual(button.state, "disabled")
        self.assertIn("nihai yazıma devam", logs[-1][0])

    def test_completing_pass_skip_rearms_request_and_keeps_file_active(self):
        filepath = r"C:\subs\episode01.srt"
        normalized = gui.os.path.normcase(gui.os.path.abspath(filepath))
        logs = []
        status = {
            "status": "cancelled", "successful_chunks": 4,
            "total_chunks": 10, "changed": 3,
        }
        stub = SimpleNamespace(
            _is_running=True,
            _stop_flag=False,
            _current_file_path=filepath,
            _current_skippable_pass="Critic Pass",
            _skip_current_pass_request=(normalized, "Critic Pass"),
            _skip_current_file_path="",
            _helper_request_canceller=_Canceller(),
            skip_pass_btn=_Button(),
            _log=lambda message, level: logs.append((message, level)),
        )
        self.assertTrue(gui.App._complete_pass_skip(
            stub, filepath, "Critic Pass", status))
        self.assertEqual(stub._current_file_path, filepath)
        self.assertEqual(status["status"], "user_skipped")
        self.assertEqual(status["coverage_pct"], 40.0)
        self.assertEqual(status["changed"], 0)
        self.assertIsInstance(stub._helper_request_canceller, RunRequestCanceller)
        self.assertIn("4/10", logs[-1][0])

    def test_file_skip_takes_priority_over_pass_skip(self):
        filepath = r"C:\subs\episode01.srt"
        normalized = gui.os.path.normcase(gui.os.path.abspath(filepath))
        status = {"status": "cancelled", "successful_chunks": 1,
                  "total_chunks": 2}
        stub = SimpleNamespace(
            _current_file_path=filepath,
            _current_skippable_pass="Critic Pass",
            _skip_current_pass_request=(normalized, "Critic Pass"),
            _skip_current_file_path=filepath,
            skip_pass_btn=_Button(),
        )
        self.assertFalse(gui.App._complete_pass_skip(
            stub, filepath, "Critic Pass", status))
        self.assertEqual(status["status"], "cancelled")

    def test_skipped_critic_report_records_partial_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "episode01.srt"
            target.write_text("", encoding="utf-8")
            stub = SimpleNamespace(
                _log=lambda *_args: None,
                _log_exc=lambda *_args: None,
            )
            gui.App._write_critic_change_report(
                stub, target, [], [], report_only=True,
                status={
                    "status": "user_skipped", "successful_chunks": 3,
                    "total_chunks": 8, "coverage_pct": 37.5,
                })
            report = (Path(td) / "Raporlar" /
                      "episode01.critic_degisiklikler.txt")
            text = report.read_text(encoding="utf-8")
            self.assertIn("KULLANICI TARAFINDAN ATLANDI", text)
            self.assertIn("3/8 (%37.5)", text)
            self.assertIn("nihai yazım devam etti", text)

    def test_sync_writers_consume_skip_before_final_write(self):
        for method in (gui.App._run_sync_hybrid, gui.App._write_results):
            source = inspect.getsource(method)
            self.assertIn("_complete_file_skip", source)
            self.assertLess(
                source.rfind("_complete_file_skip"),
                source.find("write_srt", source.rfind("_complete_file_skip")))

    def test_every_critic_flow_supports_pass_only_skip(self):
        source = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("ht.critic_pass_with_helper("), 5)
        self.assertEqual(source.count(
            'App._begin_skippable_pass(self, fp, "Critic Pass")'), 2)
        self.assertGreaterEqual(source.count("App._complete_pass_skip("), 5)


if __name__ == "__main__":
    unittest.main()
