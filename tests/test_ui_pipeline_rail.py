import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


class PipelineStageMappingTest(unittest.TestCase):
    def test_visible_phases_map_to_user_facing_stages(self):
        cases = {
            "İçerik Türü": 0,
            "Yardımcı Analiz": 0,
            "Çeviri": 1,
            "Eksik Çeviri Onarımı": 1,
            "Critic Pass": 2,
            "Native Okuyucu": 2,
            "Nihai Anlam Mutabakatı": 2,
            "Terim Normalizasyonu": 2,
            "Yazıyor": 3,
            "Tamamlandı": 3,
            "Kısmen tamamlandı": 3,
            "Hata": 3,
        }
        for phase, expected in cases.items():
            with self.subTest(phase=phase):
                self.assertEqual(gui._pipeline_stage_index(phase), expected)

    def test_ready_detail_replaces_stale_pass_text(self):
        self.assertEqual(
            gui._phase_detail_text("Hazır", ""),
            "Dosya veya klasör ekleyerek başlayın.")
        self.assertEqual(
            gui._phase_detail_text("Native Okuyucu", "Paket 2/6"),
            "Paket 2/6")
        self.assertEqual(gui._phase_detail_text("Critic Pass", ""), "")


class JobBoardSummaryTest(unittest.TestCase):
    def test_summary_groups_finished_skipped_and_errors(self):
        rows = {
            "a": {"state": "waiting"},
            "b": {"state": "running"},
            "c": {"state": "done"},
            "d": {"state": "skip"},
            "e": {"state": "error"},
        }

        self.assertEqual(
            gui._job_board_counts(rows),
            {"waiting": 1, "running": 1, "done": 1,
             "skip": 1, "error": 1})
        self.assertEqual(gui._job_board_summary_text(rows),
                         "○ 1   ● 1   ✓ 2   ! 1")

    def test_file_progress_updates_numeric_badge_and_active_surface(self):
        filepath = "episode.srt"
        row = {
            "dot": MagicMock(), "phase": MagicMock(), "pb": MagicMock(),
            "frame": MagicMock(), "pct": MagicMock(),
            "remove": MagicMock(), "state": "waiting",
            "value": 0.0, "target": 0.0, "color": gui.FG2,
        }
        app = SimpleNamespace(
            _job_rows={filepath: row}, _PHASE_COLORS=gui.App._PHASE_COLORS,
            _is_running=False, _is_shutting_down=False,
            _refresh_job_board_title=lambda: None,
        )

        gui.App._update_file_progress(
            app, filepath, "Native Okuyucu", 64.6, "running")

        self.assertEqual(row["state"], "running")
        self.assertEqual(row["pct"].configure.call_args.kwargs["text"], "65%")
        self.assertIn("fg_color", row["frame"].configure.call_args.kwargs)


class PipelineRailStateTest(unittest.TestCase):
    @staticmethod
    def _item():
        return {
            "frame": MagicMock(),
            "number": MagicMock(),
            "label": MagicMock(),
        }

    def test_quality_stage_marks_previous_steps_complete(self):
        items = [self._item() for _ in gui.PIPELINE_STAGE_LABELS]
        app = SimpleNamespace(_pipeline_stage_widgets=items)

        gui.App._update_pipeline_rail(app, "Critic Pass", gui.INFO_BLUE)

        self.assertEqual(items[0]["number"].configure.call_args.kwargs["text"], "✓")
        self.assertEqual(items[1]["number"].configure.call_args.kwargs["text"], "✓")
        self.assertEqual(items[2]["number"].configure.call_args.kwargs["text"], "03")
        self.assertEqual(items[3]["number"].configure.call_args.kwargs["text"], "04")

    def test_completed_phase_marks_entire_rail_complete(self):
        items = [self._item() for _ in gui.PIPELINE_STAGE_LABELS]
        app = SimpleNamespace(_pipeline_stage_widgets=items)

        gui.App._update_pipeline_rail(app, "Tamamlandı", gui.GREEN)

        self.assertEqual(
            [item["number"].configure.call_args.kwargs["text"] for item in items],
            ["✓", "✓", "✓", "✓"])

    def test_phase_setter_updates_detail_and_rail(self):
        source = inspect.getsource(gui.App._set_phase)
        self.assertIn("progress_lbl.configure(text=visible_detail)", source)
        self.assertIn("App._update_pipeline_rail(self, phase, color)", source)

    def test_progress_percentage_badge_tracks_target(self):
        pct_label = MagicMock()
        app = SimpleNamespace(
            _progress_pct_lbl=pct_label,
            _motion_phase_color=gui.INFO_BLUE,
            _motion_progress_target=0.0,
            _motion_progress_value=0.0,
            _is_running=False,
            _is_shutting_down=False,
            progress=MagicMock(),
            light_animations_var=SimpleNamespace(get=lambda: False),
        )

        gui.App._set_progress(app, 64.6)

        pct_label.configure.assert_called_once_with(
            text="65%", text_color=gui.INFO_BLUE)


if __name__ == "__main__":
    unittest.main()
