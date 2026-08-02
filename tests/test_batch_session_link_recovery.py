import json
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class BatchSessionLinkRecoveryTest(unittest.TestCase):
    def test_durable_fmap_restores_submitted_link_before_resubmit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            bid_path = root / "batch_id.txt"
            bid_path.write_text("batch-safe-1", encoding="utf-8")
            fmap_path = root / "batch_fmap_batch-safe-1.json"
            fmap_path.write_text(json.dumps({
                "type": "hybrid",
                "source_path": str(source),
                "output_path": str(root / "translated.srt"),
                "schema_name": "Belgesel",
                "session_fingerprint": "fp-1",
                "fmap": {"chunk_0": [[1, "00:00:00,000", "00:00:01,000"]]},
            }), encoding="utf-8")
            session = {
                "files": {str(source): {"status": "pending"}},
            }

            with patch.object(ht, "_batch_id_path", return_value=bid_path), \
                    patch.object(ht, "_batch_fmap_path", return_value=fmap_path):
                count = ht._recover_submitted_batch_links(
                    session, [str(source)], "fp-1")

            self.assertEqual(count, 1)
            entry = session["files"][str(source)]
            self.assertEqual(entry["status"], "submitted")
            self.assertEqual(entry["batch_id"], "batch-safe-1")
            self.assertEqual(entry["out_path"], str(root / "translated.srt"))

    def test_mismatched_run_fingerprint_is_not_reattached(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("x", encoding="utf-8")
            bid_path = root / "batch_id.txt"
            bid_path.write_text("batch-safe-1", encoding="utf-8")
            fmap_path = root / "batch_fmap_batch-safe-1.json"
            fmap_path.write_text(json.dumps({
                "type": "hybrid",
                "source_path": str(source),
                "session_fingerprint": "old-fingerprint",
                "fmap": {"chunk_0": [[1, "a", "b"]]},
            }), encoding="utf-8")
            session = {"files": {str(source): {"status": "pending"}}}

            with patch.object(ht, "_batch_id_path", return_value=bid_path), \
                    patch.object(ht, "_batch_fmap_path", return_value=fmap_path):
                count = ht._recover_submitted_batch_links(
                    session, [str(source)], "new-fingerprint")

            self.assertEqual(count, 0)
            self.assertEqual(session["files"][str(source)]["status"], "pending")

    def test_resumed_batch_updates_original_session_terminal_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("x", encoding="utf-8")
            session = {
                "input_dir": str(root),
                "files": {
                    str(source): {
                        "status": "submitted",
                        "batch_id": "batch-safe-1",
                    },
                },
            }
            with patch.object(ht, "_session_dir", return_value=root):
                ht._save_batch_session(session)
                updated = ht.update_recovered_batch_session(
                    "batch-safe-1", str(source), "completed",
                    out_path=str(root / "translated.srt"),
                )
                loaded = ht.load_batch_session(str(root))

            self.assertTrue(updated)
            entry = loaded["files"][str(source)]
            self.assertEqual(entry["status"], "completed")
            self.assertEqual(entry["out_path"], str(root / "translated.srt"))

    def test_orphan_reconcile_attaches_submitted_batch_to_failed_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("x", encoding="utf-8")
            session = {
                "input_dir": str(root),
                "files": {str(source): {"status": "failed"}},
            }
            with patch.object(ht, "_session_dir", return_value=root):
                ht._save_batch_session(session)
                updated = ht.update_recovered_batch_session(
                    "batch-orphan", str(source), "submitted",
                    out_path=str(root / "translated.srt"),
                )
                loaded = ht.load_batch_session(str(root))

            self.assertTrue(updated)
            entry = loaded["files"][str(source)]
            self.assertEqual(entry["status"], "submitted")
            self.assertEqual(entry["batch_id"], "batch-orphan")

    def test_resume_dispatch_persists_hybrid_outcome(self):
        source = inspect.getsource(gui.App._resume_batches)
        self.assertIn("result_out=_resume_result", source)
        self.assertIn("update_recovered_batch_session", source)

    def test_submitted_batch_reconnects_before_helper_analysis(self):
        source = inspect.getsource(gui.App._run_hybrid)
        reconnect = source.index(
            'file_status == "submitted" and sess_entry.get("batch_id")')
        analysis = source.index("ht.analyze_with_helper(")
        self.assertLess(reconnect, analysis)
        reconnect_block = source[reconnect:analysis]
        self.assertIn("analiz tekrarlanmadan", reconnect_block)
        self.assertIn("ht.empty_analysis_result", reconnect_block)

    def test_added_file_does_not_discard_submitted_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / "first.srt"
            second = root / "second.srt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            fingerprint = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(first)], {"model": "m"})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(first)], fingerprint)
                ht.update_batch_session(
                    session, str(first), "submitted", batch_id="batch-paid")
                expanded_fingerprint = ht.batch_session_fingerprint(
                    str(root), str(root / "out"), [str(first), str(second)],
                    {"model": "m"})
                expanded = ht.create_batch_session(
                    str(root), str(root / "out"), [str(first), str(second)],
                    expanded_fingerprint)

            self.assertEqual(
                expanded["files"][str(first)]["status"], "submitted")
            self.assertEqual(
                expanded["files"][str(first)]["batch_id"], "batch-paid")
            self.assertEqual(expanded["files"][str(second)]["status"], "pending")

    def test_missing_completed_output_is_requeued(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("source", encoding="utf-8")
            fingerprint = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)
                ht.update_batch_session(
                    session, str(source), "completed",
                    out_path=str(root / "missing.srt"))
                resumed = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)

            self.assertEqual(resumed["files"][str(source)]["status"], "pending")

    def test_user_edited_completed_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "output.srt"
            source.write_text("source", encoding="utf-8")
            output.write_text("first final", encoding="utf-8")
            fingerprint = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)
                ht.update_batch_session(
                    session, str(source), "completed", out_path=str(output),
                    output_state=ht._file_state_signature(str(output)))
                output.write_text("user corrected final", encoding="utf-8")
                resumed = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)

            entry = resumed["files"][str(source)]
            self.assertEqual(entry["status"], "completed")
            self.assertEqual(
                entry["output_state"], ht._file_state_signature(str(output)))

    def test_explicit_retranslate_choice_resets_completed_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "output.srt"
            source.write_text("source", encoding="utf-8")
            output.write_text("final", encoding="utf-8")
            fingerprint = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)
                ht.update_batch_session(
                    session, str(source), "completed", out_path=str(output))
                forced = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint,
                    force_retranslate_paths={str(source).upper()})

            self.assertEqual(forced["files"][str(source)]["status"], "pending")

    def test_settings_change_preserves_paid_submitted_batch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("source", encoding="utf-8")
            old_fp = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {"model": "old"})
            new_fp = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {"model": "new"})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], old_fp)
                ht.update_batch_session(
                    session, str(source), "submitted", batch_id="batch-paid")
                resumed = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], new_fp)

            self.assertEqual(resumed["files"][str(source)]["status"], "submitted")
            self.assertEqual(resumed["files"][str(source)]["batch_id"], "batch-paid")

    def test_successfully_cancelled_batch_becomes_retryable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            source.write_text("source", encoding="utf-8")
            fingerprint = ht.batch_session_fingerprint(
                str(root), str(root / "out"), [str(source)], {})
            with patch.object(ht, "_session_dir", return_value=root):
                session = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)
                ht.update_batch_session(
                    session, str(source), "submitted", batch_id="batch-cancel")
                changed = ht.mark_cancelled_batch_sessions(["batch-cancel"])
                retried = ht.create_batch_session(
                    str(root), str(root / "out"), [str(source)], fingerprint)

            self.assertEqual(changed, 1)
            self.assertEqual(retried["files"][str(source)]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
