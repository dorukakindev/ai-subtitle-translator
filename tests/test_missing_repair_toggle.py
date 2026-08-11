import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


class MissingRepairToggleTest(unittest.TestCase):
    def test_disabled_repair_logs_every_cue_without_api_call(self):
        client = MagicMock()
        logs = []
        reviews = []

        blocks, repaired = gui._repair_untranslated_sync(
            [("17", "00:00:01,000 --> 00:00:02,000", "[HATA]")],
            {"17": "Translate this line."},
            client,
            "English",
            "Turkish",
            log_fn=lambda message, level="info": logs.append((level, message)),
            advisory_reviews_out=reviews,
            enabled=False,
        )

        self.assertEqual(repaired, 0)
        self.assertEqual(blocks[0][2], "[HATA]")
        client.chat.completions.create.assert_not_called()
        self.assertEqual(reviews[0]["id"], "17")
        self.assertEqual(reviews[0]["reason"], "automatic_repair_disabled")
        rendered = "\n".join(message for _level, message in logs)
        self.assertIn("#17", rendered)
        self.assertIn("Translate this line.", rendered)
        self.assertIn("API'ye gönderilmedi", rendered)

    def test_missing_only_failure_is_not_automatically_restarted(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {
            "auto_retry_files": True,
            "repair_missing": False,
        }
        app._auto_retry_blocked_by_permanent_provider = False
        app._auto_retry_attempts = {}
        app._selected_files = []
        logs = []
        app._log = lambda message, level="info": logs.append((level, message))

        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "source.srt")
            source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            record = {
                "status": "hata",
                "settings": {"mode": "sync"},
                "files": {
                    str(source): {"status": "error", "phase": "Eksik çeviri: 1"},
                },
            }
            scheduled = gui.App._schedule_failed_file_retry(app, record)

        self.assertFalse(scheduled)
        self.assertEqual(app._selected_files, [])
        self.assertTrue(any("otomatik yeniden başlatılmadı" in msg for _level, msg in logs))

    def test_final_error_phase_uses_quality_row_to_skip_missing_retry(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {
            "auto_retry_files": True,
            "repair_missing": False,
        }
        app._auto_retry_blocked_by_permanent_provider = False
        app._auto_retry_attempts = {}
        app._selected_files = []
        app._log = lambda *_args, **_kwargs: None

        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "source.srt")
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                encoding="utf-8",
            )
            record = {
                "status": "başarısız",
                "settings": {"mode": "sync"},
                "files": {
                    str(source): {
                        "status": "error",
                        "phase": "Hata",
                        "output_path": str(Path(root, "source.partial.srt")),
                    },
                },
                "_quality_report_rows": [{
                    "source_path": str(source),
                    "repair_missing_after": 1,
                    "delivery_audit": {"unresolved_markers": 1},
                }],
            }

            scheduled = gui.App._schedule_failed_file_retry(app, record)

        self.assertFalse(scheduled)
        self.assertEqual(app._selected_files, [])
        self.assertEqual(app._auto_retry_attempts, {})

    def test_default_profiles_keep_expensive_repair_off(self):
        self.assertFalse(gui.QUALITY_PROFILE_DEFAULTS["repair_missing"])
        for profile in gui.WORKFLOW_PROFILES.values():
            self.assertFalse(profile["repair_missing_var"])
        snapshot_source = inspect.getsource(gui.App._take_run_snapshot)
        save_source = inspect.getsource(gui.App._save_settings)
        load_source = inspect.getsource(gui.App._load_settings)
        self.assertIn('"repair_missing"', snapshot_source)
        self.assertIn('"repair_missing"', save_source)
        self.assertIn('"repair_missing"', load_source)

    def test_quality_report_says_off_even_if_a_repair_trace_exists(self):
        lines = gui._quality_feature_audit(
            {
                "status": "done",
                "pass_trace": {"Repair": 0},
                "pass_status": {},
            },
            {"repair_missing": False},
        )

        self.assertIn("Eksik Cue API Onarımı: kapalı", lines)
        self.assertNotIn("Eksik Cue API Onarımı: çalıştı, 0 cue değiştirdi", lines)


if __name__ == "__main__":
    unittest.main()
