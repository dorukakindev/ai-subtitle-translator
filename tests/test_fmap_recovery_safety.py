import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui
from app_state import STATE_DIR_ENV


class FmapLoadStatusTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._td.name})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def _write(self, batch_id, value):
        path = ht._batch_fmap_path(batch_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_detailed_loader_distinguishes_missing_invalid_and_empty(self):
        self.assertEqual(
            ht.load_fmap_for_batch("batch_missing", detailed=True),
            ("missing", None),
        )

        corrupt = self._write("batch_corrupt", "{not json")
        self.assertEqual(
            ht.load_fmap_for_batch("batch_corrupt", detailed=True),
            ("invalid_json", None),
        )
        self.assertTrue(corrupt.exists())

        self._write("batch_schema", {"fmap": {"cid": "not-a-list"}})
        self.assertEqual(
            ht.load_fmap_for_batch("batch_schema", detailed=True),
            ("invalid_schema", None),
        )

        self._write("batch_empty", {"fmap": {}})
        self.assertEqual(
            ht.load_fmap_for_batch("batch_empty", detailed=True),
            ("valid_empty", {}),
        )

    def test_valid_fmap_is_converted_to_tuples(self):
        self._write("batch_ok", {"fmap": {"cid": [["1", "start", "end"]]}})
        status, fmap = ht.load_fmap_for_batch("batch_ok", detailed=True)
        self.assertEqual(status, "ok")
        self.assertEqual(fmap, {"cid": [("1", "start", "end")]})
        self.assertEqual(ht.load_fmap_for_batch("batch_ok"), fmap)


class SavedRegularRequestSafetyTest(unittest.TestCase):
    def test_legacy_fmap_without_requests_is_not_rebuilt_from_ui(self):
        requests, reason = gui._saved_regular_requests(
            {"type": "regular", "fmap": {"cid": []}},
            {"cid": []},
        )
        self.assertIsNone(requests)
        self.assertEqual(reason, "missing_requests")

    def test_request_ids_must_cover_saved_fmap(self):
        requests, reason = gui._saved_regular_requests(
            {"requests": [{"custom_id": "other"}]},
            {"cid": []},
        )
        self.assertIsNone(requests)
        self.assertEqual(reason, "id_mismatch")

    def test_matching_saved_requests_are_reused(self):
        saved = [{"custom_id": "cid", "body": {"messages": []}}]
        requests, reason = gui._saved_regular_requests(
            {"requests": saved},
            {"cid": []},
        )
        self.assertIs(requests, saved)
        self.assertEqual(reason, "")

    def test_hybrid_resume_uses_saved_output_path(self):
        saved = gui._resolve_hybrid_resume_output_path({
            "output_path": r"D:\out\final.srt",
            "output_dir": r"D:\other",
            "source_path": r"D:\src\episode.srt",
        })
        self.assertEqual(saved, r"D:\out\final.srt")

    def test_hybrid_resume_derives_path_from_saved_dir_and_source(self):
        with tempfile.TemporaryDirectory() as td:
            saved = gui._resolve_hybrid_resume_output_path({
                "output_dir": td,
                "source_path": r"D:\src\episode.vtt",
            })
            self.assertEqual(saved, os.path.join(td, "episode.srt"))

    def test_hybrid_resume_rejects_missing_safe_path(self):
        self.assertEqual(gui._resolve_hybrid_resume_output_path({}), "")


class RetryClassificationTest(unittest.TestCase):
    def test_transient_provider_errors_are_retried(self):
        for message in ("HTTP 408", "HTTP 429", "HTTP 529", "server error", "internal error"):
            with self.subTest(message=message):
                self.assertTrue(gui._is_transient_retry_error(RuntimeError(message)))

    def test_permanent_http_errors_are_not_retried(self):
        for code in ("400", "401", "403", "404", "409", "422"):
            with self.subTest(code=code):
                self.assertFalse(gui._is_transient_retry_error(
                    RuntimeError(f"HTTP {code}: internal error")
                ))

    def test_upstream_server_error_uses_small_request_fallback(self):
        self.assertTrue(gui._is_upstream_provider_error(
            RuntimeError("upstream server error")
        ))


class OrphanBatchCancellationTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {STATE_DIR_ENV: self._td.name})
        self._env.start()
        self.client = MagicMock()
        self.client.files.create.return_value.id = "file_1"
        self.client.batches.create.return_value.id = "batch_orphan"
        self.requests = [{"custom_id": "cid", "body": {"messages": []}}]
        self.fmap = {"cid": [("1", "start", "end")]}

    def tearDown(self):
        self._env.stop()
        self._td.cleanup()

    def _fail_only_fmap_write(self, path, data):
        if Path(path).name.startswith("hybrid_batch_intent_"):
            return self._real_atomic_write_json(path, data)
        raise OSError("disk full")

    def test_fmap_write_failure_cancels_remote_batch_and_removes_id(self):
        self._real_atomic_write_json = ht.atomic_write_json
        with patch("openai.OpenAI", return_value=self.client), \
             patch.object(ht, "atomic_write_json", side_effect=self._fail_only_fmap_write):
            with self.assertRaisesRegex(RuntimeError, "recovery metadata"):
                ht.submit_batch(
                    "key", self.requests, file_map=self.fmap, log_fn=MagicMock())

        self.client.batches.cancel.assert_called_once_with("batch_orphan")
        self.assertFalse(ht._batch_id_path().exists())

    def test_failed_remote_cancel_preserves_batch_id_for_manual_recovery(self):
        self.client.batches.cancel.side_effect = RuntimeError("provider unavailable")
        self._real_atomic_write_json = ht.atomic_write_json
        with patch("openai.OpenAI", return_value=self.client), \
             patch.object(ht, "atomic_write_json", side_effect=self._fail_only_fmap_write):
            with self.assertRaisesRegex(RuntimeError, "uzak iptal=başarısız"):
                ht.submit_batch(
                    "key", self.requests, file_map=self.fmap, log_fn=MagicMock())

        self.assertEqual(
            ht._batch_id_path().read_text(encoding="utf-8").strip(),
            "batch_orphan",
        )


if __name__ == "__main__":
    unittest.main()
