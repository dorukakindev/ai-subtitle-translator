import tempfile
import threading
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
    def test_maximum_profile_uses_deep_analysis_without_expensive_passes(self):
        profile = gui.WORKFLOW_PROFILES["Maksimum kalite"]
        self.assertTrue(profile["hybrid_var"])
        self.assertEqual(profile["analysis_depth_var"], "Maksimum")
        self.assertTrue(profile["critic_var"])
        self.assertTrue(profile["term_normalize_var"])
        self.assertTrue(profile["chain_ctx_var"])
        for key in (
            "polish_var", "native_var", "backtrans_var",
            "semantic_reconcile_var", "review_pass_var", "qc_var",
            "season_canon_var",
        ):
            self.assertFalse(profile[key])

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

    def test_same_movie_year_across_releases_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "Wise.Blood.1979.release-a.eng.srt"
            second = root / "wise_blood_(1979)_release-b.eng.srt"
            first.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nFirst.\n",
                encoding="utf-8",
            )
            second.write_text(
                "1\n00:00:02,000 --> 00:00:04,000\nSecond.\n",
                encoding="utf-8",
            )

            issues = gui.scan_subtitle_preflight(
                [str(first), str(second)], str(root), str(root / "out"))

            duplicates = [
                item for item in issues
                if item["code"] == "duplicate_title_year"
            ]
            self.assertEqual({item["path"] for item in duplicates}, {
                str(first), str(second)})
            self.assertTrue(all(item["severity"] == "warning" for item in duplicates))

    def test_same_cue_content_across_different_paths_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.srt"
            second = root / "second.srt"
            subtitle = "1\n00:00:01,000 --> 00:00:03,000\nSame source.\n"
            first.write_text(subtitle, encoding="utf-8")
            second.write_text(subtitle, encoding="utf-8-sig")

            issues = gui.scan_subtitle_preflight(
                [str(first), str(second)], str(root), str(root / "out"))

            duplicates = [
                item for item in issues
                if item["code"] == "duplicate_content"
            ]
            self.assertEqual({item["path"] for item in duplicates}, {
                str(first), str(second)})

    def test_series_episodes_are_not_grouped_as_duplicate_movies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "Hamiltons.Pharmacopeia.2016.S03E01.eng.srt"
            second = root / "Hamiltons.Pharmacopeia.2016.S03E02.eng.srt"
            first.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nEpisode one.\n",
                encoding="utf-8",
            )
            second.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nEpisode two.\n",
                encoding="utf-8",
            )

            issues = gui.scan_subtitle_preflight(
                [str(first), str(second)], str(root), str(root / "out"))

            self.assertNotIn(
                "duplicate_title_year", {item["code"] for item in issues})

    def test_binary_control_data_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.srt"
            source.write_bytes(
                b"1\n00:00:01,000 --> 00:00:03,000\nHello\x00world\n")
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))
            self.assertIn("encoding", {issue["code"] for issue in issues})

    def test_opensubtitles_vip_placeholder_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.srt"
            source.write_text(
                "1\n00:00:00,001 --> 04:00:00,001\n"
                "Altyazıları almak için OpenSubtitles.org\n"
                "VIP üye olun -> osdb.link/vip\n",
                encoding="utf-8",
            )

            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))

            placeholder = [
                item for item in issues
                if item["code"] == "download_placeholder"
            ]
            self.assertEqual(len(placeholder), 1)
            self.assertEqual(placeholder[0]["severity"], "error")

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

    def test_numeric_episode_name_in_season_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Hamiltons.Pharmacopeia.2016.S02.REPACK"
            root.mkdir()
            source = root / "3.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nHello.\n",
                encoding="utf-8",
            )
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))

            upload = [issue for issue in issues if issue["code"] == "upload_name"]
            self.assertEqual(len(upload), 1)
            self.assertIn("S02E03", upload[0]["message"])

    def test_dos_short_episode_name_in_season_folder_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Hamiltons.Pharmacopeia.2016.S02.REPACK"
            root.mkdir()
            source = root / "HA42BA~1.vtt"
            source.write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello.\n",
                encoding="utf-8",
            )
            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(root / "out"))

            upload = [issue for issue in issues if issue["code"] == "upload_name"]
            self.assertEqual(len(upload), 1)
            self.assertIn("DOS 8.3", upload[0]["message"])

    def test_existing_resolved_output_is_reported_with_target_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "out"
            source = root / "film.eng.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nHello.\n",
                encoding="utf-8",
            )
            target = gui._resolve_output_path(
                str(root), str(output_dir), str(source))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "1\n00:00:01,000 --> 00:00:03,000\nMerhaba.\n",
                encoding="utf-8",
            )

            issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(output_dir))

            existing = [item for item in issues if item["code"] == "existing_output"]
            self.assertEqual(len(existing), 1)
            self.assertEqual(existing[0]["path"], str(source))
            self.assertEqual(existing[0]["output"], str(target))
            self.assertEqual(existing[0]["severity"], "warning")

            resumed_issues = gui.scan_subtitle_preflight(
                [str(source)], str(root), str(output_dir),
                ignore_existing_outputs=[str(source)],
            )
            self.assertNotIn(
                "existing_output", {item["code"] for item in resumed_issues})

    def test_existing_output_choices_remove_only_selected_sources(self):
        files = [
            str(Path("season-a") / "episode-1.srt"),
            str(Path("season-a") / "episode-2.srt"),
            str(Path("season-b") / "episode-1.srt"),
        ]
        choices = {
            files[0]: "remove",
            files[2]: "retranslate",
        }

        kept, removed = gui.resolve_existing_output_choices(files, choices)

        self.assertEqual(removed, [files[0]])
        self.assertEqual(kept, [files[1], files[2]])

    def test_multi_folder_scan_matches_only_the_existing_episode_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "translated"
            season_a = root / "Series A"
            season_b = root / "Series B"
            season_a.mkdir()
            season_b.mkdir()
            first = season_a / "Episode 01.srt"
            second = season_b / "Episode 01.srt"
            subtitle = "1\n00:00:01,000 --> 00:00:03,000\nHello.\n"
            first.write_text(subtitle, encoding="utf-8")
            second.write_text(subtitle, encoding="utf-8")
            target = gui._resolve_output_path(
                "", str(output_dir), str(first),
                selected_roots=(str(season_a), str(season_b)),
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(subtitle.replace("Hello", "Merhaba"), encoding="utf-8")

            issues = gui.scan_subtitle_preflight(
                [str(first), str(second)], "", str(output_dir),
                selected_roots=(str(season_a), str(season_b)),
            )

            existing_paths = {
                item["path"] for item in issues if item["code"] == "existing_output"
            }
            self.assertEqual(existing_paths, {str(first)})


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
                _resume_snapshot_override=None,
                _log=lambda *args: None,
                after=lambda delay, callback: scheduled.append((delay, callback)),
                _start=lambda: None,
            )
            record = {
                "run_id": "run-original",
                "status": "kısmen tamamlandı",
                "settings": {"auto_retry_files": True},
                "files": {
                    str(done): {"status": "done"},
                    str(failed): {"status": "error"},
                },
            }
            self.assertTrue(gui.App._schedule_failed_file_retry(stub, record))
            self.assertEqual(stub._selected_files, [str(failed)])
            self.assertEqual(stub._auto_retry_attempts[str(failed)], 1)
            self.assertEqual(len(scheduled), 1)
            self.assertTrue(stub._resume_snapshot_override["crash_resume"])
            self.assertTrue(
                stub._resume_snapshot_override["auto_retry_repair_only"])
            self.assertEqual(
                stub._resume_snapshot_override["resume_origin_run_id"],
                "run-original")

    def test_source_or_output_changed_files_are_not_auto_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_changed = Path(tmp) / "source.srt"
            output_changed = Path(tmp) / "output.srt"
            source_changed.write_text("x", encoding="utf-8")
            output_changed.write_text("x", encoding="utf-8")
            scheduled = []
            stub = SimpleNamespace(
                _active_snapshot={"auto_retry_files": True},
                _auto_retry_attempts={}, _selected_files=[],
                _log=lambda *args: None,
                after=lambda *args: scheduled.append(args),
            )
            record = {
                "run_id": "run-original", "status": "başarısız",
                "settings": {"auto_retry_files": True},
                "files": {
                    str(source_changed): {
                        "status": "error", "phase": "Kaynak değişti"},
                    str(output_changed): {
                        "status": "error", "phase": "Hedef değişti"},
                },
            }

            self.assertFalse(
                gui.App._schedule_failed_file_retry(stub, record))
            self.assertEqual(stub._selected_files, [])
            self.assertEqual(scheduled, [])

    def test_batch_failure_is_never_resubmitted_as_automatic_file_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            source.write_text("x", encoding="utf-8")
            scheduled = []
            stub = SimpleNamespace(
                _active_snapshot={"auto_retry_files": True},
                _auto_retry_attempts={}, _selected_files=[],
                _log=lambda *args: None,
                after=lambda *args: scheduled.append(args),
            )
            record = {
                "run_id": "batch-run", "status": "başarısız",
                "settings": {"auto_retry_files": True, "mode": "batch"},
                "files": {str(source): {
                    "status": "error", "phase": "Faz-2 hatası"}},
            }

            self.assertFalse(
                gui.App._schedule_failed_file_retry(stub, record))
            self.assertEqual(scheduled, [])

    def test_permanent_provider_failure_blocks_whole_file_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            source.write_text("x", encoding="utf-8")
            scheduled = []
            stub = SimpleNamespace(
                _active_snapshot={"auto_retry_files": True},
                _auto_retry_attempts={}, _selected_files=[],
                _auto_retry_blocked_by_permanent_provider=True,
                _log=lambda *args: None,
                after=lambda *args: scheduled.append(args),
            )
            record = {
                "run_id": "sync-run", "status": "başarısız",
                "settings": {"auto_retry_files": True, "mode": "sync"},
                "files": {str(source): {
                    "status": "error", "phase": "Ana Çeviri"}},
            }

            self.assertFalse(
                gui.App._schedule_failed_file_retry(stub, record))
            self.assertEqual(scheduled, [])

    def test_permanent_file_state_is_not_saved_as_crash_resume_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            retryable = Path(tmp) / "retryable.srt"
            source.write_text("x", encoding="utf-8")
            retryable.write_text("x", encoding="utf-8")
            record = {"files": {
                str(source): {
                    "status": "error", "phase": "Kaynak değişti"},
                str(retryable): {
                    "status": "error", "phase": "Faz-2 hatası"},
            }}

            self.assertEqual(
                gui._interrupted_run_pending_files(record),
                [str(retryable)])

    def test_permanent_provider_run_is_not_resumed_after_app_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            source.write_text("x", encoding="utf-8")
            record = {
                "recovery_blocked_reason": "permanent_provider",
                "files": {str(source): {
                    "status": "error", "phase": "Eksik çeviri"}},
            }

            self.assertEqual(
                gui._interrupted_run_pending_files(record), [])

    def test_failed_quality_row_cannot_be_promoted_to_done(self):
        source = str(Path("movie.srt"))
        record = {
            "files": {source: {"status": "pending", "phase": "Bekliyor"}},
            "fixes_applied": 0,
            "reports": [],
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record,
        )
        rows = [{
            "name": "movie.srt",
            "run_status": "error",
            "pass_coverage": "skipped_missing",
        }]
        with patch.object(gui, "atomic_write_json"):
            gui.App._record_quality_report(stub, rows, [])
        self.assertEqual(record["files"][source]["status"], "error")

    def test_duplicate_basenames_are_not_cross_marked_by_report_name(self):
        first = str(Path("folder-a") / "movie.srt")
        second = str(Path("folder-b") / "movie.srt")
        record = {
            "files": {
                first: {"status": "pending", "phase": "Bekliyor"},
                second: {"status": "pending", "phase": "Bekliyor"},
            },
            "fixes_applied": 0,
            "reports": [],
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record,
        )
        with patch.object(gui, "atomic_write_json"):
            gui.App._record_quality_report(
                stub, [{"name": "movie.srt"}], [])
        self.assertEqual(record["files"][first]["status"], "pending")
        self.assertEqual(record["files"][second]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
