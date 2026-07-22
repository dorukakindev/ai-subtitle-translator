import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui


class MultiFolderAddTest(unittest.TestCase):
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
                logs=[], refreshes=[])
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
