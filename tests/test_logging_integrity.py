import io
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
