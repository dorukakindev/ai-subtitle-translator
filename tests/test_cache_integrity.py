import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui


class CacheIntegrityTest(unittest.TestCase):
    def test_analysis_fingerprint_changes_with_cache_version(self):
        before = ht.analysis_fingerprint("English", "Turkish", "standard", "model")
        old = ht.CONTEXT_ANALYSIS_CACHE_VER
        try:
            ht.CONTEXT_ANALYSIS_CACHE_VER = old + 1
            after = ht.analysis_fingerprint("English", "Turkish", "standard", "model")
        finally:
            ht.CONTEXT_ANALYSIS_CACHE_VER = old
        self.assertNotEqual(before, after)

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
            self.assertIsNone(ht.load_context_cache(str(fp), expected_target="en"))

    def test_degraded_analysis_is_not_cached(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "degraded.srt")
            fp.write_bytes(b"degraded analysis")
            ctx = SimpleNamespace(
                source_language="en", summary="fallback", setting="", tone="fallback",
                characters=[], recurring_terms={}, scene_notes=[],
                _analysis_degraded=True,
            )

            ht.save_context_cache(ctx, str(fp), target_language="tr")

            self.assertFalse(ht._cache_path(str(fp)).exists())

    def test_incomplete_precontext_is_used_but_not_cached(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "partial.srt")
            fp.write_bytes(b"partial precontext")
            app = SimpleNamespace(
                precontext_var=SimpleNamespace(get=lambda: True),
                hybrid_var=SimpleNamespace(get=lambda: False),
                _stop_flag=False,
                _log=lambda *args: None,
                _cached_blocks_for=lambda _p: [("1", "ts", "source")],
                _update_tokens=lambda _n, **_kwargs: None,
                _update_series_memory_from_precontext=lambda *args, **kwargs: None,
            )
            partial = {
                "summary": "usable now",
                "terms": {},
                "_analysis_complete": False,
            }
            with mock.patch(
                    "subtitle_translator_gui.analyze_file_precontext",
                    return_value=partial):
                hints = gui.App._get_precontext_hints(
                    app, None, [str(fp)], "en", "tr", "gpt-5.4")

            self.assertIn(str(fp), hints)
            self.assertFalse(gui._precontext_cache_path(str(fp)).exists())

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

    def test_corrupt_context_json_causes_cache_miss_without_crash(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "corrupt.srt")
            fp.write_bytes(b"corrupt test")

            cpath = ht._cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text("{corrupt json content...", encoding="utf-8")

            loaded = ht.load_context_cache(str(fp))
            self.assertIsNone(loaded)

    def test_corrupt_precontext_json_causes_cache_miss_without_crash(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "corrupt_pre.vtt")
            fp.write_bytes(b"corrupt precontext test")

            pre_cpath = gui._precontext_cache_path(str(fp))
            pre_cpath.parent.mkdir(parents=True, exist_ok=True)
            pre_cpath.write_text("{corrupt json content...", encoding="utf-8")
            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None,
                                  _cached_blocks_for=lambda _p: [],
                                  _update_tokens=lambda _n: None,
                                  _update_series_memory_from_precontext=lambda *args, **kwargs: None)
            with mock.patch("subtitle_translator_gui.analyze_file_precontext", return_value={"terms": {}}):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")
            self.assertEqual(hints, {})

    def test_context_atomic_write_error_preserves_existing_cache(self):
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

            fp.unlink()
            ctx_new = SimpleNamespace(
                source_language="en", summary="new", setting="st", tone="t",
                characters=[], recurring_terms={}, scene_notes=[]
            )
            ht.save_context_cache(ctx_new, str(fp), target_language="tr")

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
                                  _log=lambda *args: None,
                                  _cached_blocks_for=lambda _p: [],
                                  _update_tokens=lambda _n: None,
                                  _update_series_memory_from_precontext=lambda *args, **kwargs: None)

            variants = [
                ("missing", {"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "data": {"characters": [{"name": "OldChar"}]}}),
                ("empty", {"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "_sig": "", "data": {"characters": [{"name": "OldChar"}]}}),
                ("legacy", {"_ver": gui.PRECONTEXT_CACHE_VER, "_tgt": "tr", "_sig": "10:1700000", "data": {"characters": [{"name": "OldChar"}]}}),
            ]

            for label, payload in variants:
                with self.subTest(variant=label):
                    cpath.write_text(json.dumps(payload), encoding="utf-8")
                    mock_analyze = mock.MagicMock(return_value={"characters": [{"name": "NewChar"}]})

                    with mock.patch("subtitle_translator_gui.analyze_file_precontext", mock_analyze):
                        hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

                    mock_analyze.assert_called_once()
                    hint_text = hints.get(str(fp), "")
                    self.assertIn("NewChar", hint_text)
                    self.assertNotIn("OldChar", hint_text)

    def test_precontext_deleted_source_causes_miss(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "pre_del.vtt")
            fp.write_bytes(b"to be deleted precontext")
            cpath = gui._precontext_cache_path(str(fp))
            cpath.parent.mkdir(parents=True, exist_ok=True)
            sig = gui._precontext_cache_sig(str(fp))
            cpath.write_text(json.dumps({
                "_ver": gui.PRECONTEXT_CACHE_VER,
                "_tgt": "tr",
                "_sig": sig,
                "data": {"characters": [{"name": "OldChar"}], "terms": {"old": "eski"}}
            }), encoding="utf-8")

            # Delete source file
            fp.unlink()

            app = SimpleNamespace(precontext_var=SimpleNamespace(get=lambda: True),
                                  hybrid_var=SimpleNamespace(get=lambda: False),
                                  _stop_flag=False,
                                  _log=lambda *args: None,
                                  _cached_blocks_for=lambda _p: None,
                                  _update_tokens=lambda _n: None,
                                  _update_series_memory_from_precontext=lambda *args, **kwargs: None)

            mock_analyze = mock.MagicMock(return_value={"characters": [{"name": "NewChar"}]})
            with mock.patch("subtitle_translator_gui.analyze_file_precontext", mock_analyze), \
                 mock.patch("subtitle_translator_gui.parse_subtitle", side_effect=IOError("File not found")):
                hints = gui.App._get_precontext_hints(app, None, [str(fp)], "en", "tr", "gpt-4o-mini")

            hint_text = hints.get(str(fp), "")
            self.assertNotIn("OldChar", hint_text)
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
            self.assertNotIn("OldChar", hints.get(str(fp), ""))

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

            self.assertIn("yeni", hints.get(str(fp), ""))
            disk_data = json.loads(cpath.read_text(encoding="utf-8"))
            self.assertEqual(disk_data.get("data"), {"terms": {"orig": "orjinal"}})


if __name__ == "__main__":
    unittest.main()
