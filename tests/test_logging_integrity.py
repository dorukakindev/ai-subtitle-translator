import io
import threading
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class _LogBox:
    def __init__(self):
        self.text = ""

    def configure(self, **_kwargs):
        pass

    def insert(self, _where, text):
        self.text += text

    def see(self, _where):
        pass


class LoggingIntegrityTest(unittest.TestCase):
    def test_disk_log_failure_is_reported_once_in_ui(self):
        class _FailingLog:
            def write(self, _text):
                raise OSError("disk full")

            def flush(self):
                raise AssertionError("write should fail first")

        log_box = _LogBox()
        recorder = MagicMock()
        stub = SimpleNamespace(
            _log_lock=threading.Lock(),
            _log_file=_FailingLog(),
            log_box=log_box,
            _log_pinned=False,
            _record_log_metadata=recorder,
        )

        with patch.object(gui, "_post_ui", side_effect=lambda _app, fn: fn()):
            gui.App._log(stub, "ilk", "info")
            gui.App._log(stub, "ikinci", "info")

        self.assertEqual(
            log_box.text.count("Oturum logu dosyasına yazılamıyor"), 1)
        self.assertIn("ilk", log_box.text)
        self.assertIn("ikinci", log_box.text)
        warning_calls = [
            call for call in recorder.call_args_list
            if "Oturum logu dosyasına yazılamıyor" in str(call.args[0])]
        self.assertEqual(len(warning_calls), 1)

    def test_disk_keeps_full_redacted_message_while_ui_is_truncated(self):
        log_file = io.StringIO()
        log_box = _LogBox()
        stub = SimpleNamespace(
            _log_lock=threading.Lock(),
            _log_file=log_file,
            log_box=log_box,
            _log_pinned=False,
        )
        secret = "sk-" + "sensitive-token-123"
        tail = "TAIL-MUST-REMAIN"
        message = f"request failed key={secret} " + ("x" * 700) + tail

        with patch.object(gui, "_post_ui", side_effect=lambda _app, fn: fn()):
            gui.App._log(stub, message, "err")

        disk_text = log_file.getvalue()
        self.assertIn(tail, disk_text)
        self.assertIn("[REDACTED]", disk_text)
        self.assertNotIn(secret, disk_text)
        self.assertNotIn(secret, log_box.text)
        self.assertIn("…", log_box.text)
        self.assertNotIn(tail, log_box.text)

    def test_copy_log_uses_complete_disk_log_not_truncated_ui(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "session.log"
            full_text = "[12:00:00] ›  " + ("x" * 900) + "TAIL\n"
            log_file = path.open("w", encoding="utf-8")
            log_file.write(full_text)
            clipboard_append = MagicMock()
            stub = SimpleNamespace(
                _log_file=log_file,
                _log_lock=threading.Lock(),
                log_box=SimpleNamespace(get=lambda *_args: "TRUNCATED"),
                clipboard_clear=MagicMock(),
                clipboard_append=clipboard_append,
                update_idletasks=MagicMock(),
                _copy_log_btn=None,
                _log=MagicMock(),
            )
            stub._complete_session_log_text = (
                lambda: gui.App._complete_session_log_text(stub))
            try:
                result = gui.App._copy_complete_log_to_clipboard(stub)
            finally:
                log_file.close()

        self.assertTrue(result)
        clipboard_append.assert_called_once_with(full_text)
        self.assertIn("TAIL", clipboard_append.call_args.args[0])
        stub._log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
