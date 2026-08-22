# -*- coding: utf-8 -*-
"""Kaynak dil / içerik türü tespitinin kalıcı önbelleği.

Tespitler eskiden yalnız koşu anlık görüntüsünde yaşıyordu; program kapanınca
kaybolup aynı dosya için yardımcı model baştan çalışıyordu.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


SRT = (
    "1\n00:00:01,000 --> 00:00:02,000\nBonjour.\n\n"
    "2\n00:00:03,000 --> 00:00:04,000\nCa va?\n"
)


class DetectionCacheTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "film.srt")
        Path(self.path).write_text(SRT, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_cache_returns_empty(self):
        self.assertEqual(g.load_detection_cache(self.path), {})

    def test_roundtrip_language_and_content_type(self):
        self.assertTrue(g.save_detection_cache(
            self.path, source_language="French", content_type="Belgesel"))
        data = g.load_detection_cache(self.path)
        self.assertEqual(data.get("source_language"), "French")
        self.assertEqual(data.get("content_type"), "Belgesel")

    def test_cache_lives_next_to_the_file(self):
        g.save_detection_cache(self.path, source_language="French")
        expected = Path(self._tmp.name) / ".context_cache" / "film.srt.detect.json"
        self.assertTrue(expected.exists())

    def test_none_keeps_the_other_field(self):
        g.save_detection_cache(self.path, source_language="French")
        g.save_detection_cache(self.path, content_type="Belgesel")
        data = g.load_detection_cache(self.path)
        self.assertEqual(data.get("source_language"), "French")
        self.assertEqual(data.get("content_type"), "Belgesel")

    def test_auto_clears_the_field(self):
        g.save_detection_cache(
            self.path, source_language="French", content_type="Belgesel")
        g.save_detection_cache(self.path, source_language=g.AUTO_LANGUAGE)
        data = g.load_detection_cache(self.path)
        self.assertNotIn("source_language", data)
        self.assertEqual(data.get("content_type"), "Belgesel")

    def test_all_auto_removes_the_cache_file(self):
        g.save_detection_cache(self.path, source_language="French")
        self.assertFalse(g.save_detection_cache(
            self.path, source_language=g.AUTO_LANGUAGE))
        self.assertEqual(g.load_detection_cache(self.path), {})

    def test_changed_source_invalidates_cache(self):
        g.save_detection_cache(
            self.path, source_language="French", content_type="Belgesel")
        Path(self.path).write_text(SRT + "\n3\n00:00:05,000 --> 00:00:06,000\nOui.\n",
                                   encoding="utf-8")
        self.assertEqual(g.load_detection_cache(self.path), {})

    def test_corrupt_cache_is_ignored(self):
        g.save_detection_cache(self.path, source_language="French")
        cache = Path(self._tmp.name) / ".context_cache" / "film.srt.detect.json"
        cache.write_text("{ bozuk", encoding="utf-8")
        self.assertEqual(g.load_detection_cache(self.path), {})

    def test_missing_file_is_not_written(self):
        self.assertFalse(g.save_detection_cache(
            os.path.join(self._tmp.name, "yok.srt"), source_language="French"))

    def test_saved_language_is_normalized(self):
        g.save_detection_cache(self.path, source_language="french")
        self.assertEqual(
            g.load_detection_cache(self.path).get("source_language"),
            g.normalize_language_name("french"))


class RememberedValueTest(unittest.TestCase):
    """App metotları, örnek kurmadan (unbound) çağrılarak sınanır."""

    class _Stub:
        def __init__(self):
            self.logs = []

        def _log(self, msg, level="info"):
            self.logs.append((msg, level))

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._tmp.name, "film.srt")
        Path(self.path).write_text(SRT, encoding="utf-8")
        self.stub = self._Stub()

    def tearDown(self):
        self._tmp.cleanup()

    def test_explicit_global_language_wins_over_cache(self):
        g.save_detection_cache(self.path, source_language="French")
        got = g.App._remembered_source_language(self.stub, self.path, "English")
        self.assertEqual(got, "English")
        self.assertFalse(self.stub.logs)

    def test_cache_fills_in_auto_language(self):
        g.save_detection_cache(self.path, source_language="French")
        got = g.App._remembered_source_language(
            self.stub, self.path, g.AUTO_LANGUAGE)
        self.assertEqual(got, g.normalize_language_name("French"))
        self.assertTrue(self.stub.logs)

    def test_auto_stays_auto_without_cache(self):
        got = g.App._remembered_source_language(
            self.stub, self.path, g.AUTO_LANGUAGE)
        self.assertEqual(got, g.AUTO_LANGUAGE)

    def test_explicit_global_content_type_wins_over_cache(self):
        g.save_detection_cache(self.path, content_type="Belgesel")
        got = g.App._remembered_content_type(self.stub, self.path, "Anime")
        self.assertEqual(got, "Anime")

    def test_cache_fills_in_auto_content_type(self):
        g.save_detection_cache(self.path, content_type="Belgesel")
        got = g.App._remembered_content_type(self.stub, self.path, "Otomatik")
        self.assertEqual(got, "Belgesel")
        self.assertTrue(self.stub.logs)

    def test_unknown_schema_name_is_rejected(self):
        cache = Path(self._tmp.name) / ".context_cache"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "film.srt.detect.json").write_text(json.dumps({
            "_sig": g._precontext_cache_sig(self.path),
            "content_type": "Boyle Bir Tur Yok",
        }), encoding="utf-8")
        got = g.App._remembered_content_type(self.stub, self.path, "Otomatik")
        self.assertEqual(got, "Otomatik")


if __name__ == "__main__":
    unittest.main()
