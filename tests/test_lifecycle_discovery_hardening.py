import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui


class NestedOutputDiscoveryTest(unittest.TestCase):
    def test_nested_custom_output_is_excluded_but_selected_root_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "CUSTOM OUTPUT"
            output.mkdir()
            exclusions = gui._nested_output_exclusions(
                [str(root)], str(output), False)
            self.assertEqual(exclusions, [str(output.resolve())])
            self.assertEqual(
                gui._nested_output_exclusions([str(output)], str(output), False),
                [],
            )

    def test_folder_append_does_not_reingest_custom_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "translated"
            output.mkdir()
            source = root / "source.srt"
            generated = output / "already-translated.srt"
            source.write_text("", encoding="utf-8")
            generated.write_text("", encoding="utf-8")
            app = SimpleNamespace(
                _is_running=False,
                _selected_files=[],
                _selected_folder_roots=[],
                _content_type_preflight_done=True,
                _language_preflight_done=True,
                _input_folder_explicitly_selected=False,
                input_var=SimpleNamespace(get=lambda: ""),
                output_var=SimpleNamespace(get=lambda: str(output)),
                same_folder_var=SimpleNamespace(get=lambda: False),
                logs=[],
            )
            app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
            app._log = lambda *args: app.logs.append(args)
            app._refresh_selected_files_ui = lambda _text: None

            added = gui.App._append_folder_files(app, [str(root)])

            self.assertEqual(added, 1)
            self.assertEqual(app._selected_files, [str(source)])


class StaleFolderScanTest(unittest.TestCase):
    def test_finished_input_scan_cannot_replace_new_explicit_file_selection(self):
        path = r"C:\input"
        captured = {}
        app = SimpleNamespace(
            _selected_files=[],
            _input_folder_explicitly_selected=True,
            input_var=SimpleNamespace(get=lambda: path),
            output_var=SimpleNamespace(get=lambda: ""),
            same_folder_var=SimpleNamespace(get=lambda: False),
            tgt_var=SimpleNamespace(get=lambda: "Turkish"),
            src_var=SimpleNamespace(get=lambda: "English"),
            populated=[],
        )
        app._run_folder_scan = lambda work, finish: captured.update(
            work=work, finish=finish)
        app._populate_file_list = lambda files: app.populated.append(list(files))
        app._estimate_async = lambda *_args: None
        app._log = lambda *_args: None

        gui.App._queue_input_folder_scan(app, path)
        app._selected_files = [r"D:\manual.srt"]
        app._input_folder_explicitly_selected = False
        captured["finish"](([r"C:\input\old.srt"], object(), None))

        self.assertEqual(app.populated, [])
        self.assertFalse(hasattr(app, "_pm"))


if __name__ == "__main__":
    unittest.main()
