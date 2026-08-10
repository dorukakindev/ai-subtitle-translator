import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class ManualPostprocessOwnershipTests(unittest.TestCase):
    def test_changed_output_is_not_owned_by_old_postprocess_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "film.tr.srt"
            output.write_text("old final", encoding="utf-8")
            backup = gui._create_postprocess_backup(output)

            self.assertEqual(gui._postprocess_write_guard_reason(output, backup), "")
            output.write_text("user edited final", encoding="utf-8")

            self.assertEqual(
                gui._postprocess_write_guard_reason(output, backup),
                "output_changed")

    def test_known_source_fingerprint_blocks_manual_postprocess_after_source_drift(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "film.en.srt"
            output = root / "film.tr.srt"
            source.write_text("original source", encoding="utf-8")
            output.write_text("translated final", encoding="utf-8")
            reports = root / "Raporlar"

            self.assertTrue(gui._write_output_source_fingerprint(
                reports, output, gui._file_content_sha256(source)))
            self.assertFalse(gui._postprocess_source_drifted(output, source))

            source.write_text("new source after delivery", encoding="utf-8")

            self.assertTrue(gui._postprocess_source_drifted(output, source))

    def test_legacy_output_without_fingerprint_remains_eligible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "film.en.srt"
            output = root / "film.tr.srt"
            source.write_text("source", encoding="utf-8")
            output.write_text("translated", encoding="utf-8")

            self.assertFalse(gui._postprocess_source_drifted(output, source))

    def test_hybrid_stage_partial_keeps_recovery_fingerprint_and_old_partial(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "film.en.srt"
            output = root / "film.tr.srt"
            stage = root / ".film.tr.srt.batch-stage.srt"
            source.write_text("source", encoding="utf-8")
            stage.write_text("new partial", encoding="utf-8")
            previous = gui._partial_output_path(output)
            previous.parent.mkdir(parents=True, exist_ok=True)
            previous.write_text("older partial", encoding="utf-8")
            reports = root / "Raporlar"

            partial = gui._move_stage_to_partial(
                stage, output, reports, gui._file_content_sha256(source))

            self.assertEqual(partial.read_text(encoding="utf-8"), "new partial")
            self.assertTrue(gui._partial_output_recovery_allowed(
                reports, partial, source))
            self.assertEqual(
                next(partial.parent.glob("*.superseded.bak.srt")).read_text(
                    encoding="utf-8"),
                "older partial")


if __name__ == "__main__":
    unittest.main()
