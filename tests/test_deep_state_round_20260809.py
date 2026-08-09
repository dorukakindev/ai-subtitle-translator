import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import provider_retry
import subtitle_translator_gui as gui
from app_state import mutate_batch_ids


class BatchSessionFailClosedTest(unittest.TestCase):
    def test_terminal_state_write_failure_does_not_abort_other_results(self):
        backend = SimpleNamespace(
            update_batch_session=MagicMock(side_effect=OSError("disk full")))
        session = {"files": {"film.srt": {"status": "submitted"}}}
        app = SimpleNamespace(_log=MagicMock())

        saved = gui.App._record_batch_terminal_state(
            app, backend, session, "film.srt", "failed")

        self.assertFalse(saved)
        self.assertEqual(session["files"]["film.srt"]["status"], "failed")
        self.assertEqual(
            session["files"]["film.srt"]["state_persist_error"], "OSError")
        self.assertIn(
            "diğer dosyalar işlenmeye devam edecek",
            " ".join(str(call.args[0]) for call in app._log.call_args_list),
        )

    def test_non_terminal_state_cannot_use_best_effort_writer(self):
        app = SimpleNamespace(_log=MagicMock())
        with self.assertRaises(ValueError):
            gui.App._record_batch_terminal_state(
                app, SimpleNamespace(), {"files": {}}, "film.srt", "completed")

    def test_same_input_with_trailing_separator_loads_existing_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            session = {"input_dir": str(root), "files": {}}
            with patch.object(ht, "_session_dir", return_value=root):
                ht._save_batch_session(session)
                loaded = ht.load_batch_session(str(root) + os.sep)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["input_dir"], str(root))

    def test_corrupt_session_is_not_overwritten_by_create(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("source", encoding="utf-8")
            with patch.object(ht, "_session_dir", return_value=root):
                session_path = ht._session_path(str(root))
                original = b"{broken-session"
                session_path.write_bytes(original)
                old = 1_600_000_000
                os.utime(session_path, (old, old))
                with self.assertRaisesRegex(RuntimeError, "üzerine yazılmadı"):
                    ht.create_batch_session(
                        str(root), str(root / "out"), [str(source)], "fp")
                self.assertEqual(session_path.read_bytes(), original)

    def test_stale_session_updates_merge_distinct_file_states(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.srt"
            second = root / "second.srt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            with patch.object(ht, "_session_dir", return_value=root):
                ht.create_batch_session(
                    str(root), str(root / "out"),
                    [str(first), str(second)], "fingerprint")
                stale_first = ht.load_batch_session(str(root))
                stale_second = ht.load_batch_session(str(root))

                ht.update_batch_session(
                    stale_first, str(first), "completed",
                    out_path=str(root / "first.tr.srt"))
                ht.update_batch_session(
                    stale_second, str(second), "submitted",
                    batch_id="batch-second")

                saved = ht.load_batch_session(str(root))
                self.assertEqual(
                    saved["files"][str(first)]["status"], "completed")
                self.assertEqual(
                    saved["files"][str(second)]["status"], "submitted")
                self.assertEqual(
                    saved["files"][str(second)]["batch_id"], "batch-second")

    def test_stale_completion_does_not_clear_new_pending_work(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.srt"
            second = root / "second.srt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(first)], "fingerprint")
                ht.update_batch_session(session, str(first), "completed")
                ht.create_batch_session(
                    str(root), str(root / "out"),
                    [str(first), str(second)], "fingerprint")

                self.assertFalse(ht.clear_batch_session(
                    str(root), fingerprint="fingerprint"))
                saved = ht.load_batch_session(str(root))
                self.assertEqual(
                    saved["files"][str(second)]["status"], "pending")


class SyncCheckpointFailClosedTest(unittest.TestCase):
    def test_corrupt_sync_store_is_not_overwritten_or_partially_cleared(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".sync_checkpoint.json"
            original = b"{broken-checkpoint"
            path.write_bytes(original)
            log = MagicMock()
            self.assertFalse(gui.save_sync_ckpt_entry_to_store(
                path, "c1", "text", "hash", log_fn=log))
            self.assertFalse(gui.clear_sync_ckpt_entries_from_store(
                path, {"c1:hash"}, log_fn=log))
            self.assertEqual(path.read_bytes(), original)

    def test_unreadable_batch_id_store_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "batch_id.txt"
            original = b"batch-old-1\n\xff\xfe"
            path.write_bytes(original)
            with self.assertRaisesRegex(ValueError, "değiştirilmedi"):
                mutate_batch_ids(path, add=["batch-new-2"])
            self.assertEqual(path.read_bytes(), original)

    def test_corrupt_stage_store_is_not_overwritten_or_cleared(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".sync_stage.json"
            original = b"{broken-stage"
            path.write_bytes(original)
            log = MagicMock()
            self.assertFalse(gui.save_sync_stage_entry_to_store(
                path, "source.srt", "hash", "fp", "run", {"c1": "ok"},
                log_fn=log))
            self.assertFalse(gui.clear_sync_stage_entry_from_store(
                path, "source.srt", log_fn=log))
            self.assertEqual(path.read_bytes(), original)


class ResponseCheckpointUsageTest(unittest.TestCase):
    def tearDown(self):
        provider_retry.configure_response_checkpoint()

    def test_local_checkpoint_hit_reports_real_zero_usage(self):
        response = provider_retry._cached_chat_response({
            "content": "ok", "finish_reason": "stop"})
        callback = MagicMock()
        callback.report_missing_usage = MagicMock()

        ht._report_helper_usage(response, callback)

        callback.assert_called_once_with(0, cached=0)
        callback.report_missing_usage.assert_not_called()
        self.assertTrue(response.response_checkpoint_hit)
        self.assertTrue(response.usage_available)

    def test_checkpoint_key_preserves_case_sensitive_provider_path(self):
        upper = SimpleNamespace(base_url="HTTPS://API.Example.com/Official/V1")
        lower = SimpleNamespace(base_url="https://api.example.com/official/v1")
        host_case = SimpleNamespace(base_url="https://API.EXAMPLE.COM/Official/V1")
        kwargs = {"messages": [{"role": "user", "content": "same"}]}

        upper_key = provider_retry._response_checkpoint_key(
            upper, "model", kwargs)
        lower_key = provider_retry._response_checkpoint_key(
            lower, "model", kwargs)
        host_case_key = provider_retry._response_checkpoint_key(
            host_case, "model", kwargs)

        self.assertNotEqual(upper_key, lower_key)
        self.assertEqual(upper_key, host_case_key)


class AutoGlossaryFailClosedTest(unittest.TestCase):
    @staticmethod
    def _stub(glossary_path):
        return SimpleNamespace(
            _active_snapshot=None,
            src_var=SimpleNamespace(get=lambda: "English"),
            tgt_var=SimpleNamespace(get=lambda: "Turkish"),
            glossary_var=SimpleNamespace(get=lambda: glossary_path),
            _helper_api_key=lambda _role: "key",
            _helper_api_base_url=lambda _role: "",
            _helper_api_model=lambda _role: "model",
            _log=MagicMock(),
        )

    def test_missing_glossary_path_skips_api(self):
        stub = self._stub("")
        status = {}
        with patch.object(ht, "build_glossary_suggestions") as build:
            gui.App._run_auto_glossary(
                stub, [], [], "episode.srt", status_out=status)
        build.assert_not_called()
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error"], "missing_glossary_path")

    def test_corrupt_json_glossary_is_preserved_and_api_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            glossary = Path(td) / "glossary.json"
            original = b"{broken-glossary"
            glossary.write_bytes(original)
            stub = self._stub(str(glossary))
            status = {}
            with patch.object(ht, "build_glossary_suggestions") as build:
                gui.App._run_auto_glossary(
                    stub, [], [], "episode.srt", status_out=status)
            build.assert_not_called()
            self.assertEqual(status["error"], "corrupt_glossary_store")
            self.assertEqual(glossary.read_bytes(), original)


class MainGlossaryFailClosedTest(unittest.TestCase):
    def test_selected_corrupt_json_glossary_raises_in_strict_mode(self):
        with tempfile.TemporaryDirectory() as td:
            glossary = Path(td) / "glossary.json"
            glossary.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(ht.GlossaryLoadError, "JSON sözlük bozuk"):
                ht.load_glossary(str(glossary), strict=True)
            self.assertEqual(ht.load_glossary(str(glossary)), {})

    def test_selected_missing_glossary_raises_but_empty_selection_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "missing.json")
            with self.assertRaisesRegex(ht.GlossaryLoadError, "bulunamadı"):
                ht.load_glossary(missing, strict=True)
        self.assertEqual(ht.load_glossary("", strict=True), {})


class MultiInstanceCrashRecoveryTest(unittest.TestCase):
    def test_live_instance_record_does_not_hide_dead_instance_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            own = root / "active_run.100.json"
            live = root / "active_run.200.json"
            dead = root / "active_run.300.json"
            live.write_text(json.dumps({
                "pid": 200, "process_start": "live", "started_epoch": 20,
                "files": {str(root / "live.srt"): {"status": "running"}},
            }), encoding="utf-8")
            dead.write_text(json.dumps({
                "pid": 300, "process_start": "dead", "started_epoch": 30,
                "run_id": "dead-run",
                "files": {str(root / "dead.srt"): {"status": "running"}},
            }), encoding="utf-8")

            with patch.object(gui, "_active_run_state_path", return_value=own), \
                 patch.object(gui, "_pid_alive", side_effect=lambda pid: pid == 200), \
                 patch.object(gui, "_process_start_marker", return_value="live"):
                recovered = gui._load_interrupted_run_record()

            self.assertEqual(recovered["run_id"], "dead-run")
            self.assertEqual(recovered["_state_path"], str(dead))
            self.assertTrue(live.exists())

    def test_interrupted_run_can_have_only_one_live_resume_owner(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "active_run.999.json"
            path.write_text(json.dumps({
                "pid": 999, "process_start": "dead", "run_id": "run-1",
                "files": {},
            }), encoding="utf-8")

            def marker(pid):
                return f"marker-{pid}"

            with patch.object(gui, "_process_start_marker", side_effect=marker), \
                 patch.object(gui, "_pid_alive", side_effect=lambda pid: pid == 111):
                self.assertTrue(gui._claim_interrupted_run_record(
                    path, "run-1", claimant_pid=111))
                self.assertFalse(gui._claim_interrupted_run_record(
                    path, "run-1", claimant_pid=222))

            with patch.object(gui, "_process_start_marker", side_effect=marker), \
                 patch.object(gui, "_pid_alive", return_value=False):
                self.assertTrue(gui._claim_interrupted_run_record(
                    path, "run-1", claimant_pid=222))

            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["resume_claim"]["pid"], 222)


if __name__ == "__main__":
    unittest.main()
