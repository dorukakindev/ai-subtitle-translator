import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import subtitle_translator_gui as gui


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Entry(Var):
    def delete(self, _start, _end):
        self.value = ""

    def insert(self, _index, value):
        self.value = value


def app_stub():
    roles = ("analysis", "critic", "polish", "qc")
    app = SimpleNamespace(
        _api_key_profiles={},
        _api_key_assignments={},
        _api_keys_dialog=None,
        main_custom_var=Var(False),
        api_key_entry=Entry(),
        api_url_var=Var(),
        main_custom_model_var=Var(),
        main_custom_url_var=Var(),
        main_custom_key_entry=Entry(),
        model_var=Var("gpt-5.4"),
        limit_class_var=Var("250K"),
        model_2_5m_var=Var(),
        model_250k_var=Var(),
        helper_model_vars={r: Var() for r in roles},
        helper_custom_provider_vars={r: Var() for r in roles},
        helper_custom_model_vars={r: Var() for r in roles},
        helper_custom_url_vars={r: Var() for r in roles},
        helper_custom_key_vars={r: Var() for r in roles},
        helper_role_key_vars={r: Var("old") for r in roles},
        _sync_main_custom_visibility=lambda: None,
        _on_helper_model_change_role=lambda _role: None,
        _save_settings=lambda *args, **kwargs: None,
        _log=lambda *args, **kwargs: None,
    )
    app._replace_entry_value = lambda entry, value: (
        entry.delete(0, "end"), entry.insert(0, value))
    return app


class ApiKeyProfileTest(unittest.TestCase):
    def test_sanitizer_never_persists_secrets(self):
        pid = "a" * 32
        profiles = gui._sanitize_api_key_profiles({
            pid: {
                "name": "Reseller",
                "provider": "openai_compatible",
                "model": "gpt-5.4",
                "base_url": "https://example.test/v1",
                "api_key": "sk-should-not-survive",
                "secret": "also-no",
            }
        })
        self.assertEqual(set(profiles[pid]), {"name", "provider", "model", "base_url"})
        self.assertNotIn("sk-should-not-survive", repr(profiles))

    def test_assign_reseller_to_main_populates_custom_route(self):
        app = app_stub()
        app._save_settings = Mock()
        pid = "b" * 32
        app._api_key_profiles[pid] = {
            "name": "GPT Reseller", "provider": "openai_compatible",
            "model": "gpt-5.4", "base_url": "https://reseller.test/v1",
        }
        with patch.object(gui.credential_store, "load_key", return_value="sk-profile"):
            result = gui.App._apply_api_profile(app, pid, "main", notify=False)
        self.assertTrue(result)
        self.assertTrue(app.main_custom_var.get())
        self.assertEqual(app.main_custom_model_var.get(), "gpt-5.4")
        self.assertEqual(app.main_custom_url_var.get(), "https://reseller.test/v1")
        self.assertEqual(app.main_custom_key_entry.get(), "sk-profile")
        self.assertEqual(app._api_key_assignments["main"], pid)
        # Anahtar da güvenli depoya yazılmalı; aksi hâlde uygulama yeniden
        # açıldığında özel model seçili gelip anahtar boş kalıyor ve 401 alınıyordu.
        app._save_settings.assert_called_once_with(save_credentials=True)

    def test_assign_claude_to_critic_populates_custom_helper(self):
        app = app_stub()
        pid = "c" * 32
        app._api_key_profiles[pid] = {
            "name": "Claude", "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "base_url": "https://api.anthropic.com/v1/messages",
        }
        with patch.object(gui.credential_store, "load_key", return_value="claude-key"):
            result = gui.App._apply_api_profile(app, pid, "critic", notify=False)
        self.assertTrue(result)
        self.assertEqual(app.helper_model_vars["critic"].get(), "Özel (Custom)")
        self.assertEqual(app.helper_custom_provider_vars["critic"].get(), "anthropic")
        self.assertEqual(app.helper_custom_model_vars["critic"].get(), "claude-sonnet-4-6")
        self.assertEqual(app.helper_custom_key_vars["critic"].get(), "claude-key")
        self.assertEqual(app.helper_role_key_vars["critic"].get(), "")

    def test_assigned_profile_key_wins_in_real_resolvers(self):
        pid = "d" * 32
        app = SimpleNamespace(
            _active_snapshot=None,
            _api_key_profiles={pid: {"name": "P"}},
            _api_key_assignments={"main": pid, "qc": pid},
        )
        with patch.object(gui.credential_store, "load_key", return_value="profile-key"):
            self.assertEqual(gui.App._main_api_key(app), "profile-key")
            self.assertEqual(gui.App._helper_api_key(app, "qc"), "profile-key")

    def test_assigned_profile_locks_main_route_against_manual_custom_values(self):
        pid = "e" * 32
        app = app_stub()
        app._api_key_profiles[pid] = {
            "name": "P", "provider": "openai_compatible",
            "model": "profile-model", "base_url": "https://profile.test/v1",
        }
        app._api_key_assignments["main"] = pid
        app.main_custom_var.set(True)
        app.main_custom_model_var.set("manual-model")
        app.main_custom_url_var.set("https://manual.test/v1")
        app.main_custom_key_entry.set("manual-key")

        with patch.object(gui.credential_store, "load_key", return_value="profile-key"):
            self.assertEqual(gui.App._main_api_key(app), "profile-key")
        self.assertEqual(gui.App._main_model_name(app), "profile-model")
        self.assertEqual(gui.App._main_api_base_url(app), "https://profile.test/v1")

    def test_assigned_profile_locks_helper_route_against_manual_custom_values(self):
        pid = "f" * 32
        app = app_stub()
        app._api_key_profiles[pid] = {
            "name": "P", "provider": "anthropic",
            "model": "profile-model", "base_url": "https://profile.test/v1/messages",
        }
        app._api_key_assignments["critic"] = pid
        app.helper_model_vars["critic"].set("Özel (Custom)")
        app.helper_custom_provider_vars["critic"].set("openai")
        app.helper_custom_model_vars["critic"].set("manual-model")
        app.helper_custom_url_vars["critic"].set("https://manual.test/v1")
        app.helper_custom_key_vars["critic"].set("manual-key")

        cfg = gui.App._helper_model_config(app, "critic")
        self.assertEqual((cfg.provider, cfg.model, cfg.base_url), (
            "anthropic", "profile-model", "https://profile.test/v1/messages"))
        with patch.object(gui.credential_store, "load_key", return_value="profile-key"):
            self.assertEqual(gui.App._helper_api_key(app, "critic"), "profile-key")

    def test_delete_profile_only_removes_profile_credential(self):
        app = app_stub()
        app._refresh_api_keys_panel = Mock()
        pid = "1" * 32
        app._api_key_profiles[pid] = {
            "name": "P", "provider": "openai_compatible",
            "model": "model", "base_url": "https://profile.test/v1",
        }
        app._api_key_assignments = {"main": pid, "critic": pid}

        with patch.object(gui.messagebox, "askyesno", return_value=True), \
                patch.object(gui.credential_store, "delete_key") as delete:
            gui.App._delete_api_profile(app, pid)

        delete.assert_called_once_with(f"api_profile_{pid}")
        self.assertEqual(app._api_key_assignments, {})


if __name__ == "__main__":
    unittest.main()
