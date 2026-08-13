import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class DeliveryReportOnlyPolicyTest(unittest.TestCase):
    def _app(self, enabled):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {"quality_report_only": enabled}
        return app

    def test_report_only_keeps_failed_final_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "episode.srt"
            output.write_text("broken", encoding="utf-8")

            quarantined = gui.App._maybe_quarantine_incomplete_final(
                self._app(True), output)

            self.assertIsNone(quarantined)
            self.assertTrue(output.exists())
            self.assertEqual(output.read_text(encoding="utf-8"), "broken")

    def test_strict_mode_still_quarantines_failed_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "episode.srt"
            output.write_text("broken", encoding="utf-8")

            quarantined = gui.App._maybe_quarantine_incomplete_final(
                self._app(False), output)

            self.assertIsNotNone(quarantined)
            self.assertFalse(output.exists())
            self.assertTrue(Path(quarantined).exists())
            self.assertIn("Kurtarma", str(quarantined))

    def test_review_outcome_is_not_counted_as_completed(self):
        rows = [{"source_path": "film.srt", "run_status": "review"}]

        completed, failed = gui._reconcile_delivery_outcomes(
            rows, ["film.srt"], [])

        self.assertEqual(completed, [])
        self.assertEqual(failed, ["film.srt"])

    def test_delivery_audit_records_source_and_target_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            output = Path(tmp) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello.\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\nGoodbye.\n",
                encoding="utf-8",
            )
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nMerhaba.\n",
                encoding="utf-8",
            )

            audit = gui._subtitle_delivery_audit(
                str(source), str(output), "Turkish", "English")

            missing = [
                item for item in audit["review_details"]
                if item["reason"] == "missing_dialogue"
            ]
            self.assertEqual(len(missing), 1)
            self.assertEqual(missing[0]["source_id"], "2")
            self.assertEqual(missing[0]["source"], "Goodbye.")
            self.assertEqual(missing[0]["target"], "")

    def test_review_report_explains_output_is_retained(self):
        row = gui._delivery_review_report_row(
            "film.srt", "film.tr.srt", {
                "status": "review",
                "missing_dialogue_ids": ["7"],
                "dialogue_output_cues": 10,
            })

        report = gui.build_quality_report_text(
            [row], "gpt-5.4", "Turkish", "sync", 0)

        self.assertEqual(row["run_status"], "review")
        self.assertIn("İNCELEME GEREKLİ", report)
        self.assertIn("çıktı yerinde bırakıldı", report)


if __name__ == "__main__":
    unittest.main()
