"""
project_memory.py — detect_series_key ve temel hafıza işlemleri testleri.
"""
import tempfile
import unittest
from pathlib import Path

from project_memory import ProjectMemory


class SeriesKeyDetectionTest(unittest.TestCase):
    def test_season_episode_format(self):
        key = ProjectMemory.detect_series_key("ShowName.S01E05.en.srt")
        self.assertEqual(key, "S01")

    def test_season_two_digit(self):
        key = ProjectMemory.detect_series_key("Show.S12E01.srt")
        self.assertEqual(key, "S12")

    def test_ep_format_preserves_number(self):
        """EP01, EP02 farklı kovalar olmalı — hepsi 'EP' döndürmemeli."""
        key1 = ProjectMemory.detect_series_key("Movie.EP01.srt")
        key2 = ProjectMemory.detect_series_key("Movie.EP02.srt")
        self.assertNotEqual(key1, key2)
        self.assertEqual(key1, "EP001")
        self.assertEqual(key2, "EP002")

    def test_unrecognized_returns_none(self):
        key = ProjectMemory.detect_series_key("random_video.srt")
        self.assertIsNone(key)


class ProjectMemoryOpsTest(unittest.TestCase):
    def _make_pm(self) -> ProjectMemory:
        d = tempfile.mkdtemp()
        return ProjectMemory(d)

    def test_glossary_roundtrip(self):
        pm = self._make_pm()
        pm.update_glossary({"hello": "merhaba", "world": "dünya"})
        gl = pm.get_glossary()
        self.assertEqual(gl["hello"], "merhaba")
        self.assertEqual(gl["world"], "dünya")

    def test_existing_glossary_not_overwritten(self):
        pm = self._make_pm()
        pm.update_glossary({"term": "ilk_çeviri"})
        pm.update_glossary({"term": "yeni_çeviri"})  # var olan korunmalı
        self.assertEqual(pm.get_glossary()["term"], "ilk_çeviri")

    def test_characters_stored(self):
        pm = self._make_pm()
        pm.update_characters(["Alice", "Bob"])
        chars = pm.get_characters()
        self.assertIn("Alice", chars)
        self.assertIn("Bob", chars)

    def test_stats_counts(self):
        pm = self._make_pm()
        pm.update_glossary({"a": "1", "b": "2"})
        pm.add_note("Seri notu")
        s = pm.stats()
        self.assertEqual(s["glossary"], 2)
        self.assertEqual(s["notes"], 1)

    def test_build_context_hint_includes_terms(self):
        pm = self._make_pm()
        pm.update_glossary({"Chaos Marine": "Kaos Denizlisi"})
        hint = pm.build_context_hint()
        self.assertIn("Chaos Marine", hint)
        self.assertIn("Kaos Denizlisi", hint)


if __name__ == "__main__":
    unittest.main()
