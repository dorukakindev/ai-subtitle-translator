# -*- coding: utf-8 -*-
"""Checkpoint kaydı depoyu bir kez okuyup bir kez parse eder."""
import inspect
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class TheStoreIsReadOncePerSaveTest(unittest.TestCase):
    """Depo 20 MB'a ulaşmıştı ve her chunk kaydında iki kez okunup iki kez
    parse ediliyordu. JSON parse GIL'i tuttuğu için Tkinter arayüzü o
    sürede çalışamıyor — ölçüm: kayıt başına 0,441 sn, koşu sırasında
    tıklamada donma. Tek okuma/tek parse ile 0,281 sn.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "ckpt.json"
        store = {"version": g.SYNC_CKPT_STORE_VER,
                 "entries": {f"c{i}:h{i}": {"cid": f"c{i}", "h": f"h{i}",
                                            "t": "metin", "updated_at": time.time()}
                             for i in range(20)}}
        self.path.write_text(json.dumps(store), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_a_save_reads_the_file_once(self):
        reads = []
        original = Path.read_text

        def counting(self_path, *args, **kwargs):
            if str(self_path).endswith("ckpt.json"):
                reads.append(str(self_path))
            return original(self_path, *args, **kwargs)

        Path.read_text = counting
        try:
            g.save_sync_ckpt_entry_to_store(self.path, "yeni", "t", "h")
        finally:
            Path.read_text = original
        self.assertEqual(len(reads), 1, f"beklenen 1 okuma, olan {len(reads)}")

    def test_the_entry_is_stored_and_readable(self):
        g.save_sync_ckpt_entry_to_store(self.path, "yeni", "metin", "h")
        store = g.load_sync_ckpt_store(self.path)
        self.assertIn("yeni:h", store["entries"])
        self.assertEqual(store["entries"]["yeni:h"]["t"], "metin")

    def test_the_existing_entries_survive(self):
        g.save_sync_ckpt_entry_to_store(self.path, "yeni", "metin", "h")
        store = g.load_sync_ckpt_store(self.path)
        self.assertEqual(len(store["entries"]), 21)

    def test_a_corrupt_store_is_still_refused(self):
        self.path.write_text("{bozuk", encoding="utf-8")
        self.assertFalse(
            g.save_sync_ckpt_entry_to_store(self.path, "x", "t", "h"))

    def test_the_loader_accepts_preparsed_data(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        store = g.load_sync_ckpt_store(self.path, preloaded_data=data)
        self.assertEqual(len(store["entries"]), 20)

    def test_the_saver_passes_what_the_check_already_parsed(self):
        source = inspect.getsource(g.save_sync_ckpt_entry_to_store)
        self.assertIn("preloaded_data=parsed", source)


if __name__ == "__main__":
    unittest.main()
