import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class ContentConfidenceTest(unittest.TestCase):
    def test_content_detection_detail_clamps_confidence(self):
        self.assertEqual(
            gui._content_detection_detail(
                {"category": "Belgesel", "confidence": 1.7}),
            {"category": "Belgesel", "confidence": 1.0},
        )
        self.assertEqual(
            gui._content_detection_detail("Film"),
            {"category": "Film", "confidence": None},
        )

    def test_detector_can_return_category_and_confidence(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"category": "Belgesel", "confidence": 0.92}'))],
            usage=None,
        )
        with patch("hybrid_translate._safe_chat_create", return_value=response):
            detail = gui.detect_content_type_with_ai(
                None,
                [("1", "00:00:01,000", "A documentary sample.")],
                "test",
                return_details=True,
            )
        self.assertEqual(detail["category"], "Belgesel")
        self.assertEqual(detail["confidence"], 0.92)


class WorkflowProfilesTest(unittest.TestCase):
    def test_maximum_profile_keeps_semantic_final_pass_enabled(self):
        profile = gui.WORKFLOW_PROFILES["Maksimum kalite"]
        self.assertTrue(profile["hybrid_var"])
        self.assertTrue(profile["semantic_reconcile_var"])
        self.assertTrue(profile["backtrans_var"])
        self.assertFalse(profile["qc_var"])

    def test_fast_profile_disables_expensive_quality_passes(self):
        profile = gui.WORKFLOW_PROFILES["Hızlı kontrol"]
        for key in (
            "critic_var", "polish_var", "native_var",
            "backtrans_var", "semantic_reconcile_var",
        ):
            self.assertFalse(profile[key])


class SubtitlePreflightTest(unittest.TestCase):
    def test_valid_srt_has_no_integrity_issue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nHello.\n",
                encoding="utf-8",
            )
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))
            self.assertEqual(issues, [])

    def test_empty_and_duplicate_files_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "empty.srt"
            source.write_bytes(b"")
            issues = gui.scan_subtitle_preflight(
                [str(source), str(source)], str(root), str(root / "out"))
            codes = {issue["code"] for issue in issues}
            self.assertIn("read_error", codes)
            self.assertIn("duplicate", codes)

    def test_binary_control_data_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.srt"
            source.write_bytes(
                b"1\n00:00:01,000 --> 00:00:03,000\nHello\x00world\n")
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))
            self.assertIn("encoding", {issue["code"] for issue in issues})

    def test_filename_language_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "film.ita.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nCiao.\n",
                encoding="utf-8",
            )
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"),
                expected_source_language="English",
            )
            self.assertIn("wrong_language", {issue["code"] for issue in issues})


class AutomaticRetryTest(unittest.TestCase):
    def test_only_failed_files_are_queued_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            failed = Path(tmp) / "failed.srt"
            done = Path(tmp) / "done.srt"
            failed.write_text("x", encoding="utf-8")
            done.write_text("x", encoding="utf-8")
            scheduled = []
            stub = SimpleNamespace(
                _active_snapshot={"auto_retry_files": True},
                _auto_retry_attempts={},
                _selected_files=[],
                _input_folder_explicitly_selected=True,
                _language_preflight_done=False,
                _content_type_preflight_done=False,
                _file_integrity_preflight_done=True,
                _auto_retry_continuation=False,
                _log=lambda *args: None,
                after=lambda delay, callback: scheduled.append((delay, callback)),
                _start=lambda: None,
            )
            record = {
                "status": "kısmen tamamlandı",
                "files": {
                    str(done): {"status": "done"},
                    str(failed): {"status": "error"},
                },
            }
            self.assertTrue(gui.App._schedule_failed_file_retry(stub, record))
            self.assertEqual(stub._selected_files, [str(failed)])
            self.assertEqual(stub._auto_retry_attempts[str(failed)], 1)
            self.assertEqual(len(scheduled), 1)


if __name__ == "__main__":
    unittest.main()
