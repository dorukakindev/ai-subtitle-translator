import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui


class CacheIntegrityTest(unittest.TestCase):
    def test_same_length_modification_changes_sig_and_causes_cache_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "sub.srt")
            fp.write_bytes(b"hello")
            ctx = SimpleNamespace(
                source_language="en", summary="s", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )

            ht.save_context_cache(ctx, str(fp), target_language="tr")
            loaded_before = ht.load_context_cache(str(fp), expected_target="tr")
            self.assertIsNotNone(loaded_before)

            # Modify file to same length (5 bytes) within same run
            fp.write_bytes(b"world")
            loaded_after = ht.load_context_cache(str(fp), expected_target="tr")
            self.assertIsNone(loaded_after)

    def test_precontext_sig_changes_on_same_length_modification(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "sub.vtt")
            fp.write_bytes(b"hello")
            sig1 = gui._precontext_cache_sig(str(fp))

            fp.write_bytes(b"world")
            sig2 = gui._precontext_cache_sig(str(fp))

            self.assertTrue(sig1.startswith("sha256:"))
            self.assertTrue(sig2.startswith("sha256:"))
            self.assertNotEqual(sig1, sig2)

    def test_separate_cache_paths_for_srt_and_vtt_in_same_dir(self):
        with tempfile.TemporaryDirectory() as root:
            srt_fp = Path(root, "film.srt")
            vtt_fp = Path(root, "film.vtt")
            srt_fp.write_bytes(b"srt content")
            vtt_fp.write_bytes(b"vtt content")

            srt_cache = ht._cache_path(str(srt_fp))
            vtt_cache = ht._cache_path(str(vtt_fp))

            self.assertNotEqual(srt_cache, vtt_cache)
            self.assertEqual(srt_cache.name, "film.srt.json")
            self.assertEqual(vtt_cache.name, "film.vtt.json")

            gui_srt_cache = gui._precontext_cache_path(str(srt_fp))
            gui_vtt_cache = gui._precontext_cache_path(str(vtt_fp))

            self.assertNotEqual(gui_srt_cache, gui_vtt_cache)
            self.assertEqual(gui_srt_cache.name, "film.srt.precontext.json")
            self.assertEqual(gui_vtt_cache.name, "film.vtt.precontext.json")

    def test_unchanged_file_produces_deterministic_signature(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "same.srt")
            fp.write_bytes(b"unchanged content 123")

            sig1 = ht._cache_sig(str(fp))
            sig2 = ht._cache_sig(str(fp))
            gui_sig = gui._precontext_cache_sig(str(fp))

            self.assertEqual(sig1, sig2)
            self.assertEqual(sig1, gui_sig)
            self.assertTrue(sig1.startswith("sha256:"))

    def test_legacy_size_mtime_signature_causes_cache_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "legacy.srt")
            fp.write_bytes(b"legacy file")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({
                "source_language": "en",
                "summary": "legacy",
                "_sig": "11:1700000000",
                "target_language": "tr",
            }), encoding="utf-8")

            loaded = ht.load_context_cache(str(fp), expected_target="tr")
            self.assertIsNone(loaded)

    def test_target_language_mismatch_causes_cache_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "lang.srt")
            fp.write_bytes(b"language test")
            ctx = SimpleNamespace(
                source_language="en", summary="s", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )

            ht.save_context_cache(ctx, str(fp), target_language="tr")
            self.assertIsNotNone(ht.load_context_cache(str(fp), expected_target="tr"))
            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="de"))

    def test_analysis_depth_mismatch_causes_cache_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "depth.srt")
            fp.write_bytes(b"depth test")
            ctx = SimpleNamespace(
                source_language="en", summary="s", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )

            ht.save_context_cache(ctx, str(fp), target_language="tr", analysis_depth="standard")
            self.assertIsNotNone(ht.load_context_cache(str(fp), expected_target="tr", expected_analysis_depth="standard"))
            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="tr", expected_analysis_depth="deep"))

    def test_corrupt_json_causes_cache_miss_without_crash(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "corrupt.srt")
            fp.write_bytes(b"corrupt test")

            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text("{corrupt json content...", encoding="utf-8")

            # Context cache load returns None gracefully
            loaded = ht.load_context_cache(str(fp))
            self.assertIsNone(loaded)

            pre_cpath = gui._precontext_cache_path(str(fp))
            pre_cpath.write_text("{corrupt json content...", encoding="utf-8")
            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None)
            hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")
            self.assertEqual(hints, {})

    def test_atomic_write_error_preserves_existing_valid_cache(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "atomic.srt")
            fp.write_bytes(b"atomic content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({"valid": True, "summary": "original"}), encoding="utf-8")

            ctx = SimpleNamespace(
                source_language="en", summary="new", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )

            with mock.patch("hybrid_translate.atomic_write_json", side_effect=IOError("Disk error")):
                ht.save_context_cache(ctx, str(fp), target_language="tr")

            # Existing cache remains valid original JSON
            data = json.loads(cpath.read_text(encoding="utf-8"))
            self.assertEqual(data.get("summary"), "original")

    def test_clear_context_cache_clears_target_and_legacy_but_preserves_sibling(self):
        with tempfile.TemporaryDirectory() as root:
            srt_fp = Path(root, "film.srt")
            vtt_fp = Path(root, "film.vtt")
            srt_fp.write_bytes(b"srt")
            vtt_fp.write_bytes(b"vtt")

            srt_cache = ht._cache_path(str(srt_fp))
            vtt_cache = ht._cache_path(str(vtt_fp))
            legacy_cache = ht._legacy_cache_path(str(srt_fp))

            srt_cache.parent.mkdir(parents=True, exist_ok=True)
            srt_cache.write_text("srt cache", encoding="utf-8")
            vtt_cache.write_text("vtt cache", encoding="utf-8")
            legacy_cache.write_text("legacy cache", encoding="utf-8")

            ht.clear_context_cache(str(srt_fp))

            self.assertFalse(srt_cache.exists())
            self.assertFalse(legacy_cache.exists())
            self.assertTrue(vtt_cache.exists())  # sibling preserved!

    def test_turkish_unicode_and_spaced_filenames_work(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "Bölüm 01 - Altyazı ş.srt")
            fp.write_bytes("Türkçe içerik".encode("utf-8"))

            ctx = SimpleNamespace(
                source_language="tr", summary="özet", setting="yer", tone="ton",
                characters=[], recurring_terms={"terim": "karşılık"}, scene_notes=[]
            )

            ht.save_context_cache(ctx, str(fp), target_language="tr")
            loaded = ht.load_context_cache(str(fp), expected_target="tr")

            self.assertIsNotNone(loaded)
            memory = loaded[0]
            self.assertEqual(memory.summary, "özet")
            self.assertEqual(memory.recurring_terms, {"terim": "karşılık"})


if __name__ == "__main__":
    unittest.main()
