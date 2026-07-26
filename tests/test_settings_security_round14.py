import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def insert(self, _index, value):
        self._value = str(value)

    def cget(self, _key=None):
        return self._value


class _SecurityApp:
    def __init__(self, settings_path: Path):
        self._path = settings_path
        self.api_key_entry = _Var("")
        self.helper_key_entry = _Var("")
        self.main_custom_key_entry = _Var("")
        self._helper_keys_cache = {}
        self.helper_roles = []
        self.helper_model_vars = {}
        self.helper_role_key_vars = {}
        self.helper_custom_provider_vars = {}
        self.helper_custom_key_vars = {}
        self.logs = []
        self._file_rows_frame = _Var(148)

        for name, value in {
            "model_var": "gpt-5.4-mini",
            "src_var": "English",
            "tgt_var": "Turkish",
            "input_var": "",
            "output_var": "",
            "mode_var": "sync",
            "hybrid_var": False,
            "style_var": "natural",
            "glossary_var": "",
            "analysis_depth_var": "Standart",
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
            "backup_raw_var": True,
            "auto_glossary_var": True,
            "linebreak_var": True,
            "condense_var": True,
            "chain_ctx_var": True,
            "precontext_var": True,
            "series_memory_var": True,
            "review_pass_var": True,
            "term_normalize_var": False,
            "twowave_var": False,
            "main_custom_var": False,
            "main_custom_model_var": "",
            "main_custom_url_var": "",
            "same_folder_var": False,
            "merge_cues_var": True,
            "ai_segment_var": True,
            "notify_var": True,
            "api_url_var": "",
            "limit_class_var": "250K",
            "model_2_5m_var": "gpt-5.4-mini",
            "model_250k_var": "gpt-5.4-mini",
        }.items():
            setattr(self, name, _Var(value))

        self._chunk_size = 25
        self._context_lines = 12
        self._lookahead_lines = 8
        self._max_workers = 4
        self._temperature = 0.3
        self._max_retry = 3
        self._scene_gap_seconds = 3.0
        self._merge_max_chars = 84
        self._merge_max_gap_ms = 500

    def _settings_path(self):
        return self._path

    def _toggle_hybrid(self):
        return None

    def _update_active_model(self, *_args, **_kwargs):
        return None

    def _get_current_helper_provider(self):
        return "openai_helper"

    def geometry(self):
        return "800x600+0+0"

    def _log(self, msg, level=""):
        self.logs.append((level, msg))


class SettingsBackupSecurityTest(unittest.TestCase):
    def test_sanitizer_redacts_non_sk_custom_fields(self):
        raw = ('{"main_custom_key":"AIza-value",'
               '"openai_helper_key":"plain-provider-token",'
               '"helper_analysis_key":"aws-value"}')
        cleaned = gui._sanitize_settings_backup_text(raw)
        self.assertNotIn("AIza-value", cleaned)
        self.assertNotIn("plain-provider-token", cleaned)
        self.assertNotIn("aws-value", cleaned)

    def test_broken_settings_backup_redacts_keys_and_keeps_last_three(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / ".gui_settings.json"
            settings_path.write_text('{"api_key":"sk-secret-123", "helper_key":"sk-helper-999", bad', encoding="utf-8")
            for idx in range(5):
                (Path(td) / f".gui_settings.json.bak.{100 + idx}").write_text(f"old-{idx}", encoding="utf-8")
            app = _SecurityApp(settings_path)
            with mock.patch.object(gui.credential_store, "migrate_from_settings"), \
                 mock.patch.object(gui.credential_store, "load_key", return_value=None):
                gui.App._load_settings(app)

            backups = sorted(Path(td).glob(".gui_settings.json.bak.*"))
            self.assertLessEqual(len(backups), 3)
            # mtime DEĞİL dosya adındaki sayısal suffix'e göre "en yeni"yi bul —
            # bu test 5 sahte + 1 gerçek yedeği art arda, aynı saniye içinde
            # yazıyor; bazı dosya sistemlerinde mtime çözünürlüğü bunu ayırt
            # edemeyip flaky hale getiriyordu (bkz. gui._settings_backup_suffix).
            newest = max(backups, key=gui._settings_backup_suffix)
            bak_text = newest.read_text(encoding="utf-8")
            self.assertNotIn("sk-secret-123", bak_text)
            self.assertNotIn("sk-helper-999", bak_text)
            self.assertIn("[REDACTED]", bak_text)


class SaveSettingsFallbackWarningTest(unittest.TestCase):
    def test_logs_single_warning_when_keyring_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            settings_path = Path(td) / ".gui_settings.json"
            app = _SecurityApp(settings_path)
            app.api_key_entry = _Var("sk-main")
            app.helper_key_entry = _Var("sk-helper")
            with mock.patch.object(gui.credential_store, "save_key", return_value=False), \
                 mock.patch.object(gui.credential_store, "delete_key"):
                gui.App._save_settings(app)

            warn_logs = [msg for level, msg in app.logs if "fallback dosyada saklandı" in msg]
            self.assertEqual(len(warn_logs), 1)

    def test_empty_general_keys_delete_credentials_and_helper_cache(self):
        with tempfile.TemporaryDirectory() as td:
            app = _SecurityApp(Path(td) / ".gui_settings.json")
            app._helper_keys_cache = {
                "openai_helper": "old-helper",
                "anthropic": "keep-this",
            }
            with mock.patch.object(gui.credential_store, "save_key") as save_key, \
                 mock.patch.object(gui.credential_store, "delete_key") as delete_key:
                gui.App._save_settings(app)

            save_key.assert_not_called()
            deleted = {call.args[0] for call in delete_key.call_args_list}
            self.assertIn("openai", deleted)
            self.assertIn("openai_helper", deleted)
            self.assertNotIn("openai_helper", app._helper_keys_cache)
            self.assertEqual(app._helper_keys_cache["anthropic"], "keep-this")


if __name__ == "__main__":
    unittest.main()
