import unittest
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class SeasonCanonSelectionTest(unittest.TestCase):
    def test_delivery_ids_are_realigned_by_source_timestamps(self):
        source = [
            ("10", "00:00:01,000 --> 00:00:02,000", "Hello"),
            ("20", "00:00:03,000 --> 00:00:04,000", "World"),
        ]
        output = [
            ("1", "00:00:00,000 --> 00:00:00,999", "discord: ceviri2"),
            ("2", "00:00:01,000 --> 00:00:02,000", "Merhaba"),
            ("3", "00:00:02,100 --> 00:00:02,900", "discord: ceviri2"),
            ("4", "00:00:03,000 --> 00:00:04,000", "Dünya"),
        ]
        aligned, unmapped = gui._align_delivery_blocks_to_source(source, output)
        self.assertEqual([row[0] for row in aligned], ["10", "20"])
        self.assertEqual(unmapped, [])

    def test_missing_canonical_rendering_is_selected(self):
        blocks = [("4", "00:00:01,000 --> 00:00:02,000", "Arabulucu geldi.")]
        source = {"4": "The Negotiator arrived."}
        self.assertEqual(
            gui._season_canon_suspect_ids(
                blocks, source, {"Negotiator": "Müzakereci"}),
            {"4"},
        )

    def test_inflected_canonical_rendering_is_accepted(self):
        blocks = [("4", "00:00:01,000 --> 00:00:02,000", "Müzakereciyi çağır.")]
        source = {"4": "Call the Negotiator."}
        self.assertEqual(
            gui._season_canon_suspect_ids(
                blocks, source, {"Negotiator": "Müzakereci"}),
            set(),
        )

    def test_unrelated_source_is_not_selected(self):
        blocks = [("4", "00:00:01,000 --> 00:00:02,000", "Onu çağır.")]
        source = {"4": "Call him."}
        self.assertEqual(
            gui._season_canon_suspect_ids(
                blocks, source, {"Negotiator": "Müzakereci"}),
            set(),
        )

    def test_explicit_sen_siz_lines_are_selected_for_address_canon(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Sana söyledim."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Kapıyı aç."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Sizin kararınız."),
        ]
        self.assertEqual(gui._season_address_suspect_ids(blocks), {"1", "3"})

    def test_artifact_names_do_not_collide_across_sources_or_runs(self):
        first = gui._season_canon_artifact_stem(
            "show", 1, 2, "C:/one/show.S01E02.srt", "run-1")
        second = gui._season_canon_artifact_stem(
            "show", 1, 2, "D:/two/show.S01E02.srt", "run-1")
        later = gui._season_canon_artifact_stem(
            "show", 1, 2, "C:/one/show.S01E02.srt", "run-2")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, later)

    def test_series_memory_address_map_is_returned_as_copy(self):
        memory = gui.series_memory.SeriesMemory.__new__(gui.series_memory.SeriesMemory)
        memory._data = {
            "address_map": [{"a": "Sam", "b": "Chief", "register": "siz"}]
        }
        result = memory.get_address_map()
        result[0]["register"] = "sen"
        self.assertEqual(memory._data["address_map"][0]["register"], "siz")


class MediaModeTest(unittest.TestCase):
    def _app(self):
        return SimpleNamespace(
            content_type_var=_Var("Otomatik"),
            series_memory_var=_Var(False),
            season_canon_var=_Var(False),
            media_mode_var=_Var("Dizi"),
            season_canon_switch=None,
            _log=lambda *_args: None,
            _sync_media_mode_controls=lambda: None,
        )

    def test_series_mode_enables_series_features(self):
        app = self._app()
        gui.App._apply_media_mode(app, "Dizi")
        self.assertEqual(app.content_type_var.get(), "Otomatik")
        self.assertTrue(app.series_memory_var.get())
        self.assertTrue(app.season_canon_var.get())

    def test_film_mode_disables_series_features_without_changing_content(self):
        app = self._app()
        app.content_type_var.set("Anime")
        gui.App._apply_media_mode(app, "Film")
        self.assertEqual(app.content_type_var.get(), "Anime")
        self.assertFalse(app.series_memory_var.get())
        self.assertFalse(app.season_canon_var.get())


class SeasonCanonRunRoutingTest(unittest.TestCase):
    def test_groups_only_completed_multi_episode_seasons(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out1 = root / "one.srt"
            out2 = root / "two.srt"
            out1.write_text("", encoding="utf-8")
            out2.write_text("", encoding="utf-8")
            app = SimpleNamespace(
                _active_snapshot={"src_lang": "English"},
                _active_run_record={"files": {
                    "show.S01E01.srt": {"status": "done", "output_path": str(out1)},
                    "show.S01E02.srt": {"status": "done", "output_path": str(out2)},
                    "show.S01E03.srt": {"status": "error", "output_path": str(out2)},
                }},
                _effective_file_source_language=lambda *_args: "English",
            )
            with patch.object(gui.series_memory, "parse_series_key",
                              side_effect=[("show", 1, 1), ("show", 1, 2)]), \
                    patch.object(gui.series_memory, "series_memory_root",
                                 return_value=root):
                groups = gui.App._season_canon_groups(app)
            self.assertEqual(len(groups), 1)
            self.assertEqual([item[0] for item in next(iter(groups.values()))], [1, 2])

    def test_film_mode_never_starts_season_finalizer(self):
        app = SimpleNamespace(
            _active_snapshot={
                "media_mode": "Film", "series_memory": False,
                "season_canon": False,
            },
            _active_run_record={"files": {"x": {"status": "done"}}},
            _stop_flag=False,
        )
        self.assertFalse(gui.App._should_start_season_canon(app))

    def test_finalizer_is_visible_and_uses_tracked_worker(self):
        calls = []
        app = SimpleNamespace(
            _season_canon_finalizing=False,
            _set_phase=lambda *args: calls.append(("phase", args)),
            _set_status=lambda *args: calls.append(("status", args)),
            _start_worker=lambda target: calls.append(("worker", target)),
        )
        gui.App._start_season_canon_finalizer(app)
        self.assertTrue(app._season_canon_finalizing)
        self.assertIn(
            ("phase", ("Sezon Kanonu", "Sezon genelinde terim ve hitap denetleniyor")),
            calls,
        )
        self.assertTrue(any(kind == "status" and "kapatmayın" in args[0]
                            for kind, args in calls))
        self.assertTrue(any(kind == "worker" for kind, _value in calls))

    def test_close_warns_specifically_during_season_finalizer(self):
        app = SimpleNamespace(
            _is_shutting_down=False,
            _is_running=True,
            _season_canon_finalizing=True,
        )
        with patch.object(gui.messagebox, "askyesno", return_value=False) as ask:
            gui.App._on_close(app)
        title, message = ask.call_args.args
        self.assertEqual(title, "Sezon kanon denetimi sürüyor")
        self.assertIn("dosyalar nihai hazır sayılmaz", message)


    def test_season_audit_is_targeted_and_writes_run_scoped_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "show.S01E01.srt"
            output = root / "out.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nThe Negotiator arrived.\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nArabulucu geldi.\n",
                encoding="utf-8")
            semantic_calls = []
            memory = SimpleNamespace(
                build_hint=lambda: "SERIES CANON",
                get_address_map=lambda: [],
            )
            app = SimpleNamespace(
                _active_snapshot={
                    "input_dir": str(root), "output_dir": str(root / "out"),
                    "tgt_lang": "Turkish", "src_lang": "English",
                    "term_normalize": False,
                },
                _active_run_record={"run_id": "run:42", "reports": []},
                _run_record_lock=threading.Lock(),
                _season_canon_groups=lambda: {
                    (str(root), "show", 1, "en"): [(1, str(source), output)]
                },
                _effective_file_source_language=lambda *_args: "English",
                _get_locked_terms_dict=lambda *_args: {
                    "Negotiator": "Müzakereci"
                },
                _series_mem_for=lambda *_args: (memory, 1, 1),
                _maybe_semantic_reconciliation=lambda *args, **kwargs:
                    semantic_calls.append((args, kwargs)) or 0,
                _log=lambda *_args: None,
            )

            gui.App._run_season_canon_audit(app)

            self.assertEqual(len(semantic_calls), 1)
            kwargs = semantic_calls[0][1]
            self.assertEqual(kwargs["target_coverage"], 0.0)
            self.assertIn("sezon-anlam-mutabakati", str(kwargs["report_path"]))
            self.assertIn("Raporlar", str(kwargs["report_path"]))
            report = root / "out" / "Raporlar" / "sezon_kanon_denetimi_run-42.txt"
            self.assertTrue(report.exists())

    def test_address_lines_are_ignored_without_address_canon(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "show.S01E01.srt"
            output = root / "out.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nI told you.\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nSana söyledim.\n",
                encoding="utf-8")
            semantic = MagicMock()
            memory = SimpleNamespace(
                build_hint=lambda: "CHARACTERS ONLY",
                get_address_map=lambda: [],
            )
            app = SimpleNamespace(
                _active_snapshot={
                    "input_dir": str(root), "output_dir": str(root / "out"),
                    "tgt_lang": "Turkish", "src_lang": "English",
                    "term_normalize": False,
                },
                _active_run_record={"run_id": "run-1", "reports": []},
                _run_record_lock=threading.Lock(),
                _season_canon_groups=lambda: {
                    (str(root), "show", 1, "en"): [(1, str(source), output)]
                },
                _effective_file_source_language=lambda *_args: "English",
                _get_locked_terms_dict=lambda *_args: {},
                _series_mem_for=lambda *_args: (memory, 1, 1),
                _maybe_semantic_reconciliation=semantic,
                _log=lambda *_args: None,
            )

            gui.App._run_season_canon_audit(app)

            semantic.assert_not_called()


if __name__ == "__main__":
    unittest.main()
