import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui


class MultiFolderAddTest(unittest.TestCase):
    def test_file_list_pagination_caps_live_rows(self):
        files = [f"file-{index}.srt" for index in range(2050)]

        first, page, pages = gui._file_list_page(files, 0)
        last, last_page, _ = gui._file_list_page(files, 999)

        self.assertEqual(len(first), gui.FILE_LIST_PAGE_SIZE)
        self.assertEqual(page, 0)
        self.assertEqual(pages, 35)
        self.assertEqual(last_page, 34)
        self.assertEqual(len(last), 10)

    def test_add_folder_prefers_background_scan_queue(self):
        selected = [r"C:\one", r"D:\two"]
        app = SimpleNamespace(_is_running=False, queued=None, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.winfo_id = lambda: 123
        app._queue_append_folder_files = (
            lambda paths: setattr(app, "queued", paths))
        app._append_folder_files = lambda _paths: self.fail(
            "UI callback must not scan folders synchronously")

        with mock.patch(
                "subtitle_translator_gui.pick_multiple_folders",
                return_value=selected):
            gui.App._add_folder_files(app)

        self.assertEqual(app.queued, selected)

    def test_add_folder_uses_single_native_multi_select_dialog(self):
        selected = [r"C:\one", r"D:\two"]
        app = SimpleNamespace(_is_running=False, received=None, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.winfo_id = lambda: 123
        app._append_folder_files = lambda paths: setattr(app, "received", paths)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=selected) as picker:
            gui.App._add_folder_files(app)

        picker.assert_called_once_with(
            owner_hwnd=123,
            title="Altyazı Klasörlerini Seç (Ctrl/Shift ile birden fazla klasör seçebilirsiniz)")
        self.assertEqual(app.received, selected)
        self.assertEqual(len(app.logs), 0)

    def test_add_folder_cancel_does_not_append_and_does_not_trigger_fallback(self):
        app = SimpleNamespace(_is_running=False, appended=False, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.winfo_id = lambda: 123
        app._append_folder_files = lambda _paths: setattr(app, "appended", True)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=[]), \
             mock.patch("subtitle_translator_gui.filedialog.askdirectory") as askdir:
            gui.App._add_folder_files(app)

        self.assertFalse(app.appended)
        askdir.assert_not_called()
        self.assertEqual(len(app.logs), 0)

    def test_fallback_when_native_picker_returns_none(self):
        app = SimpleNamespace(_is_running=False, received=None, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.winfo_id = lambda: 123
        app.attributes = lambda *args: None
        app._append_folder_files = lambda paths: setattr(app, "received", paths)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=None), \
             mock.patch("subtitle_translator_gui.filedialog.askdirectory", side_effect=[r"C:\dir1", r"C:\dir2"]), \
             mock.patch("subtitle_translator_gui.messagebox.askyesno", side_effect=[True, False]):
            gui.App._add_folder_files(app)

        self.assertEqual(app.received, [r"C:\dir1", r"C:\dir2"])
        self.assertTrue(any("Native çoklu klasör seçici kullanılamadı" in msg[0] for msg in app.logs))

    def test_fallback_cancelled_on_second_prompt(self):
        app = SimpleNamespace(_is_running=False, received=None, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.winfo_id = lambda: 123
        app.attributes = lambda *args: None
        app._append_folder_files = lambda paths: setattr(app, "received", paths)

        with mock.patch("subtitle_translator_gui.pick_multiple_folders", return_value=None), \
             mock.patch("subtitle_translator_gui.filedialog.askdirectory", side_effect=[r"C:\dir1", ""]), \
             mock.patch("subtitle_translator_gui.messagebox.askyesno", side_effect=[True]):
            gui.App._add_folder_files(app)

        self.assertEqual(app.received, [r"C:\dir1"])

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
