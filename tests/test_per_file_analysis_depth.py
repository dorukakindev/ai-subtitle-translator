import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest import mock

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class PerFileAnalysisDepthTests(unittest.TestCase):
    def test_choice_inherits_global_or_uses_explicit_value(self):
        self.assertEqual(
            gui._resolve_analysis_depth_choice("Varsayılan", "Gelişmiş"),
            "Gelismis",
        )
        self.assertEqual(
            gui._resolve_analysis_depth_choice("Maksimum", "Standart"),
            "Maksimum",
        )

    def test_main_thread_file_choice_overrides_global(self):
        app = SimpleNamespace(
            _active_snapshot={},
            _file_analysis_depth_vars={
                "advanced.srt": _Var("Gelişmiş"),
                "inherit.srt": _Var("Varsayılan"),
            },
            analysis_depth_var=_Var("Maksimum"),
        )
        self.assertEqual(
            gui.App._get_file_analysis_depth(app, "advanced.srt"), "Gelismis")
        self.assertEqual(
            gui.App._get_file_analysis_depth(app, "inherit.srt"), "Maksimum")

    def test_worker_uses_frozen_per_file_snapshot(self):
        app = SimpleNamespace(
            _active_snapshot={
                "analysis_depth": "Standart",
                "file_analysis_depths": {
                    "a.srt": "Gelişmiş",
                    "b.srt": "Maksimum",
                },
            },
            _file_analysis_depth_vars={
                "a.srt": _Var("Standart"),
                "b.srt": _Var("Standart"),
            },
            analysis_depth_var=_Var("Standart"),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            a = pool.submit(gui.App._get_file_analysis_depth, app, "a.srt").result()
            b = pool.submit(gui.App._get_file_analysis_depth, app, "b.srt").result()
        self.assertEqual((a, b), ("Gelismis", "Maksimum"))

    def test_context_cache_is_bound_to_file_depth(self):
        ht = SimpleNamespace(load_context_cache=mock.Mock(return_value="cached"))
        app = SimpleNamespace(
            _get_file_schema=lambda _path: {"name": "Film"},
            _active_snapshot=None,
            _file_analysis_depth_vars={"film.srt": _Var("Maksimum")},
            analysis_depth_var=_Var("Standart"),
            _helper_api_model=lambda _role: "gpt-5.4",
            _helper_api_base_url=lambda _role: "https://helper.example/v1",
            _snap_get=lambda _key, default: default,
            _scene_gap_seconds=3.0,
        )
        result = gui.App._load_context_cache_for_file(
            app, ht, "film.srt", "Turkish", "English",
            schema_dict={"name": "Film"}, glossary={"God": "Tanrı"})
        self.assertEqual(result, "cached")
        self.assertEqual(
            ht.load_context_cache.call_args.kwargs["expected_analysis_depth"],
            "Maksimum",
        )

    def test_snapshot_carries_distinct_file_depths(self):
        class _Stub:
            _chunk_size = 25
            _context_lines = 20
            _lookahead_lines = 10
            _max_workers = 4
            _temperature = 0.2
            _max_retry = 3
            _scene_gap_seconds = 3.0
            _selected_files = ("a.srt", "b.srt")
            _selected_folder_roots = ()
            _file_schema_vars = {}

            input_var = _Var("D:/in")
            output_var = _Var("D:/out")
            src_var = _Var("English")
            tgt_var = _Var("Turkish")
            glossary_var = _Var("")
            ext_project_path_var = _Var("")
            analysis_depth_var = _Var("Standart")

            def __getattr__(self, name):
                if name.endswith("_var"):
                    return _Var(False)
                raise AttributeError(name)

            def _get_srt_files(self):
                return ["a.srt", "b.srt"]

            def _get_file_glossary(self, _path):
                return ""

            def _get_file_source_language(self, _path):
                return "English"

            def _get_file_analysis_depth(self, path):
                return {"a.srt": "Gelismis", "b.srt": "Maksimum"}[path]

            def _schema_by_name(self, _name):
                return {"name": "Otomatik"}

            def _get_schema(self):
                return {"name": "Otomatik"}

            def _main_api_key(self):
                return "key"

            def _main_api_base_url(self):
                return "https://api.openai.com/v1"

            def _main_model_name(self):
                return "gpt-5.4"

            def _helper_api_key(self, _role):
                return "helper"

            def _helper_api_base_url(self, _role):
                return "https://helper.example/v1"

            def _helper_api_model(self, _role):
                return "gpt-5.4"

        snapshot = gui.App._take_run_snapshot(_Stub())
        self.assertEqual(snapshot["file_analysis_depths"], {
            "a.srt": "Gelismis",
            "b.srt": "Maksimum",
        })

    def test_batch_context_and_crash_refresh_keep_file_depths(self):
        depths = {"a.srt": "Gelismis", "b.srt": "Maksimum"}
        context = gui._batch_run_context({
            "analysis_depth": "Standart",
            "file_analysis_depths": depths,
        })
        self.assertEqual(context["file_analysis_depths"], depths)
        merged = gui._refresh_start_snapshot(
            {"crash_resume": True, "file_analysis_depths": {"old": "Standart"}},
            {"file_analysis_depths": depths},
        )
        self.assertEqual(merged["file_analysis_depths"], depths)


if __name__ == "__main__":
    unittest.main()
