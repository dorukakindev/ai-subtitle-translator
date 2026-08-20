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

    def test_merged_delivery_span_uses_combined_source_context(self):
        source = [
            ("10", "00:00:01,000 --> 00:00:02,000", "I do"),
            ("11", "00:00:02,100 --> 00:00:03,000", "not know."),
        ]
        output = [
            ("1", "00:00:01,000 --> 00:00:03,000", "Bilmiyorum."),
        ]

        aligned, unmapped = gui._align_delivery_blocks_to_source(source, output)
        source_map = gui._source_map_for_aligned_delivery(source, aligned)

        self.assertEqual(unmapped, [])
        self.assertEqual(aligned[0][0], "10|11")
        self.assertEqual(source_map["10|11"], "I do not know.")

    def test_broad_output_across_scene_gap_is_not_treated_as_merge(self):
        source = [
            ("10", "00:00:01,000 --> 00:00:02,000", "First."),
            ("11", "00:00:10,000 --> 00:00:11,000", "Second."),
        ]
        output = [
            ("1", "00:00:01,000 --> 00:00:11,000", "Only first."),
        ]

        aligned, unmapped = gui._align_delivery_blocks_to_source(source, output)

        self.assertEqual(aligned, [])
        self.assertEqual(unmapped, ["1"])

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

    def test_series_mode_enables_memory_without_costly_season_canon(self):
        app = self._app()
        gui.App._apply_media_mode(app, "Dizi")
        self.assertEqual(app.content_type_var.get(), "Otomatik")
        self.assertTrue(app.series_memory_var.get())
        self.assertFalse(app.season_canon_var.get())

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

    def test_finalizer_orchestration_failure_marks_unreviewed_episode_error(self):
        statuses = []
        source = "show.S01E01.srt"
        record = {"files": {
            source: {"status": "done", "output_path": "out.srt"},
        }}

        def record_status(path, phase, status):
            statuses.append((path, phase, status))
            record["files"][path]["status"] = status

        app = SimpleNamespace(
            _season_canon_finalizing=False,
            _active_run_record=record,
            _run_record_lock=threading.RLock(),
            _season_canon_groups=lambda: {
                ("root", "show", 1, "en"): [(1, source, Path("out.srt"))],
            },
            _run_season_canon_audit=MagicMock(
                side_effect=RuntimeError("orchestration failed")),
            _record_file_status=record_status,
            _log=MagicMock(),
            _set_phase=lambda *_args: None,
            _set_status=lambda *_args: None,
            _set_running=lambda *_args: None,
            _start_worker=lambda target: target(),
        )

        gui.App._start_season_canon_finalizer(app)

        self.assertEqual(statuses, [(
            source, "Sezon kanon denetimi tamamlanamadı", "error")])
        self.assertEqual(record["files"][source]["status"], "error")
        self.assertTrue(any(call.args[1] == "err" for call in app._log.call_args_list))

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
                build_hint=lambda **_kwargs: "SERIES CANON",
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
                _maybe_semantic_reconciliation=lambda *args, **kwargs: (
                    semantic_calls.append((args, kwargs)),
                    kwargs["status_out"].update(status="completed"),
                    0,
                )[-1],
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

    def test_failed_episode_is_not_left_marked_done(self):
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
            statuses = []
            record = {
                "run_id": "run-failed", "reports": [], "errors": 0,
                "files": {str(source): {
                    "status": "done", "output_path": str(output),
                }},
            }
            def record_status(path, phase, status):
                statuses.append((path, phase, status))
                record["files"][str(path)]["phase"] = phase
                record["files"][str(path)]["status"] = status

            app = SimpleNamespace(
                _active_snapshot={
                    "input_dir": str(root), "output_dir": str(root / "out"),
                    "tgt_lang": "Turkish", "src_lang": "English",
                    "term_normalize": False,
                },
                _active_run_record=record,
                _run_record_lock=threading.RLock(),
                _season_canon_groups=lambda: {
                    (str(root), "show", 1, "en"): [(1, str(source), output)]
                },
                _effective_file_source_language=lambda *_args: "English",
                _get_locked_terms_dict=lambda *_args: {
                    "Negotiator": "Müzakereci"
                },
                _series_mem_for=lambda *_args: (
                    SimpleNamespace(build_hint=lambda: "SERIES CANON",
                                    get_address_map=lambda: []), 1, 1),
                _maybe_semantic_reconciliation=MagicMock(
                    side_effect=RuntimeError("provider unavailable")),
                _record_file_status=record_status,
                _log=MagicMock(),
            )

            gui.App._run_season_canon_audit(app)

            self.assertEqual(statuses, [(
                str(source), "Sezon kanon denetimi hatası", "error")])
            self.assertEqual(record["files"][str(source)]["status"], "error")
            self.assertEqual(
                record["season_canon_errors"][0]["source_path"], str(source))
            self.assertTrue(any(call.args[1] == "err" for call in app._log.call_args_list))

    def test_semantic_reconcile_can_propagate_errors_for_required_pass(self):
        app = SimpleNamespace(
            _active_snapshot={"src_lang": "English", "tgt_lang": "Turkish"},
            src_var=SimpleNamespace(get=lambda: "English"),
            tgt_var=SimpleNamespace(get=lambda: "Turkish"),
            _stop_flag=False,
            _helper_request_canceller=None,
            _helper_api_key=lambda _role: "key",
            _helper_api_base_url=lambda _role: "https://api.example/v1",
            _helper_api_model=lambda _role: "gpt-5.4-mini",
            _get_locked_terms_dict=lambda *_args: {},
            _run_scene_gap=lambda: 3.0,
            _token_callback_for_model=lambda _model: None,
            _log=MagicMock(),
        )
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "Arabulucu geldi.")]
        with patch("hybrid_translate.semantic_reconciliation_pass",
                   side_effect=RuntimeError("provider unavailable")), \
                self.assertRaisesRegex(RuntimeError, "provider unavailable"):
            gui.App._maybe_semantic_reconciliation(
                app, "out.srt", {"1": "The Negotiator arrived."}, blocks,
                source_path="show.S01E01.srt", force=True,
                raise_errors=True)


if __name__ == "__main__":
    unittest.main()
