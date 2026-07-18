"""
credential_store testleri — keyring'siz fallback yolu ve JSON göçü.
Gerçek keyring'e dokunmamak için _has_keyring False'a, fallback dosyası
geçici dizine yamalanır.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import credential_store as cs


class FallbackRoundtripTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._fb = Path(self._tmp.name) / ".credentials"
        self._patches = [
            mock.patch.object(cs, "_has_keyring", return_value=False),
            mock.patch.object(cs, "_fallback_path", return_value=self._fb),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_save_load_roundtrip(self):
        cs.save_key("openai", "sk-test-12345")
        self.assertEqual(cs.load_key("openai"), "sk-test-12345")

    def test_fallback_file_is_not_plaintext(self):
        cs.save_key("openai", "sk-secret-abcdef")
        raw = self._fb.read_text(encoding="utf-8")
        self.assertNotIn("sk-secret-abcdef", raw, "anahtar düz metin yazılmış!")

    def test_delete_key(self):
        cs.save_key("minimax", "mk-1")
        cs.delete_key("minimax")
        self.assertIsNone(cs.load_key("minimax"))

    def test_missing_key_returns_none(self):
        self.assertIsNone(cs.load_key("nonexistent"))

    def test_migrate_from_settings_strips_json(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps({
            "model": "gpt-5.4-mini",
            "api_key": "sk-legacy-openai-key",
            "minimax_key": "sk-legacy-helper-key",
        }), encoding="utf-8")

        cs.migrate_from_settings(settings)

        d = json.loads(settings.read_text(encoding="utf-8"))
        self.assertNotIn("api_key", d, "api_key JSON'dan silinmemiş")
        self.assertNotIn("minimax_key", d, "minimax_key JSON'dan silinmemiş")
        self.assertEqual(d["model"], "gpt-5.4-mini")  # diğer ayarlar korunur
        self.assertEqual(cs.load_key("openai"), "sk-legacy-openai-key")
        self.assertEqual(cs.load_key("minimax"), "sk-legacy-helper-key")

    def test_migrate_idempotent_on_clean_file(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps({"model": "gpt-5.4-mini"}), encoding="utf-8")
        cs.migrate_from_settings(settings)  # anahtar yok — hata vermemeli
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8"))["model"],
                         "gpt-5.4-mini")

    def test_migrate_role_specific_helper_keys(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps({
            "model": "gpt-5.4-mini",
            "helper_role_key_polish": "sk-polish-role-key",
            "helper_role_key_critic": "sk-critic-role-key",
            "helper_model_polish": "MiniMax M3 (OpenCode Go)",
        }), encoding="utf-8")

        cs.migrate_from_settings(settings)

        d = json.loads(settings.read_text(encoding="utf-8"))
        self.assertNotIn("helper_role_key_polish", d)
        self.assertNotIn("helper_role_key_critic", d)
        self.assertIn("helper_model_polish", d)
        self.assertEqual(cs.load_key("helper_role_polish_key"), "sk-polish-role-key")
        self.assertEqual(cs.load_key("helper_role_critic_key"), "sk-critic-role-key")


if __name__ == "__main__":
    unittest.main()
