import json
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import credential_store
import hybrid_translate as ht
import series_memory
import subtitle_formats as sf
import subtitle_translator_gui as gui
from translation_memory import TranslationMemory


class CacheAndSessionIdentityTest(unittest.TestCase):
    def test_analysis_fingerprint_covers_all_prompt_inputs(self):
        base = dict(source_language="en", target_language="tr",
                    analysis_depth="standard", model="m1", style="natural",
                    schema={"name": "Belgesel"}, glossary={"A": "B"})
        first = ht.analysis_fingerprint(**base)
        for key, value in (
            ("source_language", "de"), ("target_language", "it"),
            ("analysis_depth", "maximum"), ("model", "m2"),
            ("style", "literal"), ("schema", {"name": "Anime"}),
            ("glossary", {"A": "C"}),
        ):
            changed = dict(base)
            changed[key] = value
            self.assertNotEqual(first, ht.analysis_fingerprint(**changed), key)

    def test_batch_fingerprint_hashes_file_content(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "a.srt"
            fp.write_text("AAAA", encoding="utf-8")
            stamp = fp.stat().st_mtime_ns
            first = ht.batch_session_fingerprint(d, d, [str(fp)], {})
            fp.write_text("BBBB", encoding="utf-8")
            os.utime(fp, ns=(stamp, stamp))
            second = ht.batch_session_fingerprint(d, d, [str(fp)], {})
            self.assertNotEqual(first, second)

    def test_context_cache_uses_declared_source_for_identity(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "a.srt"
            fp.write_text("source", encoding="utf-8")
            context = SimpleNamespace(
                source_language="English", summary="", setting="", tone="",
                characters=[], recurring_terms={}, scene_notes=[],
            )
            ht.save_context_cache(
                context, str(fp), target_language="tr",
                source_language="en", helper_model="model-a",
            )
            data = json.loads(ht._cache_path(str(fp)).read_text(encoding="utf-8"))
            self.assertEqual(data["_source_hint"], "en")
            expected = ht.analysis_fingerprint(
                "en", "tr", "standard", "model-a", "", None, None)
            self.assertEqual(data["_analysis_fp"], expected)

    def test_session_path_normalizes_case_slashes_and_trailing_separator(self):
        with tempfile.TemporaryDirectory() as d:
            canonical = ht._session_path(d)
            variant = ht._session_path(str(Path(d)) + os.sep)
            self.assertEqual(canonical, variant)


class MemoryIsolationTest(unittest.TestCase):
    def test_manual_file_selection_clears_stale_project_memory(self):
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "a.srt")
            Path(fp).write_text("", encoding="utf-8")
            stub = SimpleNamespace(
                _is_running=False,
                _content_type_preflight_done=True,
                _input_folder_explicitly_selected=True,
                _selected_files=[],
                _pm=object(),
                attributes=lambda *_args: None,
                _dedupe_paths=lambda paths: list(paths),
                _refresh_selected_files_ui=lambda *_args: None,
            )
            with mock.patch.object(gui.filedialog, "askopenfilenames",
                                   return_value=(fp,)):
                gui.App._pick_files(stub)
            self.assertIsNone(stub._pm)

    def test_selected_files_use_own_parent_for_series_memory(self):
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "Show.S01E02.srt")
            stub = SimpleNamespace(
                series_memory_var=SimpleNamespace(get=lambda: True),
                input_var=SimpleNamespace(get=lambda: r"C:\stale"),
                _selected_files=[fp],
                _active_snapshot=None,
            )
            with mock.patch.object(series_memory.SeriesMemory, "load",
                                   return_value="memory") as load:
                result = gui.App._series_mem_for(stub, fp)
            self.assertEqual(result, ("memory", 1, 2))
            self.assertEqual(Path(load.call_args.args[0]), Path(d))

    def test_fuzzy_tm_isolates_model_profanity_and_schema(self):
        with tempfile.TemporaryDirectory() as d:
            tm = TranslationMemory(str(Path(d) / "tm.db"))
            tm.store("A very similar source sentence", "Yanlış havuz",
                     model="model-a", tgt_lang="tr",
                     profanity="Sert", schema_name="Anime")
            self.assertIsNone(tm.fuzzy_lookup(
                "A very similar source sentence!", threshold=0.8,
                model="model-b", tgt_lang="tr",
                profanity="Sert", schema_name="Anime"))
            self.assertIsNone(tm.fuzzy_lookup(
                "A very similar source sentence!", threshold=0.8,
                model="model-a", tgt_lang="tr",
                profanity="Hafif", schema_name="Anime"))
            self.assertIsNotNone(tm.fuzzy_lookup(
                "A very similar source sentence!", threshold=0.8,
                model="model-a", tgt_lang="tr",
                profanity="Sert", schema_name="Anime"))
            tm.close()

    def test_hybrid_request_builder_routes_all_tm_dimensions(self):
        cue = SimpleNamespace(
            index=1, start="00:00:01,000", end="00:00:02,000",
            text="A source line.",
        )
        tm = mock.Mock()
        tm.lookup.return_value = None
        tm.fuzzy_lookup.return_value = None

        ht.build_batch_requests(
            [cue], "system", "model-a", tm=tm, tgt_lang="tr",
            profanity="Sert", schema_name="Anime",
        )

        tm.lookup.assert_called_once_with(
            "A source line.", tgt_lang="tr", model="model-a",
            profanity="Sert", schema_name="Anime",
        )
        tm.fuzzy_lookup.assert_called_once_with(
            "A source line.", threshold=0.95, tgt_lang="tr",
            model="model-a", profanity="Sert", schema_name="Anime",
        )

    def test_both_hybrid_flows_forward_tm_dimensions(self):
        for method in (gui.App._run_sync_hybrid, gui.App._run_hybrid):
            source = inspect.getsource(method)
            self.assertIn("profanity=profanity", source)
            self.assertIn('schema_name=schema_dict.get("name", "")', source)


class ParserAndValidationTest(unittest.TestCase):
    def test_auto_glossary_rejects_hallucinated_and_unsafe_pairs(self):
        cues = [SimpleNamespace(index=1, text="The Arc Reactor is ready.")]
        blocks = [("1", "", "Ark Reaktörü hazır.")]
        suggestions = {
            "suggestions": [
                {"src": "Arc Reactor", "tgt": "Ark Reaktörü"},
                {"src": "Not In Source", "tgt": "Uydurma"},
                {"src": "Arc\nReactor", "tgt": "Ark Reaktörü"},
            ]
        }
        response = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(
                    suggestions, ensure_ascii=False)))])
        with mock.patch("openai.OpenAI", return_value=object()), \
                mock.patch.object(ht, "_safe_chat_create", return_value=response):
            result = ht.build_glossary_suggestions(
                cues, blocks, "English", "Turkish", "key")
        self.assertEqual(
            [(item["src"], item["tgt"]) for item in result],
            [("Arc Reactor", "Ark Reaktörü")],
        )

    def test_auto_glossary_preserves_json_format(self):
        with tempfile.TemporaryDirectory() as d:
            glossary = Path(d) / "glossary.json"
            glossary.write_text(json.dumps({"Old": "Eski"}), encoding="utf-8")
            stub = SimpleNamespace(
                _active_snapshot=None,
                src_var=SimpleNamespace(get=lambda: "English"),
                tgt_var=SimpleNamespace(get=lambda: "Turkish"),
                glossary_var=SimpleNamespace(get=lambda: str(glossary)),
                _helper_api_key=lambda _role: "key",
                _helper_api_base_url=lambda _role: "",
                _helper_api_model=lambda _role: "model",
                _log=mock.Mock(),
                _show_glossary_dialog=lambda *_args: None,
                _wait_for_dialog_event=lambda *_args, **_kwargs: "completed",
            )

            def approve(_app, _fn, suggestions, holder, done, _path):
                holder.extend(suggestions)
                done.set()

            with mock.patch.object(
                    ht, "build_glossary_suggestions",
                    return_value=[{"src": "New", "tgt": "Yeni"}]), \
                    mock.patch.object(gui, "_post_ui", side_effect=approve):
                gui.App._run_auto_glossary(stub, [], [], "episode.srt")

            self.assertEqual(
                json.loads(glossary.read_text(encoding="utf-8")),
                {"Old": "Eski", "New": "Yeni"},
            )

    def test_hybrid_array_extractor_rejects_object(self):
        self.assertEqual(ht._extract_json_array('{"items": []}'), "")
        self.assertEqual(json.loads(ht._extract_json_array('{"tr": []}')), [])
        self.assertEqual(json.loads(ht._extract_json_array('[{"i": 1}]')),
                         [{"i": 1}])

    def test_ass_literal_braces_and_vtt_timestamp_tag(self):
        self.assertEqual(sf._clean_ass_text(r"Use {username} {\an8}now"),
                         "Use {username} now")
        self.assertEqual(sf._clean_vtt_text("<00:00:01.500>Hello"), "Hello")

    def test_numeric_normalization_distinguishes_decimal_and_grouping(self):
        self.assertEqual(ht._normalized_numeric_tokens("1,000 and 2.5"),
                         ["1000", "2.5"])
        self.assertEqual(ht._normalized_numeric_tokens("1.000 and 2,5"),
                         ["1000", "2.5"])

    def test_bomless_utf16_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "a.srt"
            fp.write_bytes(
                "1\n00:00:00,000 --> 00:00:01,000\nMerhaba\n".encode("utf-16-le"))
            self.assertIn("Merhaba", sf.read_subtitle_text(fp))
            self.assertNotIn("\x00", sf.read_subtitle_text(fp))


class CredentialAndAccountingTest(unittest.TestCase):
    def test_migration_ignores_non_string_secret_values(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "settings.json"
            fp.write_text(json.dumps({"api_key": 12345, "other": True}),
                          encoding="utf-8")
            with mock.patch.object(credential_store, "save_key") as save:
                credential_store.migrate_from_settings(fp)
            save.assert_not_called()

    def test_settings_redacts_google_and_aws_keys(self):
        raw = "AIza" + "A" * 30 + " AKIA" + "B" * 16
        clean = gui._sanitize_settings_backup_text(raw)
        self.assertNotIn("AIza", clean)
        self.assertNotIn("AKIA", clean)

    def test_batch_token_callback_accepts_cached(self):
        stub = SimpleNamespace(
            _main_model_name=lambda: "gpt-5.4",
            _update_tokens=mock.Mock(),
        )
        gui.App._update_batch_tokens(stub, 100, cached=40)
        self.assertEqual(stub._update_tokens.call_args.kwargs["cached"], 40)


if __name__ == "__main__":
    unittest.main()
