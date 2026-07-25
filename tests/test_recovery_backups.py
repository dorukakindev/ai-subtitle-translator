import inspect
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import subtitle_translator_gui as gui


class PostProcessBackupTest(unittest.TestCase):
    def test_backup_preserves_exact_bytes_and_avoids_collision(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "episode.srt"
            original = b"\xef\xbb\xbf1\r\n00:00:01,000 --> 00:00:02,000\r\nHello\r\n"
            src.write_bytes(original)

            first = gui._create_postprocess_backup(src)
            second = gui._create_postprocess_backup(src)

            self.assertEqual(first.name, "episode.postprocess.bak.srt")
            self.assertEqual(second.name, "episode.postprocess.2.bak.srt")
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(second.read_bytes(), original)
            self.assertEqual(src.read_bytes(), original)

    def test_backup_failure_is_reported_to_caller(self):
        with TemporaryDirectory() as td:
            src = Path(td) / "episode.srt"
            src.write_text("original", encoding="utf-8")
            with patch.object(
                    gui, "atomic_write_bytes", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    gui._create_postprocess_backup(src)
            self.assertEqual(src.read_text(encoding="utf-8"), "original")

    def test_postprocess_creates_backup_before_final_write(self):
        source = inspect.getsource(gui.App._run_post_process)
        self.assertLess(
            source.index("_create_postprocess_backup(fp)"),
            source.index("write_srt(fp, blocks)"),
        )
        self.assertIn("orijinal dosyaya dokunulmadı", source)


class ResumeRawBackupPlacementTest(unittest.TestCase):
    def test_resume_writes_raw_backup_before_quality_passes(self):
        source = inspect.getsource(gui.App._wait_batch_hybrid)
        capture = source.index("_raw_backup_blocks = list(pp)")
        early_backup = source.index(
            "self._save_raw_backup(\n                                output_path",
            capture,
        )
        critic = source.index("ht.critic_pass_with_helper(", capture)
        self.assertLess(capture, early_backup)
        self.assertLess(early_backup, critic)


class HybridPhaseTwoPauseTest(unittest.TestCase):
    def test_phase_two_waits_at_every_file_boundary_via_finally(self):
        source = inspect.getsource(gui.App._run_hybrid)
        phase_two = source.index("FAZ 2")
        wait = source.index(
            "self._wait_between_files(si, n_sub, fname)", phase_two)
        finally_pos = source.rfind("finally:", phase_two, wait)
        self.assertGreater(finally_pos, phase_two)
        self.assertGreater(wait, finally_pos)


if __name__ == "__main__":
    unittest.main()
