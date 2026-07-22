import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui


class MultiFolderAddTest(unittest.TestCase):
    def test_add_folder_uses_single_native_multi_select_dialog(self):
        selected = [r"C:\one", r"D:\two"]
        app = SimpleNamespace(_is_running=False, received=None)
        app._log = lambda *args: None
        app.winfo_id = lambda: 123
        app._append_folder_files = lambda paths: setattr(app, "received", paths)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=selected) as picker:
            gui.App._add_folder_files(app)

        picker.assert_called_once_with(
            owner_hwnd=123, title="Altyazı Klasörlerini Seç")
        self.assertEqual(app.received, selected)

    def test_add_folder_cancel_does_not_append(self):
        app = SimpleNamespace(_is_running=False, appended=False)
        app._log = lambda *args: None
        app.winfo_id = lambda: 123
        app._append_folder_files = lambda _paths: setattr(app, "appended", True)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=[]):
            gui.App._add_folder_files(app)

        self.assertFalse(app.appended)

    def test_multiple_folders_append_to_existing_queue(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root, "first")
            second = Path(root, "second")
            first.mkdir()
            second.mkdir()
            (first / "one.srt").write_text("", encoding="utf-8")
            (second / "two.vtt").write_text("", encoding="utf-8")
            app = SimpleNamespace(
                _selected_files=[], _content_type_preflight_done=True,
                _is_running=False,
                logs=[], refreshes=[])
            app.input_var = SimpleNamespace(get=lambda: "")
            app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
            app._log = lambda *args: app.logs.append(args)
            app._refresh_selected_files_ui = lambda text: app.refreshes.append(text)

            added = gui.App._append_folder_files(app, [str(first), str(second)])

            self.assertEqual(added, 2)
            self.assertEqual({Path(p).name for p in app._selected_files}, {"one.srt", "two.vtt"})
            self.assertIn("2 klasör eklendi: +2 yeni, toplam 2", app.refreshes[-1])
            self.assertFalse(app._content_type_preflight_done)


if __name__ == "__main__":
    unittest.main()
