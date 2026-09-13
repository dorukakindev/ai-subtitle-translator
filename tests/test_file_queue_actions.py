"""Kuyruk düğmeleri görünen dosyaları korumalı; diskten dosya silmez."""
import contextlib
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=''):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FileQueueActionsTest(unittest.TestCase):
    def app(self, files, folder_mode=False):
        app = SimpleNamespace(
            _selected_files=[] if folder_mode else list(files),
            _file_list_files=list(files), _selected_folder_roots=['folder'],
            _is_running=False, _folder_scan_busy=False,
            _file_schema_vars={path: 'schema' for path in files},
            _file_language_vars={path: 'language' for path in files},
            _file_analysis_depth_vars={path: 'depth' for path in files},
            input_var=_Var('folder'),
            _log=Mock(), _refresh_selected_files_ui=Mock(),
            _clear_selected_files=Mock(),
        )
        app._get_srt_files = lambda: list(app._selected_files or app._file_list_files)
        app._dedupe_paths = lambda paths: gui.App._dedupe_paths(app, paths)
        return app

    def pick(self, app, paths, append):
        with patch.object(gui.App, '_dialog_topmost', return_value=contextlib.nullcontext()), \
                patch.object(gui.filedialog, 'askopenfilenames', return_value=paths):
            gui.App._pick_files(app, append=append)

    def test_add_preserves_existing_queue_and_per_file_settings(self):
        app = self.app(['one.srt'])
        self.pick(app, ['one.srt', 'two.vtt'], append=True)
        self.assertEqual(app._selected_files, ['one.srt', 'two.vtt'])
        self.assertEqual(app._file_schema_vars['one.srt'], 'schema')
        self.assertEqual(app._selected_folder_roots, ['folder'])

    def test_add_preserves_folder_queue(self):
        app = self.app(['one.srt'], folder_mode=True)
        self.pick(app, ['two.ass'], append=True)
        self.assertEqual(app._selected_files, ['one.srt', 'two.ass'])

    def test_replace_still_replaces_and_cancel_preserves_selection(self):
        app = self.app(['one.srt'])
        self.pick(app, [], append=False)
        self.assertEqual(app._selected_files, ['one.srt'])
        app._refresh_selected_files_ui.assert_not_called()
        self.pick(app, ['two.srt'], append=False)
        self.assertEqual(app._selected_files, ['two.srt'])
        self.assertEqual(app._selected_folder_roots, [])

    def test_remove_one_from_folder_keeps_other_files_and_settings(self):
        app = self.app(['one.srt', 'two.srt'], folder_mode=True)
        gui.App._remove_file_from_list(app, 'one.srt')
        self.assertEqual(app._selected_files, ['two.srt'])
        self.assertEqual(app._file_schema_vars, {'two.srt': 'schema'})
        self.assertEqual(app._file_language_vars, {'two.srt': 'language'})
        self.assertEqual(app._file_analysis_depth_vars, {'two.srt': 'depth'})
        app._clear_selected_files.assert_not_called()
        app._refresh_selected_files_ui.assert_called_once()

    def test_remove_last_file_does_not_restore_input_folder(self):
        app = self.app(['one.srt'], folder_mode=True)
        gui.App._remove_file_from_list(app, 'one.srt')
        self.assertEqual(app._selected_files, [])
        self.assertEqual(app.input_var.get(), '')
        app._clear_selected_files.assert_called_once()

    def test_busy_queue_cannot_be_replaced_removed_or_cleared(self):
        for flag in ('_is_running', '_folder_scan_busy'):
            with self.subTest(flag=flag):
                app = self.app(['one.srt'])
                setattr(app, flag, True)
                with patch.object(gui.filedialog, 'askopenfilenames') as picker:
                    gui.App._pick_files(app, append=True)
                    picker.assert_not_called()
                gui.App._remove_file_from_list(app, 'one.srt')
                gui.App._clear_selected_files(app)
                self.assertEqual(app._selected_files, ['one.srt'])
                app._refresh_selected_files_ui.assert_not_called()

    def test_path_aliases_only_add_one_file_preserving_first_spelling(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'source.srt'
            path.write_text('', encoding='utf-8')
            self.assertEqual(gui.App._dedupe_paths(None, [str(path), str(path.resolve())]),
                             [str(path)])

    def test_clear_cancels_pending_estimate_and_cannot_rescan_old_folder(self):
        app = self.app(['one.srt'])
        token = object()
        cancel = threading.Event()
        app._estimate_token = token
        app._estimate_cancel = cancel
        app._estimate_busy = True
        app._estimate_pending = ('pending',)
        app.file_info_var = _Var('hesaplanıyor')
        app.stat_files_var = _Var('1')
        app.stat_blocks_var = _Var('12')
        app._set_stat = lambda var, value: var.set(value)
        app._show_log_grip = Mock()
        app.clear_files_btn = Mock()
        app.clear_info_btn = Mock()
        with patch.object(gui.App, '_update_readiness_card'):
            gui.App._clear_selected_files(app)
        gui.App._finish_token_estimate(app, token, lambda *_: 'eski sonuç',
                                       1, (1000, 12), None)
        self.assertTrue(cancel.is_set())
        self.assertIsNone(app._estimate_pending)
        self.assertFalse(app._estimate_busy)
        self.assertEqual(app.file_info_var.get(), '')
        self.assertEqual(app.stat_files_var.get(), '0')
        self.assertEqual(app.stat_blocks_var.get(), '0')
        self.assertEqual(gui.App._get_srt_files(app), [])


if __name__ == '__main__':
    unittest.main()
