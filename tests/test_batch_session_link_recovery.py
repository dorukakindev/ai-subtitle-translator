import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hybrid_translate as ht


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


if __name__ == "__main__":
    unittest.main()
