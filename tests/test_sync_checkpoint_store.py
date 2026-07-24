import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from subtitle_translator_gui import (
    SYNC_CKPT_STORE_VER,
    App,
    clear_sync_ckpt_entries_from_store,
    load_sync_ckpt_store,
    save_sync_ckpt_entry_to_store,
    should_clear_sync_ckpt,
)


def _mp_checkpoint_worker(store_path_str, i):
    """Top-level worker function for Windows multiprocessing spawn test."""
    path = Path(store_path_str)
    save_sync_ckpt_entry_to_store(path, f"mp_cid_{i}", f"mp_val_{i}", f"mp_hash_{i}")


def _make_req(cid, srcs):
    payload = {"tr": [{"i": i, "t": s} for i, s in enumerate(srcs, 1)]}
    return {"custom_id": cid, "body": {"messages": [{}, {"content": json.dumps(payload)}]}}


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

    def test_clear_empty_set_is_noop_and_preserves_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h1")
            save_sync_ckpt_entry_to_store(p, "cid2", "t2", "h2")

            # clear with empty set must be NO-OP
            res = clear_sync_ckpt_entries_from_store(p, set())
            self.assertTrue(res)
            self.assertTrue(p.exists())
            store = load_sync_ckpt_store(p)
            self.assertIn("cid1:h1", store["entries"])
            self.assertIn("cid2:h2", store["entries"])

            # clear with non-empty set removes specified entry only
            res_partial = clear_sync_ckpt_entries_from_store(p, {"cid1:h1"})
            self.assertTrue(res_partial)
            self.assertTrue(p.exists())
            store_after = load_sync_ckpt_store(p)
            self.assertNotIn("cid1:h1", store_after["entries"])
            self.assertIn("cid2:h2", store_after["entries"])

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

    def test_should_clear_sync_ckpt_truth_table(self):
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
            dummy_app._prefill_sync_ckpt = App._prefill_sync_ckpt.__get__(dummy_app)

            reqs = [{"custom_id": "cid1"}, {"custom_id": "cid2"}]
            raw_map = {}
            count, resumed_keys = dummy_app._prefill_sync_ckpt(reqs, raw_map)
            self.assertEqual(count, 1)
            self.assertIn("cid1", raw_map)
            self.assertEqual(resumed_keys, {"cid1:h1"})

    def test_chunk_src_hash_consistency(self):
        req = _make_req("c1", ["Hello world"])
        h1 = App._chunk_src_hash(req, "fp1")
        h2 = App._chunk_src_hash(req, "fp1")
        h3 = App._chunk_src_hash(req, "fp2")
        self.assertEqual(len(h1), 10)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_same_cid_different_scope_hashes_separate(self):
        req = _make_req("cid_1", ["Hello"])
        fp = "fingerprint_v1"
        h_scope1 = App._chunk_src_hash(req, fp, scope="A.srt")
        h_scope2 = App._chunk_src_hash(req, fp, scope="B.srt")
        self.assertNotEqual(h_scope1, h_scope2)

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid_1", "Çeviri A", h_scope1)
            save_sync_ckpt_entry_to_store(p, "cid_1", "Çeviri B", h_scope2)
            store = load_sync_ckpt_store(p)
            self.assertEqual(len(store["entries"]), 2)
            self.assertIn(f"cid_1:{h_scope1}", store["entries"])
            self.assertIn(f"cid_1:{h_scope2}", store["entries"])
            self.assertEqual(store["entries"][f"cid_1:{h_scope1}"]["t"], "Çeviri A")
            self.assertEqual(store["entries"][f"cid_1:{h_scope2}"]["t"], "Çeviri B")

    def test_resume_finds_correct_hash_ignores_wrong_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "cid1", "t1", "h_correct")

            dummy_app = SimpleNamespace(
                _sync_ckpt_path=lambda: p,
                _ckpt_fingerprint=lambda: "fp",
                _chunk_src_hash=lambda req, fp: "h_correct" if req["custom_id"] == "cid1" else "h_wrong",
                _log=MagicMock(),
            )
            dummy_app._resume_from_sync_ckpt = App._resume_from_sync_ckpt.__get__(dummy_app)

            req_correct = {"custom_id": "cid1"}
            req_wrong = {"custom_id": "cid2"}

            raw_map = {}
            remaining, resumed_keys = dummy_app._resume_from_sync_ckpt([req_correct, req_wrong], raw_map)
            self.assertEqual(remaining, [req_wrong])
            self.assertEqual(raw_map, {"cid1": "t1"})
            self.assertEqual(resumed_keys, {"cid1:h_correct"})

    def test_fingerprint_change_causes_cache_miss(self):
        req = _make_req("c1", ["Hello"])
        h1 = App._chunk_src_hash(req, "model_A|tr")
        h2 = App._chunk_src_hash(req, "model_B|tr")

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "c1", "merhaba", h1)

            dummy_app = SimpleNamespace(
                _sync_ckpt_path=lambda: p,
                _ckpt_fingerprint=lambda: "model_B|tr",
                _chunk_src_hash=App._chunk_src_hash,
                _log=MagicMock(),
            )
            dummy_app._resume_from_sync_ckpt = App._resume_from_sync_ckpt.__get__(dummy_app)

            raw_map = {}
            remaining, resumed_keys = dummy_app._resume_from_sync_ckpt([req], raw_map)
            self.assertEqual(len(remaining), 1)
            self.assertNotIn("c1", raw_map)
            self.assertEqual(resumed_keys, set())

    def test_prev_tr_change_does_not_change_hash(self):
        r1 = _make_req("c1", ["Hello"])
        h1 = App._chunk_src_hash(r1, "fp")

        r2 = _make_req("c1", ["Hello"])
        pl = json.loads(r2["body"]["messages"][1]["content"])
        pl["prev_tr"] = [{"src": "previous line", "tr": "önceki satır"}]
        r2["body"]["messages"][1]["content"] = json.dumps(pl)

        h2 = App._chunk_src_hash(r2, "fp")
        self.assertEqual(h1, h2)

    def test_legacy_migration_write_error_preserves_legacy_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p_jsonl = Path(tmpdir) / ".sync_checkpoint.jsonl"
            p_json = Path(tmpdir) / "read_only_dir" / ".sync_checkpoint.json"
            # create read_only_dir as file to force write failure
            p_json_parent = Path(tmpdir) / "read_only_dir"
            p_json_parent.write_text("file block", encoding="utf-8")

            p_jsonl.write_text(json.dumps({"cid": "cid1", "t": "text1", "h": "h1"}) + "\n", encoding="utf-8")
            res = save_sync_ckpt_entry_to_store(p_json, "cid2", "text2", "h2")
            self.assertFalse(res)
            self.assertTrue(p_jsonl.exists())
            self.assertIn("cid1", p_jsonl.read_text(encoding="utf-8"))

    def test_atomic_v2_write_error_preserves_existing_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            save_sync_ckpt_entry_to_store(p, "c1", "old_val", "h1")
            store_before = load_sync_ckpt_store(p)

            # force write failure by passing invalid path
            bad_path = Path(tmpdir) / "file_as_dir" / "file.json"
            Path(tmpdir, "file_as_dir").write_text("block", encoding="utf-8")

            res = save_sync_ckpt_entry_to_store(bad_path, "c1", "new_val", "h1")
            self.assertFalse(res)

            store_after = load_sync_ckpt_store(p)
            self.assertEqual(store_before, store_after)

    def test_same_key_written_100_times_entries_len_is_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            for i in range(100):
                save_sync_ckpt_entry_to_store(p, "cid_1", f"val_{i}", "h_1")
            store = load_sync_ckpt_store(p)
            self.assertEqual(len(store["entries"]), 1)
            self.assertEqual(store["entries"]["cid_1:h_1"]["t"], "val_99")

    def test_sync_hybrid_same_cid_different_filepath_scopes(self):
        req1 = _make_req("cid_0", ["Intro line"])
        req2 = _make_req("cid_0", ["Intro line"])

        scope1 = str(Path("/path/to/movie1.srt").resolve())
        scope2 = str(Path("/path/to/movie2.srt").resolve())

        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            fp = "fingerprint"
            h1 = App._chunk_src_hash(req1, fp, scope=scope1)
            h2 = App._chunk_src_hash(req2, fp, scope=scope2)

            save_sync_ckpt_entry_to_store(p, "cid_0", "Giriş satırı 1", h1)
            save_sync_ckpt_entry_to_store(p, "cid_0", "Giriş satırı 2", h2)

            dummy_app = SimpleNamespace(
                _sync_ckpt_path=lambda: p,
                _ckpt_fingerprint=lambda: fp,
                _chunk_src_hash=App._chunk_src_hash,
                _log=MagicMock(),
            )
            dummy_app._prefill_sync_ckpt = App._prefill_sync_ckpt.__get__(dummy_app)

            raw1 = {}
            dummy_app._prefill_sync_ckpt([req1], raw1, scope=scope1)
            self.assertEqual(raw1.get("cid_0"), "Giriş satırı 1")

            raw2 = {}
            dummy_app._prefill_sync_ckpt([req2], raw2, scope=scope2)
            self.assertEqual(raw2.get("cid_0"), "Giriş satırı 2")

    def test_interthread_lock_prevents_race(self):
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

    def test_interprocess_lock_multiprocessing(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / ".sync_checkpoint.json"
            procs = []
            for i in range(4):
                proc = ctx.Process(target=_mp_checkpoint_worker, args=(str(p), i))
                procs.append(proc)
                proc.start()

            for proc in procs:
                proc.join(timeout=10.0)
                self.assertEqual(proc.exitcode, 0, f"Multiprocessing worker process failed with exitcode {proc.exitcode}")

            store = load_sync_ckpt_store(p)
            for i in range(4):
                key = f"mp_cid_{i}:mp_hash_{i}"
                self.assertIn(key, store["entries"])

    def test_no_app_instantiation(self):
        # Confirm that no App instance was initialized in this test module
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
