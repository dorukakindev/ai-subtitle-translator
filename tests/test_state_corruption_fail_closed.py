import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import credential_store as credentials
from project_memory import ProjectMemory
from series_memory import SeriesMemory


class CredentialCorruptionTest(unittest.TestCase):
    def test_corrupt_fallback_is_not_overwritten_by_another_service_save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".credentials"
            original = b'{"openai":"existing",broken'
            path.write_bytes(original)

            with patch.object(credentials, "_fallback_path", return_value=path), \
                    patch.object(credentials, "_has_keyring", return_value=False):
                with self.assertRaises(credentials.CredentialStoreCorruptError):
                    credentials.save_key("anthropic", "sk-new-secret")

            self.assertEqual(path.read_bytes(), original)

    def test_corrupt_fallback_load_is_non_destructive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".credentials"
            original = b"not-json"
            path.write_bytes(original)

            with patch.object(credentials, "_fallback_path", return_value=path), \
                    patch.object(credentials, "_has_keyring", return_value=False):
                self.assertIsNone(credentials.load_key("openai"))

            self.assertEqual(path.read_bytes(), original)


class MemoryCorruptionTest(unittest.TestCase):
    def test_project_memory_does_not_replace_corrupt_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".project_memory.json"
            original = b'{"glossary":{"old":"eski"}'
            path.write_bytes(original)
            memory = ProjectMemory(tmpdir)
            memory._data["glossary"]["new"] = "yeni"

            self.assertFalse(memory.save())
            self.assertEqual(path.read_bytes(), original)

    def test_series_memory_does_not_replace_corrupt_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".series_memory" / "show.json"
            path.parent.mkdir(parents=True)
            original = b'{"terms":{"old":"eski"}'
            path.write_bytes(original)
            memory = SeriesMemory.load(tmpdir, "show")
            memory._data["terms"]["new"] = "yeni"

            self.assertFalse(memory.save())
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
