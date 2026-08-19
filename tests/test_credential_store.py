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

    @unittest.skipUnless(os.name == "nt", "Windows fallback ACL applies only on Windows")
    def test_windows_fallback_removes_inherited_acl_before_replacing_file(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0)) as run:
            cs.save_key("openai", "sk-secret-abcdef")
        command = run.call_args.args[0]
        self.assertIn("/inheritance:r", command)
        self.assertIn("*S-1-5-18:F", command)
        self.assertIn("*S-1-5-32-544:F", command)
        # Kullanıcı hesabı da yetkilendirilmeli. Türkçe karakterli kullanıcı
        # adlarında icacls Error 1332 verdiği için hesap tercihen SID ile verilir.
        self.assertTrue(any(
            part.endswith(":F")
            and part not in {"*S-1-5-18:F", "*S-1-5-32-544:F"}
            for part in command))

    @unittest.skipUnless(os.name == "nt", "Windows fallback ACL applies only on Windows")
    def test_windows_acl_failure_preserves_existing_fallback(self):
        original = '{"old":"value"}'
        self._fb.write_text(original, encoding="utf-8")
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=1)):
            with self.assertRaisesRegex(OSError, "ACL"):
                cs.save_key("openai", "sk-secret-abcdef")
        self.assertEqual(self._fb.read_text(encoding="utf-8"), original)
        self.assertFalse(list(self._fb.parent.glob(f".{self._fb.name}.*.tmp")))

    def test_delete_key(self):
        cs.save_key("minimax", "mk-1")
        cs.delete_key("minimax")
        self.assertIsNone(cs.load_key("minimax"))

    def test_missing_key_returns_none(self):
        self.assertIsNone(cs.load_key("nonexistent"))

    def test_malformed_fallback_container_fails_closed(self):
        self._fb.write_text("[]", encoding="utf-8")
        self.assertIsNone(cs.load_key("openai"))
        with self.assertRaises(cs.CredentialStoreCorruptError):
            cs.save_key("openai", "sk-safe")
        self.assertEqual(self._fb.read_text(encoding="utf-8"), "[]")

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

    def test_migrate_short_secret_does_not_remain_plaintext(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps({"api_key": "abcde"}), encoding="utf-8")

        cs.migrate_from_settings(settings)

        self.assertNotIn("api_key", json.loads(settings.read_text(encoding="utf-8")))
        self.assertEqual(cs.load_key("openai"), "abcde")

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

    def test_migrate_custom_and_openai_helper_keys(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps({
            "main_custom_key": "provider-secret-value",
            "openai_helper_key": "helper-secret-value",
            "helper_custom_key_qc": "qc-secret-value",
        }), encoding="utf-8")
        cs.migrate_from_settings(settings)
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), {})
        self.assertEqual(cs.load_key("main_custom"), "provider-secret-value")
        self.assertEqual(cs.load_key("openai_helper"), "helper-secret-value")
        self.assertEqual(cs.load_key("helper_qc_key"), "qc-secret-value")

    def test_migration_write_failure_preserves_original_settings_file(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        original = json.dumps({
            "model": "gpt-5.4-mini",
            "api_key": "sk-legacy-openai-key",
        })
        settings.write_text(original, encoding="utf-8")

        with mock.patch.object(cs, "save_key", return_value=True), \
             mock.patch.object(cs.os, "replace", side_effect=OSError("locked")):
            with self.assertRaisesRegex(OSError, "locked"):
                cs.migrate_from_settings(settings)

        self.assertEqual(settings.read_text(encoding="utf-8"), original)
        self.assertFalse(list(settings.parent.glob(
            f".{settings.name}.*.tmp")))


if __name__ == "__main__":
    unittest.main()
