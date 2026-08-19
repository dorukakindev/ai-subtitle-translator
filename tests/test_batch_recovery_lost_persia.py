import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui
from app_state import STATE_DIR_ENV, state_path


class BatchRecoveryLostPersiaTests(unittest.TestCase):
    def _mkout(self):
        fd, path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        return path

    def test_salvage_json_objects_keeps_complete_items_only(self):
        raw = '[{"i":514,"t":"Bu sat\u0131r tamam"},{"i":515,"t":"Marduk onu se\u00e7ti"},{"i":516,"t":"yar\u0131m'
        out = ht._salvage_json_objects(raw)
        self.assertEqual([x["i"] for x in out], [514, 515])
        self.assertEqual(out[1]["t"], "Marduk onu se\u00e7ti")

    def test_save_results_salvages_truncated_batch_chunk(self):
        out_path = self._mkout()
        log_calls = []

        def log_fn(msg, level="info"):
            log_calls.append((level, msg))

        raw_translation = '[{"i":514,"t":"Cyrus me\u015fru bir h\u00fck\u00fcmdar oldu\u011funu g\u00f6sterir."},{"i":515,"t":"Marduk onu y\u00f6netmesi i\u00e7in se\u00e7mi\u015ftir."},{"i":516,"t":"yar\u0131m'
        response_line = {
            "custom_id": "chunk_513",
            "response": {
                "body": {
                    "choices": [{"message": {"content": raw_translation},
                                 "finish_reason": "length"}],
                    "usage": {"total_tokens": 10},
                }
            },
        }
        mock_client = mock.MagicMock()
        mock_client.files.content.return_value.text = json.dumps(response_line, ensure_ascii=False)
        file_map = {
            "chunk_513": [
                (514, "00:00:01,000", "00:00:02,000"),
                (515, "00:00:02,000", "00:00:03,000"),
                (516, "00:00:03,000", "00:00:04,000"),
            ]
        }
        cues = [
            SimpleNamespace(index=514, text="In this line, Cyrus is trying to show that he's a legitimate ruler,"),
            SimpleNamespace(index=515, text="the God Marduk himself chose him to rule."),
            SimpleNamespace(index=516, text="But Cyrus doesn't just use the foreign religion"),
        ]

        try:
            with mock.patch("openai.OpenAI", return_value=mock_client):
                count, n_marked = ht.save_results(
                    openai_api_key="fake",
                    output_file_id="fid",
                    file_map=file_map,
                    output_path=out_path,
                    log_fn=log_fn,
                    src_cues=cues,
                )
            written = Path(out_path).read_text(encoding="utf-8")
            self.assertEqual(count, 3)
            self.assertEqual(n_marked, 1)
            self.assertIn("Cyrus me\u015fru bir h\u00fck\u00fcmdar", written)
            self.assertIn("Marduk onu y\u00f6netmesi", written)
            self.assertIn("[\u00c7EV\u0130R\u0130 EKS\u0130K]", written)
            self.assertTrue(any("JSON k\u0131smi kurtar\u0131ld\u0131" in msg for _level, msg in log_calls))
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_final_write_cleanup_common_documentary_residue(self):
        text = "[Ali speaking]\n21 feet mesafe var. Babylon b\u00fcy\u00fckt\u00fc."
        out = ht._normalize_output_text(text)
        # SDH tan\u0131mlay\u0131c\u0131s\u0131 art\u0131k \u00e7evrilmiyor, tamamen siliniyor
        self.assertNotIn("[Ali", out)
        self.assertIn("21 fit", out)
        self.assertIn("Babil", out)
        self.assertNotIn("speaking", out)
        self.assertNotIn("feet", out)
        self.assertNotIn("Babylon", out)

    def test_neighbor_start_duplicate_is_flagged(self):
        blocks = [
            (122, "00:00:01,000 --> 00:00:02,000", "Yunanlar ayr\u0131ca \u015fu efsanevi metropol\u00fcn hazinelerle dolu oldu\u011funu s\u00f6ylerler."),
            (123, "00:00:02,000 --> 00:00:03,000", "Yunanlar ayr\u0131ca \u015fu efsanevi metropol\u00fcn ak\u0131l almaz zenginliklerle dolu oldu\u011funu s\u00f6ylerler."),
        ]
        hits = ht.run_validators(blocks)
        self.assertTrue(any(reason == "NEIGHBOR_PREFIX_ECHO" for *_rest, reason in hits))

    def test_split_file_map_contains_only_part_requests(self):
        fmap = {"a": [(1, "s", "e")], "b": [(2, "s", "e")]}
        self.assertEqual(gui._slice_file_map(fmap, [{"custom_id": "b"}]), {"b": fmap["b"]})

    def test_regular_group_not_ready_until_every_part_terminal(self):
        groups = {"run": {"expected": 2, "seen": {0}, "terminal": True}}
        self.assertFalse(gui._regular_batch_groups_ready(groups))
        groups["run"]["seen"].add(1)
        groups["run"]["terminal"] = False
        self.assertFalse(gui._regular_batch_groups_ready(groups))
        groups["run"]["terminal"] = True
        self.assertTrue(gui._regular_batch_groups_ready(groups))

    def test_manifest_identifies_only_unsent_parts(self):
        manifest = {
            "part_count": 3,
            "parts": [{"part_index": index} for index in range(3)],
        }
        self.assertEqual(
            gui._regular_manifest_missing_indices(manifest, {0, 2}), [1])

    def test_resume_submits_only_manifest_parts_without_batch_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            source = Path(tmpdir) / "source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            output = Path(tmpdir) / "out.srt"
            run_id = "run-safe"
            context = {
                "context_version": 1,
                "api_key_fingerprint": hashlib.sha256(b"key").hexdigest(),
                "main_api_base_url": "",
            }
            common = {
                "output_dir": tmpdir,
                "output_paths": {str(source): str(output)},
                "source_languages": {str(source): "English"},
                "schema_names": {str(source): "Film"},
                "source_hashes": {str(source): gui._file_content_sha256(source)},
                "output_baselines": {str(source): {"exists": False}},
                "run_context": context,
                "locked_terms_by_file": {str(source): {}},
            }
            parts = [
                {"part_index": 0, "requests": [{"custom_id": "c0"}],
                 "fmap": {"c0": [[1, "ts", str(source)]]}},
                {"part_index": 1, "requests": [{"custom_id": "c1"}],
                 "fmap": {"c1": [[2, "ts", str(source)]]}},
            ]
            manifest = {
                "type": "regular_run", "run_id": run_id, "part_count": 2,
                "parts": parts, "submitted": {"0": "batch_existing"}, **common,
            }
            manifest_path = gui._regular_batch_manifest_path(run_id)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            existing = {
                "type": "regular", "run_id": run_id,
                "run_manifest": str(manifest_path), "part_index": 0,
                "part_count": 2, "requests": parts[0]["requests"],
                "fmap": parts[0]["fmap"], **common,
            }
            state_path(gui.__file__, "batch_fmap_batch_existing.json").write_text(
                json.dumps(existing), encoding="utf-8")

            client = mock.MagicMock()
            client.files.create.return_value = SimpleNamespace(id="file-new")
            client.batches.create.return_value = SimpleNamespace(id="batch_new")
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            app._unregister_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client):
                expanded = app._submit_missing_regular_batch_parts(
                    "key", ["batch_existing"])

            self.assertEqual(expanded, ["batch_existing", "batch_new"])
            self.assertTrue(state_path(
                gui.__file__, "batch_fmap_batch_new.json").exists())
            client.batches.create.assert_called_once()

    def test_crash_intent_recovers_existing_remote_batch_without_resubmit(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            source = Path(tmpdir) / "source.srt"
            source.write_text("source", encoding="utf-8")
            output = Path(tmpdir) / "out.srt"
            run_id = "crash-safe"
            token = f"{run_id}-0"
            part = {
                "part_index": 0,
                "requests": [{"custom_id": "c0"}],
                "fmap": {"c0": [[1, "ts", str(source)]]},
            }
            manifest = {
                "type": "regular_run", "run_id": run_id, "part_count": 1,
                "output_dir": tmpdir,
                "output_paths": {str(source): str(output)},
                "source_languages": {str(source): "English"},
                "schema_names": {str(source): "Film"},
                "source_hashes": {str(source): gui._file_content_sha256(source)},
                "output_baselines": {str(source): {"exists": False}},
                "locked_terms_by_file": {str(source): {}},
                "run_context": {
                    "context_version": 1,
                    "api_key_fingerprint": hashlib.sha256(b"key").hexdigest(),
                    "main_api_base_url": "",
                },
                "parts": [part],
            }
            gui._regular_batch_manifest_path(run_id).write_text(
                json.dumps(manifest), encoding="utf-8")
            intent = gui._regular_batch_intent_path(run_id, 0)
            intent.write_text(json.dumps({
                "run_id": run_id, "part_index": 0,
                "input_file_id": "input-file", "recovery_intent": token,
            }), encoding="utf-8")
            remote = SimpleNamespace(
                id="batch_orphan", input_file_id="input-file",
                metadata={"recovery_intent": token})
            client = mock.MagicMock()
            client.batches.list.return_value = [remote]
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client):
                recovered = app._reconcile_regular_batch_intents("key")

            self.assertEqual(recovered, ["batch_orphan"])
            self.assertFalse(intent.exists())
            self.assertTrue(state_path(
                gui.__file__, "batch_fmap_batch_orphan.json").exists())
            client.batches.create.assert_not_called()

    def test_hybrid_crash_intent_recovers_remote_batch_without_resubmit(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            token = "hybrid-intent"
            fmap_data = {
                "type": "hybrid", "source_path": str(Path(tmpdir) / "source.srt"),
                "output_path": str(Path(tmpdir) / "out.srt"),
                "run_context": {
                    "context_version": 1,
                    "api_key_fingerprint": hashlib.sha256(b"key").hexdigest(),
                },
                "fmap": {"c0": [[1, "ts", "source"]]},
            }
            intent = ht._hybrid_batch_intent_path(token)
            intent.write_text(json.dumps({
                "recovery_intent": token, "input_file_id": "input-hybrid",
                "base_url": "", "fmap_data": fmap_data,
            }), encoding="utf-8")
            remote = SimpleNamespace(
                id="batch_hybrid_orphan", input_file_id="input-hybrid",
                metadata={"recovery_intent": token})
            client = mock.MagicMock()
            client.batches.list.return_value = [remote]
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client), \
                 mock.patch.object(ht, "update_recovered_batch_session") as update:
                recovered = app._reconcile_hybrid_batch_intents("key")

            self.assertEqual(recovered, ["batch_hybrid_orphan"])
            self.assertFalse(intent.exists())
            self.assertTrue(ht._batch_fmap_path("batch_hybrid_orphan").exists())
            client.batches.create.assert_not_called()
            update.assert_called_once()

    def test_cancel_requested_regular_intent_cancels_remote_without_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            source = Path(tmpdir) / "source.srt"
            source.write_text("source", encoding="utf-8")
            run_id, token = "cancel-safe", "cancel-safe-0"
            manifest = {
                "type": "regular_run", "run_id": run_id, "part_count": 1,
                "run_context": {"api_key_fingerprint": hashlib.sha256(b"key").hexdigest()},
                "parts": [{"part_index": 0, "requests": [{"custom_id": "c0"}],
                           "fmap": {"c0": [[1, "ts", str(source)]]}}],
            }
            gui._regular_batch_manifest_path(run_id).write_text(
                json.dumps(manifest), encoding="utf-8")
            intent = gui._regular_batch_intent_path(run_id, 0)
            intent.write_text(json.dumps({
                "run_id": run_id, "part_index": 0, "input_file_id": "input-file",
                "recovery_intent": token, "cancel_requested": True,
            }), encoding="utf-8")
            remote = SimpleNamespace(id="batch_cancel", input_file_id="input-file",
                                     metadata={"recovery_intent": token})
            client = mock.MagicMock()
            client.batches.list.return_value = [remote]
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client):
                recovered = app._reconcile_regular_batch_intents("key")

            self.assertEqual(recovered, [])
            client.batches.cancel.assert_called_once_with("batch_cancel")
            self.assertFalse(intent.exists())
            app._register_batch.assert_not_called()

    def test_cancel_requested_hybrid_intent_cancels_remote_without_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            token = "hybrid-cancel"
            fmap_data = {
                "type": "hybrid", "source_path": str(Path(tmpdir) / "source.srt"),
                "output_path": str(Path(tmpdir) / "out.srt"),
                "run_context": {"api_key_fingerprint": hashlib.sha256(b"key").hexdigest()},
                "fmap": {"c0": [[1, "ts", "source"]]},
            }
            intent = ht._hybrid_batch_intent_path(token)
            intent.write_text(json.dumps({
                "recovery_intent": token, "input_file_id": "input-hybrid",
                "base_url": "", "fmap_data": fmap_data, "cancel_requested": True,
            }), encoding="utf-8")
            remote = SimpleNamespace(id="batch_hybrid_cancel", input_file_id="input-hybrid",
                                     metadata={"recovery_intent": token})
            client = mock.MagicMock()
            client.batches.list.return_value = [remote]
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client):
                recovered = app._reconcile_hybrid_batch_intents("key")

            self.assertEqual(recovered, [])
            client.batches.cancel.assert_called_once_with("batch_hybrid_cancel")
            self.assertFalse(intent.exists())
            app._register_batch.assert_not_called()

    def test_cancel_requested_intent_never_resubmits_when_remote_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.dict(os.environ, {STATE_DIR_ENV: tmpdir}):
            run_id, token = "cancel-missing", "cancel-missing-0"
            manifest = {
                "type": "regular_run", "run_id": run_id, "part_count": 1,
                "run_context": {"api_key_fingerprint": hashlib.sha256(b"key").hexdigest()},
                "parts": [{"part_index": 0, "requests": [{"custom_id": "c0"}],
                           "fmap": {"c0": [[1, "ts", "source"]]}}],
            }
            gui._regular_batch_manifest_path(run_id).write_text(
                json.dumps(manifest), encoding="utf-8")
            intent = gui._regular_batch_intent_path(run_id, 0)
            intent.write_text(json.dumps({
                "run_id": run_id, "part_index": 0, "input_file_id": "input-file",
                "recovery_intent": token, "cancel_requested": True,
            }), encoding="utf-8")
            client = mock.MagicMock()
            client.batches.list.return_value = []
            app = object.__new__(gui.App)
            app._log = mock.MagicMock()
            app._register_batch = mock.MagicMock()
            with mock.patch("openai.OpenAI", return_value=client):
                recovered = app._reconcile_regular_batch_intents("key")

            self.assertEqual(recovered, [])
            client.batches.create.assert_not_called()
            self.assertTrue(intent.exists())


if __name__ == "__main__":
    unittest.main()
