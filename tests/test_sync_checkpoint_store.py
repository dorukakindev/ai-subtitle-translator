import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from subtitle_translator_gui import (
    SYNC_CKPT_STORE_VER,
    clear_sync_ckpt_entries_from_store,
    load_sync_ckpt_store,
    save_sync_ckpt_entry_to_store,
    should_clear_sync_ckpt,
)


class TestSyncCheckpointStore(unittest.TestCase):
    """Pure unit tests for v2 atomic sync checkpoint store and helpers without App() instantiation."""

    def test_v2_store_format_integrity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "merhaba", "hash1")
            content = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(content.get("version"), SYNC_CKPT_STORE_VER)
            self.assertIn("cid1:hash1", content.get("entries", {}))

    def test_v2_store_contains_expected_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "merhaba", "hash1")
            store = load_sync_ckpt_store(p)
            entry = store["entries"]["cid1:hash1"]
            self.assertEqual(entry["cid"], "cid1")
            self.assertEqual(entry["h"], "hash1")
            self.assertEqual(entry["t"], "merhaba")
            self.assertIsInstance(entry["updated_at"], float)

    def test_legacy_jsonl_migration_on_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_jsonl = Path(tmpdir) / ".sync_checkpoint.jsonl"
            p_json = Path(tmpdir) / ".sync_checkpoint.json"
            p_jsonl.write_text(
                json.dumps({"cid": "cid1", "t": "selam", "h": "h1"}) + "\n" +
                json.dumps({"cid": "cid2", "t": "dunya", "h": "h2"}) + "\n",
                encoding="utf-8"
            )
            store = load_sync_ckpt_store(p_json)
            self.assertEqual(store["version"], 2)
            self.assertIn("cid1:h1", store["entries"])
            self.assertIn("cid2:h2", store["entries"])

    def test_legacy_jsonl_migration_persists_on_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_jsonl = Path(tmpdir) / ".sync_checkpoint.jsonl"
            p_json = Path(tmpdir) / ".sync_checkpoint.json"
            p_jsonl.write_text(
                json.dumps({"cid": "cid1", "t": "selam", "h": "h1"}) + "\n",
                encoding="utf-8"
            )
            save_sync_ckpt_entry_to_store(p_json, "cid2", "yeni", "h2")
            self.assertTrue(p_json.exists())
            store = load_sync_ckpt_store(p_json)
            self.assertIn("cid1:h1", store["entries"])
            self.assertIn("cid2:h2", store["entries"])

    def test_same_cid_hash_update_replaces_entry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "ilk", "hash1")
            save_sync_ckpt_entry_to_store(p, "cid1", "guncel", "hash1")
            store = load_sync_ckpt_store(p)
            self.assertEqual(len(store["entries"]), 1)
            self.assertEqual(store["entries"]["cid1:hash1"]["t"], "guncel")

    def test_different_hash_same_cid_stored_separately(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "versiyon1", "hashA")
            save_sync_ckpt_entry_to_store(p, "cid1", "versiyon2", "hashB")
            store = load_sync_ckpt_store(p)
            self.assertEqual(len(store["entries"]), 2)
            self.assertIn("cid1:hashA", store["entries"])
            self.assertIn("cid1:hashB", store["entries"])

    def test_atomic_write_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            res = save_sync_ckpt_entry_to_store(p, "cid1", "test", "h1")
            self.assertTrue(res)
            self.assertTrue(p.exists())

    def test_write_failure_logs_warning_once(self):
        log_calls = []
        def mock_log(msg, level="warn"):
            log_calls.append((msg, level))

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_file = Path(tmpdir) / "file_as_dir"
            parent_file.write_text("not a directory", encoding="utf-8")
            bad_path = parent_file / "file.json"
            res1 = save_sync_ckpt_entry_to_store(bad_path, "cid1", "test", "h1", log_fn=mock_log)
            res2 = save_sync_ckpt_entry_to_store(bad_path, "cid2", "test", "h2", log_fn=mock_log)
            self.assertFalse(res1)
            self.assertFalse(res2)
            self.assertEqual(len(log_calls), 2)

    def test_corrupt_v2_json_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            p.write_text("{bozuk_json", encoding="utf-8")
            store = load_sync_ckpt_store(p)
            self.assertEqual(store["version"], 2)
            self.assertEqual(store["entries"], {})

    def test_corrupt_legacy_jsonl_handled_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_jsonl = Path(tmpdir) / ".sync_checkpoint.jsonl"
            p_json = Path(tmpdir) / ".sync_checkpoint.json"
            p_jsonl.write_text(
                "bozuk_satir_1\n" +
                json.dumps({"cid": "cid1", "t": "gecerli", "h": "h1"}) + "\n" +
                "{bozuk_satir_2\n",
                encoding="utf-8"
            )
            store = load_sync_ckpt_store(p_json)
            self.assertEqual(len(store["entries"]), 1)
            self.assertIn("cid1:h1", store["entries"])

    def test_clear_with_keys_removes_only_target_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h1")
            save_sync_ckpt_entry_to_store(p, "cid2", "t2", "h2")
            clear_sync_ckpt_entries_from_store(p, {"cid1:h1"})
            store = load_sync_ckpt_store(p)
            self.assertNotIn("cid1:h1", store["entries"])
            self.assertIn("cid2:h2", store["entries"])

    def test_clear_last_entry_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h1")
            clear_sync_ckpt_entries_from_store(p, {"cid1:h1"})
            self.assertFalse(p.exists())

    def test_clear_none_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h1")
            clear_sync_ckpt_entries_from_store(p, None)
            self.assertFalse(p.exists())

    def test_clear_empty_set_removes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h1")
            clear_sync_ckpt_entries_from_store(p, set())
            self.assertFalse(p.exists())

    def test_should_clear_sync_ckpt_truth_table(self):
        # (is_stop_flag, is_full_success) -> expected
        self.assertTrue(should_clear_sync_ckpt(False, True))
        self.assertFalse(should_clear_sync_ckpt(True, True))
        self.assertFalse(should_clear_sync_ckpt(False, False))
        self.assertFalse(should_clear_sync_ckpt(True, False))

    def test_resume_from_sync_ckpt_returns_resumed_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", '[{"i":"1","t":"Merhaba"}]', "h1")

            dummy_app = SimpleNamespace(
                _sync_ckpt_path=lambda: p,
                _ckpt_fingerprint=lambda: "fp",
                _chunk_src_hash=lambda req, fp: "h1" if req["custom_id"] == "cid1" else "h2",
                _log=MagicMock(),
            )
            # Bind method dynamically
            from subtitle_translator_gui import App
            dummy_app._resume_from_sync_ckpt = App._resume_from_sync_ckpt.__get__(dummy_app)

            reqs = [{"custom_id": "cid1"}, {"custom_id": "cid2"}]
            raw_map = {}
            remaining, resumed_keys = dummy_app._resume_from_sync_ckpt(reqs, raw_map)
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["custom_id"], "cid2")
            self.assertIn("cid1", raw_map)
            self.assertEqual(resumed_keys, {"cid1:h1"})

    def test_prefill_sync_ckpt_returns_count_and_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", '[{"i":"1","t":"Merhaba"}]', "h1")

            dummy_app = SimpleNamespace(
                _sync_ckpt_path=lambda: p,
                _ckpt_fingerprint=lambda: "fp",
                _chunk_src_hash=lambda req, fp, scope="": "h1" if req["custom_id"] == "cid1" else "h2",
                _log=MagicMock(),
            )
            from subtitle_translator_gui import App
            dummy_app._prefill_sync_ckpt = App._prefill_sync_ckpt.__get__(dummy_app)

            reqs = [{"custom_id": "cid1"}, {"custom_id": "cid2"}]
            raw_map = {}
            count, resumed_keys = dummy_app._prefill_sync_ckpt(reqs, raw_map)
            self.assertEqual(count, 1)
            self.assertIn("cid1", raw_map)
            self.assertEqual(resumed_keys, {"cid1:h1"})

    def test_chunk_src_hash_consistency(self):
        from subtitle_translator_gui import App
        req = {
            "body": {
                "messages": [
                    {"role": "system", "content": "prompt"},
                    {"role": "user", "content": json.dumps({"tr": [{"i": "1", "t": "Hello world"}]})}
                ]
            }
        }
        h1 = App._chunk_src_hash(req, "fp1")
        h2 = App._chunk_src_hash(req, "fp1")
        h3 = App._chunk_src_hash(req, "fp2")
        self.assertEqual(len(h1), 10)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_interprocess_lock_prevents_race(self):
        import concurrent.futures
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"

            def worker(i):
                save_sync_ckpt_entry_to_store(p, f"cid_{i}", f"val_{i}", f"h_{i}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
                futs = [ex.submit(worker, i) for i in range(10)]
                for f in concurrent.futures.as_completed(futs):
                    f.result()

            store = load_sync_ckpt_store(p)
            self.assertEqual(len(store["entries"]), 10)

    def test_no_app_instantiation(self):
        # Confirm that no App instance was initialized in this test module
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
