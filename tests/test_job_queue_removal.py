import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class _Widget:
    def __init__(self, text=""):
        self.text = text
        self.destroyed = False
        self.options = {}

    def cget(self, key):
        return self.text if key == "text" else self.options.get(key)

    def configure(self, **kwargs):
        self.options.update(kwargs)
        if "text" in kwargs:
            self.text = kwargs["text"]

    def destroy(self):
        self.destroyed = True


class JobQueueRemovalTest(unittest.TestCase):
    def _app(self, state="waiting"):
        dot, frame = _Widget("○"), _Widget()
        title = _Widget()
        path = r"C:\work\waiting.srt"
        import os
        app = SimpleNamespace(
            _job_rows={path: {"dot": dot, "frame": frame, "state": state}},
            _removed_queue_files=set(), _selected_files=[path],
            _file_schema_vars={path: object()}, _jb_title=title,
            _log=lambda *args: None,
            stat_files_var="stat_files_var",
        )
        app._norm_path = lambda fp: os.path.normcase(os.path.abspath(str(fp)))
        app._set_stat = lambda var, val: None
        app._refresh_job_board_title = lambda: gui.App._refresh_job_board_title(app)
        return app, path, frame

    def test_waiting_file_is_removed_from_queue_and_selection(self):
        app, path, frame = self._app()
        gui.App._remove_queued_file(app, path)
        import os
        norm = os.path.normcase(os.path.abspath(path))
        self.assertIn(norm, app._removed_queue_files)
        self.assertNotIn(path, app._job_rows)
        self.assertNotIn(path, app._selected_files)
        self.assertTrue(frame.destroyed)
        self.assertTrue(gui.App._is_queued_file_removed(app, path))

    def test_running_file_cannot_be_removed(self):
        app, path, frame = self._app(state="running")
        gui.App._remove_queued_file(app, path)
        self.assertNotIn(path, app._removed_queue_files)
        self.assertIn(path, app._job_rows)
        self.assertFalse(frame.destroyed)


if __name__ == "__main__":
    unittest.main()
