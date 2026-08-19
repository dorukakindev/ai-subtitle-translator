import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=None):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _Entry:
    def __init__(self):
        self._value = ""

    def get(self):
        return self._value

    def insert(self, _index, value):
        self._value = str(value)


class _HeightVar:
    def __init__(self, value=148):
        self._value = value

    def cget(self, _key=None):
        return self._value

    def configure(self, **kwargs):
        if "height" in kwargs:
            self._value = kwargs["height"]


class _SettingsOnlyApp:
    def __init__(self, settings_path: Path):
        self._path = settings_path
        self.api_key_entry = _Entry()
        self.helper_key_entry = _Entry()
        self.main_custom_key_entry = _Entry()
        self._file_rows_frame = _HeightVar(148)
        self._FILE_LIST_MIN_H = 40
        self._FILE_LIST_MAX_H = 500
        self._helper_keys_cache = {}
        self.helper_roles = {}
        self.helper_model_vars = {}
        self.helper_role_key_vars = {}
        self.helper_custom_provider_vars = {}
        self._toggle_hybrid_calls = 0
        self._restored_geometry = None

        for name, value in {
            "model_var": "gpt-5.4-mini",
            "limit_class_var": "250K",
            "model_2_5m_var": "gpt-5.4-mini",
            "model_250k_var": "gpt-5.4-mini",
            "api_url_var": "",
            "src_var": "English",
            "tgt_var": "Turkish",
            "input_var": "",
            "output_var": "",
            "mode_var": "sync",
            "hybrid_var": False,
            "style_var": "natural",
            "analysis_depth_var": "Standart",
            "glossary_var": "",
            "ext_project_path_var": "",
            "clean_sdh_var": False,
            "content_type_var": "auto",
            "profanity_var": "Orta",
            "critic_var": True,
            "polish_var": True,
            "qc_var": True,
            "native_var": True,
            "backtrans_var": True,
            "semantic_reconcile_var": True,
            "auto_glossary_var": True,
            "linebreak_var": True,
            "condense_var": True,
            "merge_cues_var": True,
            "ai_segment_var": True,
            "chain_ctx_var": True,
            "precontext_var": True,
            "series_memory_var": True,
            "backup_raw_var": True,
            "review_pass_var": True,
            "term_normalize_var": False,
            "term_normalize_apply_var": False,
            "twowave_var": False,
            "main_custom_var": False,
            "main_custom_model_var": "",
            "main_custom_url_var": "",
            "same_folder_var": False,
            "notify_var": True,
        }.items():
            setattr(self, name, _Var(value))

        self._chunk_size = 25
        self._context_lines = 12
        self._lookahead_lines = 8
        self._max_workers = 4
        self._temperature = 0.3
        self._max_retry = 3
        self._scene_gap_seconds = 2.0
        self._merge_max_chars = 84
        self._merge_max_gap_ms = 500

    def _settings_path(self):
        return self._path

    def _get_current_helper_provider(self):
        return "openai_helper"

    def _update_active_model(self, *_args, **_kwargs):
        return None

    def _toggle_hybrid(self):
        self._toggle_hybrid_calls += 1

    def _log(self, msg, level=""):
        pass


class SettingsPersistenceTest(unittest.TestCase):
    def test_main_api_url_sentinel_values_are_cleared(self):
        self.assertEqual(gui._normalize_api_base_url("None"), "")
        self.assertEqual(gui._normalize_api_base_url(" null "), "")
        self.assertEqual(gui._normalize_api_base_url("https://api.example.com/v1/"),
                         "https://api.example.com/v1")

    def test_shuai_openai_routes_are_normalized_to_v1_root(self):
        self.assertEqual(
            gui._normalize_api_base_url("https://api.shuaiapi.com"),
            "https://api.shuaiapi.com/v1")
        self.assertEqual(
            gui._normalize_api_base_url(
                "https://cdn.shuaiapi.com/v1/chat/completions"),
            "https://cdn.shuaiapi.com/v1")
        self.assertEqual(
            gui._normalize_api_base_url("https://oai.sb/v1/"),
            "https://oai.sb/v1")

    def test_saved_false_passes_stay_disabled_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".gui_settings.json"
            settings_path.write_text(json.dumps({
                "api_url": "None",
                "hybrid": False,
                "critic": True,
                "polish": False,
                "qc": False,
                "native": False,
                "backtrans": False,
                "semantic_reconcile": False,
                "clean_sdh": False,
                "auto_glossary": False,
                "linebreak": False,
                "condense": False,
                "merge_cues": False,
                "ai_segment": False,
                "chain_ctx": False,
                "precontext": False,
                "series_memory": False,
                "backup_raw": False,
                "review_pass": False,
                "notify": False,
            }), encoding="utf-8")
            app = _SettingsOnlyApp(settings_path)
            app.hybrid_var.set(True)

            with mock.patch.object(gui.credential_store, "migrate_from_settings"), \
                 mock.patch.object(gui.credential_store, "load_key", return_value=None):
                gui.App._load_settings(app)

            self.assertTrue(app.critic_var.get())
            self.assertFalse(app.hybrid_var.get())
            self.assertEqual(app.api_url_var.get(), "")
            for attr in (
                "polish_var", "qc_var", "native_var", "backtrans_var",
                "semantic_reconcile_var",
                "clean_sdh_var", "auto_glossary_var", "linebreak_var",
                "condense_var", "merge_cues_var", "ai_segment_var",
                "chain_ctx_var", "precontext_var", "series_memory_var",
                "backup_raw_var", "review_pass_var", "notify_var",
            ):
                self.assertFalse(getattr(app, attr).get(), attr)
            self.assertEqual(app._toggle_hybrid_calls, 1)

    def test_legacy_input_and_output_paths_are_session_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / ".gui_settings.json"
            settings_path.write_text(json.dumps({
                "input": r"C:\Users\K",
                "output": r"C:\old-output",
            }), encoding="utf-8")
            app = _SettingsOnlyApp(settings_path)

            with mock.patch.object(gui.credential_store, "migrate_from_settings"), \
                 mock.patch.object(gui.credential_store, "load_key", return_value=None):
                gui.App._load_settings(app)

            self.assertEqual(app.input_var.get(), "")
            self.assertEqual(app.output_var.get(), "")


class ContextLinesClampTest(unittest.TestCase):
    def test_context_lines_and_lookahead_clamped_to_at_least_one(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / ".gui_settings.json"
            d = dict(
                context_lines=0,
                lookahead_lines=-5,
            )
            settings_path.write_text(json.dumps(d), encoding="utf-8")
            app = _SettingsOnlyApp(settings_path)
            with mock.patch.object(gui.credential_store, "migrate_from_settings"), \
                 mock.patch.object(gui.credential_store, "load_key", return_value=None):
                gui.App._load_settings(app)
            self.assertGreaterEqual(app._context_lines, 1)
            self.assertGreaterEqual(app._lookahead_lines, 1)


if __name__ == "__main__":
    unittest.main()
