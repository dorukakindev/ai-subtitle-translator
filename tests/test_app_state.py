import tempfile
import unittest
from pathlib import Path

from app_state import atomic_write_json, mutate_batch_ids


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


if __name__ == "__main__":
    unittest.main()
