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
from project_memory import ProjectMemory
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

    def test_batch_fingerprint_is_stable_when_files_are_added(self):
        with tempfile.TemporaryDirectory() as d:
            fp = Path(d) / "a.srt"
            fp.write_text("AAAA", encoding="utf-8")
            first = ht.batch_session_fingerprint(d, d, [str(fp)], {})
            second_fp = Path(d) / "b.srt"
            second_fp.write_text("BBBB", encoding="utf-8")
            second = ht.batch_session_fingerprint(
                d, d, [str(fp), str(second_fp)], {})
            self.assertEqual(first, second)

    def test_batch_fingerprint_changes_with_settings(self):
        with tempfile.TemporaryDirectory() as d:
            first = ht.batch_session_fingerprint(d, d, [], {"model": "a"})
            second = ht.batch_session_fingerprint(d, d, [], {"model": "b"})
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

    def test_gui_context_cache_loader_forwards_full_fingerprint(self):
        loader = mock.Mock(return_value="cached")
        ht_stub = SimpleNamespace(
            load_context_cache=loader,
            load_glossary=lambda _path, **_kwargs: {"User": "Kullanıcı"},
        )
        stub = SimpleNamespace(
            _active_snapshot=None,
            analysis_depth_var=SimpleNamespace(get=lambda: "Maksimum"),
            style_var=SimpleNamespace(get=lambda: "natural"),
            _get_file_schema=lambda _fp: {"name": "Belgesel"},
            _get_file_glossary=lambda _fp: "terms.json",
            _merge_schema_glossary=lambda glossary, _schema: glossary,
            _helper_api_model=lambda _role: "gpt-5.4",
            _helper_api_base_url=lambda _role: "https://helper.example/v1",
            _scene_gap_seconds=3.0,
            _snap_get=lambda key, default=None: default,
        )

        result = gui.App._load_context_cache_for_file(
            stub, ht_stub, "movie.srt", "Turkish", "Spanish")

        self.assertEqual(result, "cached")
        loader.assert_called_once_with(
            "movie.srt",
            expected_target="Turkish",
            expected_analysis_depth="Maksimum",
            expected_source="es",
            helper_model="gpt-5.4",
            helper_url="https://helper.example/v1",
            style="natural",
            schema={"name": "Belgesel"},
            glossary={"User": "Kullanıcı"},
            expected_scene_gap_sec=3.0,
        )


class MemoryIsolationTest(unittest.TestCase):
    def test_source_languages_use_isolated_project_memory_files(self):
        with tempfile.TemporaryDirectory() as td:
            english = ProjectMemory(td, "tr", "en")
            english.update_glossary({"hello": "merhaba"})
            spanish = ProjectMemory(td, "tr", "es")
            spanish.update_glossary({"si": "evet"})

            self.assertEqual(
                ProjectMemory(td, "tr", "en").get_glossary(),
                {"hello": "merhaba"},
            )
            self.assertEqual(
                ProjectMemory(td, "tr", "es").get_glossary(),
                {"si": "evet"},
            )
            self.assertTrue((Path(td) / ".project_memory.json").exists())
            self.assertTrue(
                (Path(td) / ".project_memory.src-es.tgt-tr.json").exists())

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

    def test_selected_episode_subfolder_uses_common_tv_root_for_series_memory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "Show.(2001).tv.s01.eng.2cd"
            fp = str(root / "episode 2" / "Show - Puntata 2.srt")
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
            self.assertEqual(Path(load.call_args.args[0]), root)

    def test_series_memory_worker_uses_snapshot_without_reading_tk(self):
        with tempfile.TemporaryDirectory() as d:
            fp = str(Path(d) / "Show.S01E02.srt")
            tk_get = mock.MagicMock(side_effect=AssertionError("Tk read"))
            stub = SimpleNamespace(
                series_memory_var=SimpleNamespace(get=tk_get),
                input_var=SimpleNamespace(get=lambda: r"C:\stale"),
                tgt_var=SimpleNamespace(get=tk_get),
                _selected_files=[fp],
                _active_snapshot={
                    "series_memory": True,
                    "selected_files": [fp],
                    "src_lang": "English",
                    "tgt_lang": "Turkish",
                },
                _effective_file_source_language=lambda *_args: "English",
            )
            with mock.patch.object(series_memory.SeriesMemory, "load",
                                   return_value="memory"), \
                 mock.patch.object(gui.threading, "current_thread",
                                   return_value=object()), \
                 mock.patch.object(gui.threading, "main_thread",
                                   return_value=object()):
                result = gui.App._series_mem_for(stub, fp)
            self.assertEqual(result, ("memory", 1, 2))
            tk_get.assert_not_called()

    def test_series_memory_persist_uses_snapshot_target_without_reading_tk(self):
        tk_get = mock.MagicMock(side_effect=AssertionError("Tk read"))
        memory = SimpleNamespace(save=mock.MagicMock())
        merge = mock.MagicMock()
        stub = SimpleNamespace(
            tgt_var=SimpleNamespace(get=tk_get),
            _active_snapshot={"tgt_lang": "German"},
            _series_mem_for=lambda *_args, **_kwargs: (memory, 1, 2),
            _merge_analysis_into_series_memory=merge,
        )
        with mock.patch.object(gui.threading, "current_thread",
                               return_value=object()), \
             mock.patch.object(gui.threading, "main_thread",
                               return_value=object()):
            gui.App._update_series_memory_from_analysis(
                stub, "Show.S01E02.srt", SimpleNamespace(), {})

        tk_get.assert_not_called()
        merge.assert_called_once_with(
            memory, 1, 2, mock.ANY, {}, "German")
        memory.save.assert_called_once_with()

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
            source_language="Spanish", context_fingerprint="source-sha",
        )

        tm.lookup.assert_called_once_with(
            "A source line.", tgt_lang="tr", model="model-a",
            profanity="Sert", schema_name="Anime",
            source_language="Spanish",
            context_fingerprint="source-sha",
        )
        tm.fuzzy_lookup.assert_called_once_with(
            "A source line.", threshold=0.95, tgt_lang="tr",
            model="model-a", profanity="Sert", schema_name="Anime",
            source_language="Spanish",
            context_fingerprint="source-sha",
            allow_contextless_final=False,
        )

    def test_both_hybrid_flows_forward_tm_dimensions(self):
        for method in (gui.App._run_sync_hybrid, gui.App._run_hybrid):
            source = inspect.getsource(method)
            self.assertIn("profanity=profanity", source)
            self.assertIn('schema_name=schema_dict.get("name", "")', source)
            self.assertIn("source_language=file_src", source)

    def test_plain_sync_and_tm_store_forward_source_language(self):
        run_source = inspect.getsource(gui.App._run_sync)
        self.assertIn('r["source_language"] = group_src', run_source)
        self.assertIn("source_language=group_src", run_source)
        self.assertIn("source_language=source_language", run_source)

        store_source = inspect.getsource(gui.App._store_tm_pairs)
        self.assertIn("source_language=source_language", store_source)


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

    def test_auto_glossary_reports_empty_provider_response_as_failure(self):
        cues = [SimpleNamespace(index=1, text="The Arc Reactor is ready.")]
        blocks = [("1", "", "Ark Reaktörü hazır.")]
        response = SimpleNamespace(choices=[], usage=None)
        status = {}
        with mock.patch("openai.OpenAI", return_value=object()), \
                mock.patch.object(ht, "_safe_chat_create", return_value=response):
            result = ht.build_glossary_suggestions(
                cues, blocks, "English", "Turkish", "key",
                status_out=status)

        self.assertEqual(result, [])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 1)
        self.assertEqual(status["total_chunks"], 1)

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
            _main_api_base_url=lambda: "https://api.openai.com/v1",
            _update_tokens=mock.Mock(),
        )
        gui.App._update_batch_tokens(stub, 100, cached=40)
        self.assertEqual(stub._update_tokens.call_args.kwargs["cached"], 40)

    def test_batch_token_cost_hidden_for_third_party_route(self):
        """Kullanıcının kendi proxy'sinde sahte OpenAI USD tutarı gösterilmemeli."""
        stub = SimpleNamespace(
            _main_model_name=lambda: "gpt-5.4",
            _main_api_base_url=lambda: "https://api.shuaiapi.com/v1",
            _update_tokens=mock.Mock(),
        )
        gui.App._update_batch_tokens(stub, 100)
        self.assertIsNone(stub._update_tokens.call_args.kwargs["price"])


if __name__ == "__main__":
    unittest.main()
