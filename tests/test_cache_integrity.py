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

            fp.write_bytes(b"world")
            loaded_after = ht.load_context_cache(str(fp), expected_target="tr")
            self.assertIsNone(loaded_after)

    def test_context_cache_missing_sig_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "nosig.srt")
            fp.write_bytes(b"nosig content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({"summary": "no sig"}), encoding="utf-8")

            self.assertIsNone(ht.load_context_cache(str(fp)))

    def test_context_cache_empty_sig_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "emptysig.srt")
            fp.write_bytes(b"emptysig content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({"summary": "empty sig", "_sig": ""}), encoding="utf-8")

            self.assertIsNone(ht.load_context_cache(str(fp)))

    def test_context_cache_legacy_sig_format_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "legacysig.srt")
            fp.write_bytes(b"legacysig content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({"summary": "legacy sig", "_sig": "123:1700000000"}), encoding="utf-8")

            self.assertIsNone(ht.load_context_cache(str(fp)))

    def test_context_cache_deleted_source_file_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "del.srt")
            fp.write_bytes(b"to be deleted")
            ctx = SimpleNamespace(
                source_language="en", summary="s", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )
            ht.save_context_cache(ctx, str(fp), target_language="tr")
            self.assertIsNotNone(ht.load_context_cache(str(fp), expected_target="tr"))

            fp.unlink()
            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="tr"))

    def test_save_context_cache_unreadable_source_skips_write(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "missing.srt")
            ctx = SimpleNamespace(
                source_language="en", summary="s", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )
            ht.save_context_cache(ctx, str(fp), target_language="tr")
            cpath = ht._cache_path(str(fp))
            self.assertFalse(cpath.exists())

    def test_save_context_cache_unreadable_source_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "unreadable.srt")
            fp.write_bytes(b"original content")
            ctx_orig = SimpleNamespace(
                source_language="en", summary="orig", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )
            ht.save_context_cache(ctx_orig, str(fp), target_language="tr")
            cpath = ht._cache_path(str(fp))
            self.assertTrue(cpath.exists())

            # Make file unreadable / missing
            fp.unlink()
            ctx_new = SimpleNamespace(
                source_language="en", summary="new", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )
            ht.save_context_cache(ctx_new, str(fp), target_language="tr")

            # Existing cache file content preserved, not overwritten
            data = json.loads(cpath.read_text(encoding="utf-8"))
            self.assertEqual(data.get("summary"), "orig")

    def test_expected_target_missing_in_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "notarget.srt")
            fp.write_bytes(b"no target content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            sig = ht._cache_sig(str(fp))
            cpath.write_text(json.dumps({"summary": "no target", "_sig": sig}), encoding="utf-8")

            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="tr"))

    def test_expected_analysis_depth_missing_in_cache_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "nodepth.srt")
            fp.write_bytes(b"no depth content")
            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            sig = ht._cache_sig(str(fp))
            cpath.write_text(json.dumps({"summary": "no depth", "_sig": sig, "target_language": "tr"}), encoding="utf-8")

            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="tr", expected_analysis_depth="standard"))

    def test_precontext_cache_missing_empty_legacy_sig_causes_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "pre_sig.vtt")
            fp.write_bytes(b"precontext content")
            cpath = gui._precontext_cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)

            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None)

            # Missing _sig
            cpath.write_text(json.dumps({"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "data": {"terms": {}}}), encoding="utf-8")
            with mock.patch("subtitle_translator_gui.analyze_file_precontext", return_value={"terms": {}}):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

            # Legacy size:mtime _sig
            cpath.write_text(json.dumps({"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "_sig": "10:1700000", "data": {"terms": {}}}), encoding="utf-8")
            with mock.patch("subtitle_translator_gui.analyze_file_precontext", return_value={"terms": {}}):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

    def test_precontext_deleted_source_causes_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "pre_del.vtt")
            fp.write_bytes(b"to be deleted precontext")
            cpath = gui._precontext_cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            sig = gui._precontext_cache_sig(str(fp))
            cpath.write_text(json.dumps({"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "_sig": sig, "data": {"terms": {"x": "y"}}}), encoding="utf-8")

            fp.unlink()
            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None)
            with mock.patch("subtitle_translator_gui.analyze_file_precontext", return_value={"terms": {}}):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")
            self.assertEqual(hints, {})

    def test_precontext_hints_triggers_reanalysis_on_same_length_edit(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "edit.vtt")
            fp.write_bytes(b"hello")
            cpath = gui._precontext_cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            sig1 = gui._precontext_cache_sig(str(fp))
            cpath.write_text(json.dumps({
                "_ver": gui.PRECONTEXT_CACHE_VER,
                "_tgt": "tr",
                "_sig": sig1,
                "data": {"characters": [{"name": "OldChar"}], "terms": {"old": "eski"}}
            }), encoding="utf-8")

            # Same length edit (5 bytes)
            fp.write_bytes(b"world")

            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None,
                                  _cached_blocks_for=lambda _p: [],
                                  _update_tokens=lambda _n: None,
                                  _update_series_memory_from_precontext=lambda *args, **kwargs: None)

            analyzed_fps = []
            def fake_analyze(client, blocks, model, src, tgt, log_fn=None, token_cb=None):
                analyzed_fps.append("analyzed")
                return {"characters": [{"name": "NewChar"}], "terms": {"new": "yeni"}}

            with mock.patch("subtitle_translator_gui.analyze_file_precontext", side_effect=fake_analyze):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

            self.assertEqual(analyzed_fps, ["analyzed"])
            self.assertIn("NewChar", hints.get(str(fp), ""))

    def test_precontext_atomic_write_error_preserves_existing_cache(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "pre_err.vtt")
            fp.write_bytes(b"precontext error test")
            cpath = gui._precontext_cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({
                "_ver": gui.PRECONTEXT_CACHE_VER,
                "_tgt": "tr",
                "_sig": "invalid",
                "data": {"terms": {"orig": "orjinal"}}
            }), encoding="utf-8")

            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None,
                                  _cached_blocks_for=lambda _p: [],
                                  _update_tokens=lambda _n: None,
                                  _update_series_memory_from_precontext=lambda *args, **kwargs: None)

            with mock.patch("subtitle_translator_gui.analyze_file_precontext", return_value={"terms": {"new": "yeni"}}), \
                 mock.patch("subtitle_translator_gui.atomic_write_json", side_effect=IOError("Write failed")):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

            # Translation hints generated from new data
            self.assertIn("yeni", hints.get(str(fp), ""))
            # Existing file on disk remains original content
            disk_data = json.loads(cpath.read_text(encoding="utf-8"))
            self.assertEqual(disk_data.get("data"), {"terms": {"orig": "orjinal"}})

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
            self.assertTrue(vtt_cache.exists())

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
