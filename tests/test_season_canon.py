import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
