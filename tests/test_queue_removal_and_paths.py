import os
import queue
import tempfile
import threading
import unittest
from pathlib import Path
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

    def set(self, value):
        self.options["value"] = value

    def destroy(self):
        self.destroyed = True


def _queue_app(files, state="waiting"):
    rows = {}
    for path in files:
        rows[path] = {
            "dot": _Widget("○"), "phase": _Widget(), "pb": _Widget(),
            "frame": _Widget(), "remove": _Widget(), "state": state,
        }
    app = SimpleNamespace(
        _job_rows=rows,
        _removed_queue_files=set(),
        _selected_files=list(files),
        _file_schema_vars={p: object() for p in files},
        _PHASE_COLORS={},
        stat_files_var=object(),
        logs=[], stats=[],
        _ui_queue=queue.Queue(),
        _is_shutting_down=False,
    )
    app._norm_path = lambda path: gui.App._norm_path(app, path)
    app._log = lambda *args: app.logs.append(args)
    app._set_stat = lambda _var, value: app.stats.append(value)
    app._refresh_job_board_title = lambda: None
    return app


class ProductionPathHelperTest(unittest.TestCase):
    def test_dedupe_uses_real_helper_and_preserves_order(self):
        app = SimpleNamespace()
        first = os.path.abspath("first.srt")
        duplicate = os.path.join(os.path.dirname(first), ".", os.path.basename(first))
        second = os.path.abspath("second.srt")
        self.assertEqual(gui.App._dedupe_paths(app, [first, duplicate, second]), [first, second])

    def test_normalized_removed_lookup_is_case_insensitive_on_windows(self):
        app = _queue_app([r"C:\Subs\EP1.srt"])
        gui.App._remove_queued_file(app, r"C:\Subs\EP1.srt")
        self.assertTrue(gui.App._is_queued_file_removed(app, r"c:\subs\ep1.srt"))

    def test_running_row_cannot_be_removed(self):
        path = r"C:\Subs\EP1.srt"
        app = _queue_app([path], state="running")
        gui.App._remove_queued_file(app, path)
        self.assertIn(path, app._job_rows)
        self.assertFalse(app._job_rows[path]["frame"].destroyed)

    def test_worker_claims_row_before_main_thread_callback(self):
        path = r"C:\Subs\EP1.srt"
        app = _queue_app([path])

        worker = threading.Thread(
            target=gui.App._update_file_progress,
            args=(app, path, "Hazırlanıyor", 2),
        )
        worker.start()
        worker.join()

        self.assertEqual(app._job_rows[path]["state"], "running")
        self.assertEqual(app._ui_queue.qsize(), 1)
        gui.App._remove_queued_file(app, path)
        self.assertIn(path, app._job_rows)


class ProductionFolderAppendTest(unittest.TestCase):
    def _app(self, input_dir="", input_selected=False):
        app = SimpleNamespace(
            _selected_files=[], _content_type_preflight_done=True,
            _input_folder_explicitly_selected=input_selected,
            _is_running=False, input_var=SimpleNamespace(get=lambda: input_dir),
            logs=[], refreshes=[],
        )
        app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
        app._get_srt_files = lambda: gui.App._get_srt_files(app)
        app._log = lambda *args: app.logs.append(args)
        app._refresh_selected_files_ui = lambda text: app.refreshes.append(text)
        return app

    def test_multiple_folders_append_supported_files_recursively(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root, "first")
            second = Path(root, "second", "nested")
            first.mkdir()
            second.mkdir(parents=True)
            (first / "one.srt").write_text("", encoding="utf-8")
            (second / "two.vtt").write_text("", encoding="utf-8")
            (second / "ignore.txt").write_text("", encoding="utf-8")
            app = self._app()

            added = gui.App._append_folder_files(app, [str(first), str(second.parent)])

            self.assertEqual(added, 2)
            self.assertEqual({Path(p).name for p in app._selected_files}, {"one.srt", "two.vtt"})

    def test_existing_input_folder_is_preserved_when_another_is_added(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root, "base")
            extra = Path(root, "extra")
            base.mkdir()
            extra.mkdir()
            (base / "one.srt").write_text("", encoding="utf-8")
            (extra / "two.ass").write_text("", encoding="utf-8")
            app = self._app(str(base), input_selected=True)

            gui.App._append_folder_files(app, [str(extra)])

            self.assertEqual({Path(p).name for p in app._selected_files}, {"one.srt", "two.ass"})

    def test_saved_input_folder_is_not_implicitly_added_to_explicit_folders(self):
        with tempfile.TemporaryDirectory() as root:
            saved = Path(root, "saved-home")
            chosen = Path(root, "chosen")
            saved.mkdir()
            chosen.mkdir()
            for index in range(20):
                (saved / f"old-{index}.srt").write_text("", encoding="utf-8")
            (chosen / "wanted.srt").write_text("", encoding="utf-8")
            app = self._app(str(saved), input_selected=False)

            added = gui.App._append_folder_files(app, [str(chosen)])

            self.assertEqual(added, 1)
            self.assertEqual([Path(p).name for p in app._selected_files], ["wanted.srt"])

    def test_append_is_blocked_while_running(self):
        app = self._app()
        app._is_running = True
        self.assertEqual(gui.App._append_folder_files(app, ["unused"]), 0)

    def test_input_and_output_folder_dialogs_are_blocked_before_opening(self):
        app = SimpleNamespace(_is_running=True, logs=[])
        app._log = lambda *args: app.logs.append(args)
        app.attributes = lambda *_args: self.fail("dialog setup must not run")
        var = SimpleNamespace(set=lambda _value: None)
        gui.App._pick_folder(app, var, True)
        gui.App._pick_folder(app, var, False)
        self.assertEqual(len(app.logs), 2)


class ProductionOutputPathTest(unittest.TestCase):
    def test_external_same_named_folders_do_not_collide(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            input_dir = root / "input"
            output_dir = root / "output"
            a = root / "tree-a" / "Season" / "episode.srt"
            b = root / "tree-b" / "Season" / "episode.srt"
            input_dir.mkdir()
            a.parent.mkdir(parents=True)
            b.parent.mkdir(parents=True)

            out_a = gui._resolve_output_path(str(input_dir), str(output_dir), str(a))
            out_b = gui._resolve_output_path(str(input_dir), str(output_dir), str(b))

            self.assertNotEqual(os.path.normcase(str(out_a)), os.path.normcase(str(out_b)))
            self.assertEqual(out_a.name, "episode.srt")
            self.assertEqual(out_b.name, "episode.srt")

    def test_external_output_bucket_is_stable(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            src = root / "external" / "episode.vtt"
            src.parent.mkdir()
            args = (str(root / "input"), str(root / "output"), str(src))
            self.assertEqual(gui._resolve_output_path(*args), gui._resolve_output_path(*args))

    def test_standard_rule_two_path_is_unchanged(self):
        out = gui._resolve_output_path("/input", "/output", "/input/Film.vtt")
        self.assertEqual(out, Path("/output/Film/Film.srt"))


if __name__ == "__main__":
    unittest.main()
