import io
import threading
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class _LogBox:
    def __init__(self, view):
        self.view = view
        self.see_calls = []
        self.moveto_calls = []
        self.text = ""

    def yview(self):
        return self.view

    def yview_moveto(self, value):
        self.moveto_calls.append(value)

    def configure(self, **_kwargs):
        pass

    def insert(self, _where, text, *_tags):
        self.text += text

    def see(self, where):
        self.see_calls.append(where)


class LogScrollLockTest(unittest.TestCase):
    def test_bottom_detection_is_strict(self):
        self.assertTrue(gui._log_view_at_bottom((0.7, 1.0)))
        self.assertFalse(gui._log_view_at_bottom((0.2, 0.8)))

    def test_new_log_preserves_manual_scroll_position(self):
        box = _LogBox((0.2, 0.6))
        stub = SimpleNamespace(
            _is_shutting_down=False,
            _log_lock=threading.Lock(),
            _log_file=io.StringIO(),
            _log_pinned=True,
            log_box=box,
        )
        gui.App._log(stub, "new line", "info")
        self.assertFalse(stub._log_pinned)
        self.assertEqual(box.see_calls, [])
        self.assertEqual(box.moveto_calls, [0.2])

    def test_new_log_follows_when_view_is_at_bottom(self):
        box = _LogBox((0.7, 1.0))
        stub = SimpleNamespace(
            _is_shutting_down=False,
            _log_lock=threading.Lock(),
            _log_file=io.StringIO(),
            _log_pinned=True,
            log_box=box,
        )
        gui.App._log(stub, "new line", "info")
        self.assertTrue(stub._log_pinned)
        self.assertEqual(box.see_calls, ["end"])
        self.assertEqual(box.moveto_calls, [])


if __name__ == "__main__":
    unittest.main()
