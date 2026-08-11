import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app_state import (atomic_write_json, best_effort_cancel_remote_batch,
                       is_safe_batch_id, mutate_batch_ids)


class AppStateTest(unittest.TestCase):
    def test_batch_id_mutation_deduplicates_and_preserves_unrelated_ids(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "batch_id.txt"
            mutate_batch_ids(path, add=["batch_a", "batch_b", "batch_a"])
            mutate_batch_ids(path, remove=["batch_a"], add=["batch_c"])
            self.assertEqual(path.read_text(encoding="utf-8").splitlines(),
                             ["batch_b", "batch_c"])

    def test_atomic_json_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fmap.json"
            atomic_write_json(path, {"ok": True})
            self.assertTrue(path.exists())
            self.assertEqual(list(Path(td).glob("*.tmp")), [])

    def test_batch_id_rejects_path_components(self):
        self.assertTrue(is_safe_batch_id("batch_abc-123"))
        for value in ("../secret", r"..\secret", "x/y", "x:y", ""):
            self.assertFalse(is_safe_batch_id(value))

    def test_batch_id_mutation_discards_unsafe_values(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "batch_id.txt"
            result = mutate_batch_ids(path, add=["batch_ok", "../escape", "x/y"])
            self.assertEqual(result, ["batch_ok"])
            self.assertEqual(path.read_text(encoding="utf-8"), "batch_ok")

    def test_best_effort_cancel_retries_transient_provider_failure(self):
        class TemporaryFailure(RuntimeError):
            status_code = 503

        cancel = MagicMock(side_effect=[TemporaryFailure("unavailable"), object()])
        client = SimpleNamespace(
            batches=SimpleNamespace(cancel=cancel),
            base_url="https://example.invalid/v1",
        )
        with patch("provider_retry._REGISTRY.wait_for_retry", return_value=0):
            self.assertTrue(best_effort_cancel_remote_batch(client, "batch_retry"))

        self.assertEqual(cancel.call_count, 2)


if __name__ == "__main__":
    unittest.main()
