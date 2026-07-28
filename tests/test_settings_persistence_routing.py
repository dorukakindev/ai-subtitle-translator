import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Entry(_Var):
    def insert(self, _index, value):
        self.value = str(value)


class _Rows:
    def cget(self, _name):
        return 148


def _settings_app(path):
    app = SimpleNamespace(
        _settings_path=lambda: path,
        geometry=lambda: "900x700",
        api_key_entry=_Entry(), helper_key_entry=_Entry(),
        main_custom_key_entry=_Entry(), _file_rows_frame=_Rows(),
        helper_roles={}, helper_model_vars={}, helper_role_key_vars={},
        helper_custom_provider_vars={}, helper_custom_model_vars={},
        helper_custom_url_vars={}, helper_custom_key_vars={},
        _helper_keys_cache={}, _chunk_size=25, _context_lines=12,
        _lookahead_lines=8, _max_workers=4, _temperature=0.3,
        _max_retry=3, _scene_gap_seconds=2.0, _merge_max_chars=84,
        _merge_max_gap_ms=500, _log=lambda *_args: None,
    )
    values = {
        "model_var": "gpt-5.4-mini", "src_var": "English",
        "tgt_var": "Turkish", "mode_var": "sync", "hybrid_var": True,
        "style_var": "natural", "glossary_var": "", "analysis_depth_var": "Standart",
        "ext_project_path_var": "", "clean_sdh_var": True,
        "content_type_var": "Otomatik", "profanity_var": "Orta",
        "critic_var": True, "polish_var": True, "qc_var": True,
        "native_var": True, "backtrans_var": True,
        "semantic_reconcile_var": True, "backup_raw_var": True,
        "auto_glossary_var": True, "linebreak_var": True,
        "condense_var": True, "chain_ctx_var": True, "precontext_var": False,
        "series_memory_var": False, "review_pass_var": False,
        "term_normalize_var": False, "twowave_var": False,
        "same_folder_var": False, "merge_cues_var": True,
        "ai_segment_var": True, "notify_var": True, "api_url_var": "",
        "main_custom_var": False, "main_custom_model_var": "",
        "main_custom_url_var": "",
    }
    for name, value in values.items():
        setattr(app, name, _Var(value))
    return app


class SettingsPersistenceRoutingTest(unittest.TestCase):
    def test_json_only_save_never_touches_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".gui_settings.json"
            app = _settings_app(path)
            app.api_key_entry.set("secret")
            with mock.patch.object(gui.credential_store, "save_key") as save, \
                 mock.patch.object(gui.credential_store, "delete_key") as delete:
                gui.App._save_settings(app, save_credentials=False)
            self.assertFalse(save.called)
            self.assertFalse(delete.called)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["model"], "gpt-5.4-mini")

    def test_default_save_still_persists_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = _settings_app(Path(tmp) / ".gui_settings.json")
            app.api_key_entry.set("secret")
            with mock.patch.object(gui.credential_store, "save_key", return_value=True) as save, \
                 mock.patch.object(gui.credential_store, "delete_key"):
                gui.App._save_settings(app)
            save.assert_any_call("openai", "secret")

    def test_model_change_uses_json_only_save_once(self):
        app = SimpleNamespace(
            limit_class_var=_Var("250K"), model_var=_Var("old"),
            model_2_5m_var=_Var("gpt-5.4-mini"),
            model_250k_var=_Var("gpt-5.4"),
            model_2_5m_combo=None, model_250k_combo=None,
            _save_settings=mock.Mock(),
        )
        gui.App._update_active_model(app, "2.5M")
        self.assertEqual(app.limit_class_var.get(), "2.5M")
        self.assertEqual(app.model_var.get(), "gpt-5.4-mini")
        app._save_settings.assert_called_once_with(save_credentials=False)

    def test_model_comboboxes_have_one_callback_path(self):
        source = inspect.getsource(gui.App._build_sidebar)
        self.assertNotIn("self.model_2_5m_var.trace_add", source)
        self.assertNotIn("self.model_250k_var.trace_add", source)

    def test_custom_provider_toggle_does_not_rewrite_credentials(self):
        app = SimpleNamespace(
            _sync_main_custom_visibility=mock.Mock(),
            _save_settings=mock.Mock(),
        )

        gui.App._on_main_custom_changed(app)

        app._sync_main_custom_visibility.assert_called_once_with()
        app._save_settings.assert_called_once_with(save_credentials=False)


if __name__ == "__main__":
    unittest.main()
