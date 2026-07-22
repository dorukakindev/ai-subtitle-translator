import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui


class _Tk:
    @staticmethod
    def splitlist(value):
        return value.split("|")


class DragDropFolderTest(unittest.TestCase):
    def _app(self):
        app = SimpleNamespace(
            tk=_Tk(), _selected_files=[], _content_type_preflight_done=True,
            logs=[], refreshes=[])
        app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
        app._log = lambda *args: app.logs.append(args)
        app._refresh_selected_files_ui = lambda text: app.refreshes.append(text)
        return app

    def test_second_dropped_folder_appends_without_removing_first(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root, "first")
            second = Path(root, "second")
            first.mkdir()
            second.mkdir()
            (first / "one.srt").write_text("", encoding="utf-8")
            (second / "two.srt").write_text("", encoding="utf-8")
            app = self._app()

            gui.App._on_drop(app, SimpleNamespace(data=f"{first}|{second}"))
            self.assertEqual({Path(p).name for p in app._selected_files}, {"one.srt", "two.srt"})

            gui.App._on_drop(app, SimpleNamespace(data=str(second)))
            self.assertEqual({Path(p).name for p in app._selected_files}, {"one.srt", "two.srt"})
            self.assertIn("+0 yeni, toplam 2", app.refreshes[-1])
            self.assertFalse(app._content_type_preflight_done)


if __name__ == "__main__":
    unittest.main()
