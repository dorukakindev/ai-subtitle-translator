import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


class MissingRepairToggleTest(unittest.TestCase):
    def test_disabled_repair_uses_reporting_phase_name(self):
        self.assertEqual(
            gui._missing_repair_phase(False), "Eksik Cue Raporlama")
        self.assertEqual(
            gui._missing_repair_phase(False, partial_only=True),
            "Eksik Cue Raporlama")
        self.assertEqual(
            gui._missing_repair_phase(True), "Eksik Çeviri Onarımı")
        self.assertEqual(
            gui._missing_repair_phase(True, partial_only=True),
            "Yalnız Eksik Cue Onarımı")

    def test_disabled_setting_blocks_all_chunk_repair_api_paths(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {"repair_missing": False}
        app._stop_flag = False
        logs = []
        app._log = lambda message, level="info": logs.append((level, message))
        app._json_repair_pass = MagicMock(
            side_effect=AssertionError("JSON repair must stay disabled"))
        app._resend_missing_blocks = MagicMock(
            side_effect=AssertionError("cue repair must stay disabled"))
        request = {
            "custom_id": "chunk_1",
            "body": {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": "Translate."},
                    {"role": "user", "content": json.dumps({"tr": [
                        {"i": 1, "t": "Hello."},
                        {"i": 2, "t": "Goodbye."},
                    ]})},
                ],
            },
        }
        raw_map = {"chunk_1": json.dumps([
            {"i": 1, "t": "Merhaba."},
        ], ensure_ascii=False)}

        with unittest.mock.patch.object(gui, "_safe_chat_create") as chat:
            unresolved = gui.App._retry_hata(
                app, object(), raw_map, [request], max_rounds=3)

        self.assertEqual(unresolved, {"chunk_1"})
        app._json_repair_pass.assert_not_called()
        app._resend_missing_blocks.assert_not_called()
        chat.assert_not_called()
        rendered = "\n".join(message for _level, message in logs)
        self.assertIn("Eksik Cue API Onarımı kapalı", rendered)
        self.assertIn("2", rendered)

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

    def test_source_credit_is_removed_instead_of_reported_missing(self):
        for credit in (
                "Subtitling: www.pluridioma.pt",
                "Plain English translation by Aleksandar@Radovanovic.com"):
            with self.subTest(credit=credit):
                client = MagicMock()
                reviews = []
                blocks, repaired = gui._repair_untranslated_sync(
                    [("848", "00:01:00,000 --> 00:01:01,000", "[HATA]")],
                    {"848": credit},
                    client,
                    "English",
                    "Turkish",
                    source_cues=[(
                        "848", "00:01:00,000 --> 00:01:01,000", credit)],
                    advisory_reviews_out=reviews,
                    enabled=False,
                )

                self.assertEqual(blocks, [])
                self.assertEqual(repaired, 0)
                self.assertEqual(reviews, [])
                client.chat.completions.create.assert_not_called()

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
