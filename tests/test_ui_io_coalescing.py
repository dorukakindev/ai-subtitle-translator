import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui
from subtitle_formats import get_subtitle_files


class _Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class UiIoCoalescingTest(unittest.TestCase):
    def test_folder_scans_run_one_at_a_time_and_latest_request_wins(self):
        workers = []
        applied = []
        app = SimpleNamespace(
            _folder_scan_busy=False,
            _folder_scan_token=None,
            _folder_scan_cancel=None,
            _folder_scan_pending=None,
            _set_folder_scan_busy=lambda busy: setattr(
                app, "_folder_scan_busy", bool(busy)),
            _log=MagicMock(),
        )

        def work_one(cancel_check):
            self.assertTrue(cancel_check())
            return "old"

        def work_two(cancel_check):
            self.assertFalse(cancel_check())
            return "latest"

        with patch.object(gui.App, "_start_worker",
                          side_effect=lambda _app, fn: workers.append(fn)), \
             patch.object(gui, "_post_ui",
                          side_effect=lambda _app, callback, *args:
                          callback(*args)):
            gui.App._run_folder_scan(
                app, work_one, lambda value: applied.append(value))
            gui.App._run_folder_scan(
                app, work_two, lambda value: applied.append(value))

            self.assertEqual(len(workers), 1)
            workers.pop(0)()
            self.assertEqual(applied, [])
            self.assertEqual(len(workers), 1)
            workers.pop(0)()

        self.assertEqual(applied, ["latest"])
        self.assertFalse(app._folder_scan_busy)

    def test_estimates_run_one_at_a_time_and_skip_intermediate_lists(self):
        workers = []
        calls = []
        app = SimpleNamespace(
            _estimate_busy=False,
            _estimate_token=None,
            _estimate_cancel=None,
            _estimate_pending=None,
            _chunk_size=25,
            stat_files_var=object(),
            stat_blocks_var=object(),
            file_info_var=_Var(),
            _set_stat=MagicMock(),
        )

        def fake_estimate(files, chunk_size=None, cancel_check=None):
            calls.append(list(files))
            self.assertFalse(cancel_check())
            return 1000, len(files)

        with patch.object(gui.App, "_start_worker",
                          side_effect=lambda _app, fn: workers.append(fn)), \
             patch.object(gui, "_post_ui",
                          side_effect=lambda _app, callback, *args:
                          callback(*args)), \
             patch.object(gui, "estimate_tokens", side_effect=fake_estimate):
            gui.App._estimate_async(app, ["old.srt"], lambda *_: "old")
            gui.App._estimate_async(app, ["middle.srt"], lambda *_: "middle")
            gui.App._estimate_async(
                app, ["latest-1.srt", "latest-2.srt"],
                lambda blocks, tokens: f"latest:{blocks}:{tokens}")

            self.assertEqual(len(workers), 1)
            workers.pop(0)()
            self.assertEqual(calls, [])
            self.assertEqual(len(workers), 1)
            workers.pop(0)()

        self.assertEqual(calls, [["latest-1.srt", "latest-2.srt"]])
        self.assertEqual(app.file_info_var.get(), "latest:2:1k")
        self.assertFalse(app._estimate_busy)

    def test_project_memory_is_loaded_inside_scan_worker(self):
        workers = []
        posted = []
        memory = MagicMock()
        memory.stats.return_value = {"glossary": 0, "characters": 0}
        app = SimpleNamespace(
            _folder_scan_busy=False,
            _folder_scan_token=None,
            _folder_scan_cancel=None,
            _folder_scan_pending=None,
            _pm=None,
            _project_memories={"old": object()},
            input_var=_Var("C:/subs"),
            tgt_var=_Var("Turkish"),
            src_var=_Var("English"),
            file_info_var=_Var(),
            _set_folder_scan_busy=lambda busy: setattr(
                app, "_folder_scan_busy", bool(busy)),
            _run_folder_scan=lambda work, finish:
                gui.App._run_folder_scan(app, work, finish),
            _estimate_async=MagicMock(),
            _populate_file_list=MagicMock(),
            _log=MagicMock(),
        )
        app._queue_input_folder_scan = (
            lambda path: gui.App._queue_input_folder_scan(app, path))

        with patch.object(gui.App, "_start_worker",
                          side_effect=lambda _app, fn: workers.append(fn)), \
             patch.object(gui, "_post_ui",
                          side_effect=lambda _app, callback, *args:
                          posted.append((callback, args))), \
             patch.object(gui, "get_subtitle_files",
                          return_value=["C:/subs/one.srt"]), \
             patch("project_memory.ProjectMemory",
                   return_value=memory) as project_memory:
            gui.App._queue_input_folder_scan(app, "C:/subs")
            project_memory.assert_not_called()

            workers.pop(0)()
            project_memory.assert_called_once()
            self.assertIsNone(app._pm)

            callback, args = posted.pop(0)
            callback(*args)

        self.assertIs(app._pm, memory)
        self.assertEqual(app._project_memories, {})
        app._populate_file_list.assert_called_once_with(["C:/subs/one.srt"])

    def test_stale_language_memory_is_not_applied(self):
        workers = []
        posted = []
        memory = MagicMock()
        memory.stats.return_value = {"glossary": 0, "characters": 0}
        source = _Var("English")
        app = SimpleNamespace(
            _folder_scan_busy=False,
            _folder_scan_token=None,
            _folder_scan_cancel=None,
            _folder_scan_pending=None,
            _pm=None,
            _project_memories={},
            input_var=_Var("C:/subs"),
            tgt_var=_Var("Turkish"),
            src_var=source,
            file_info_var=_Var(),
            _set_folder_scan_busy=lambda busy: setattr(
                app, "_folder_scan_busy", bool(busy)),
            _run_folder_scan=lambda work, finish:
                gui.App._run_folder_scan(app, work, finish),
            _estimate_async=MagicMock(),
            _populate_file_list=MagicMock(),
            _log=MagicMock(),
        )
        app._queue_input_folder_scan = (
            lambda path: gui.App._queue_input_folder_scan(app, path))

        with patch.object(gui.App, "_start_worker",
                          side_effect=lambda _app, fn: workers.append(fn)), \
             patch.object(gui, "_post_ui",
                          side_effect=lambda _app, callback, *args:
                          posted.append((callback, args))), \
             patch.object(gui, "get_subtitle_files", return_value=[]), \
             patch("project_memory.ProjectMemory", return_value=memory):
            gui.App._queue_input_folder_scan(app, "C:/subs")
            workers.pop(0)()
            source.set("Spanish")
            callback, args = posted.pop(0)
            callback(*args)

        self.assertIsNone(app._pm)
        self.assertEqual(len(workers), 1)
        app._populate_file_list.assert_not_called()

    def test_cancelled_folder_walk_returns_no_partial_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one.srt").write_text("1", encoding="utf-8")
            self.assertEqual(
                get_subtitle_files(tmp, cancel_check=lambda: True), [])

    def test_cancelled_estimate_does_not_parse_files(self):
        with patch.object(gui, "parse_subtitle") as parse:
            self.assertEqual(
                gui.estimate_tokens(
                    ["one.srt"], cancel_check=lambda: True),
                (None, None),
            )
        parse.assert_not_called()

    def test_start_is_rejected_while_folder_scan_is_active(self):
        app = SimpleNamespace(
            _folder_scan_busy=True,
            _set_status=MagicMock(),
            _log=MagicMock(),
        )

        gui.App._start(app)

        app._set_status.assert_called_once()
        app._log.assert_called_once()


if __name__ == "__main__":
    unittest.main()
