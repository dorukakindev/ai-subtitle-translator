# -*- coding: utf-8 -*-
"""Ayar yükleme/etiket düzeltmeleri ve checkpoint budaması."""
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


class TheCheckpointStoreIsBoundedTest(unittest.TestCase):
    """Depo hiç budanmıyordu: 11.283 kayıt / 20 MB'a ulaşmıştı ve her chunk
    kaydında bütünüyle yeniden yazıldığı için arayüz donuyordu. Gerçek
    deponun kopyasında ölçüldü: 20,01 MB -> 5,88 MB, kayıt 0,441 -> 0,115 sn.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = Path(self.dir) / "ckpt.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _store(self, entries):
        self.path.write_text(
            json.dumps({"version": g.SYNC_CKPT_STORE_VER, "entries": entries}),
            encoding="utf-8")

    def test_an_old_entry_is_dropped(self):
        old = time.time() - (g.SYNC_CKPT_MAX_AGE_DAYS + 1) * 86400
        entries = {"a:h": {"cid": "a", "h": "h", "t": "t", "updated_at": old}}
        self.assertEqual(g._prune_sync_ckpt_entries(entries), 1)
        self.assertEqual(entries, {})

    def test_a_recent_entry_survives(self):
        entries = {"a:h": {"cid": "a", "h": "h", "t": "t",
                           "updated_at": time.time()}}
        self.assertEqual(g._prune_sync_ckpt_entries(entries), 0)
        self.assertIn("a:h", entries)

    def test_the_count_is_capped_keeping_the_newest(self):
        now = time.time()
        entries = {f"c{i}:h": {"cid": f"c{i}", "h": "h", "t": "t",
                               "updated_at": now - i}
                   for i in range(g.SYNC_CKPT_MAX_ENTRIES + 50)}
        dropped = g._prune_sync_ckpt_entries(entries)
        self.assertEqual(dropped, 50)
        self.assertEqual(len(entries), g.SYNC_CKPT_MAX_ENTRIES)
        self.assertIn("c0:h", entries)          # en yeni
        self.assertNotIn("c3049:h", entries)    # en eski

    def test_a_single_run_never_exceeds_the_cap(self):
        # Tek koşu ~30 chunk üretiyor; sınır bunun çok üstünde olmalı.
        self.assertGreater(g.SYNC_CKPT_MAX_ENTRIES, 1000)

    def test_a_save_prunes_and_keeps_the_new_entry(self):
        old = time.time() - (g.SYNC_CKPT_MAX_AGE_DAYS + 5) * 86400
        self._store({f"x{i}:h": {"cid": f"x{i}", "h": "h", "t": "t",
                                 "updated_at": old} for i in range(5)})
        g.save_sync_ckpt_entry_to_store(self.path, "yeni", "metin", "hh")
        entries = g.load_sync_ckpt_store(self.path)["entries"]
        self.assertIn("yeni:hh", entries)
        self.assertEqual(len(entries), 1)

    def test_pruning_is_reported(self):
        old = time.time() - (g.SYNC_CKPT_MAX_AGE_DAYS + 5) * 86400
        self._store({f"x{i}:h": {"cid": f"x{i}", "h": "h", "t": "t",
                                 "updated_at": old} for i in range(3)})
        seen = []
        g.save_sync_ckpt_entry_to_store(self.path, "y", "m", "h",
                                        log_fn=lambda msg, lvl=None: seen.append(msg))
        self.assertTrue(any("budandı" in m for m in seen), seen)


class SettingsLoadAndLabelsTest(unittest.TestCase):

    def test_an_emptied_external_path_is_honoured(self):
        # Boolean 'kayıtlı false yutulur' hatasının StringVar karşılığı.
        source = inspect.getsource(g.App._load_settings)
        self.assertIn('if "ext_project_path" in d:', source)
        self.assertNotIn('if d.get("ext_project_path"):', source)

    def test_the_report_only_help_matches_the_code(self):
        # Metin Kısaltma/Terim/Cue-fill'i "DURDURMAZ" diyordu; kod üçünü de
        # rapor moduna alıyor ve bu testlerle kilitli.
        source = inspect.getsource(g)
        marker = source.index("Varsayılan güvenli mod")
        window = source[marker:marker + 700]
        self.assertIn("Kısaltma", window)
        self.assertIn("çıktıyı DEĞİŞTİRMEZ", window)
        self.assertNotIn("DURDURMAZ", window)

    def test_the_auto_retry_label_names_its_mode(self):
        source = inspect.getsource(g)
        self.assertIn("otomatik yeniden dene (Anında)", source)

    def test_the_worker_reads_max_retry_from_the_snapshot(self):
        source = inspect.getsource(g)
        self.assertNotIn("max_rounds=self._max_retry", source)
        self.assertIn("max_rounds=_snap_max_retry(self)", source)

    def test_the_accessor_prefers_the_snapshot(self):
        from types import SimpleNamespace
        app = SimpleNamespace(_max_retry=9,
                              _snap_get=lambda key, default=None: 3)
        self.assertEqual(g._snap_max_retry(app), 3)

    def test_the_accessor_falls_back_for_a_stub(self):
        # Eski test taklitleri `_snap_get` tanımlamıyor.
        from types import SimpleNamespace
        self.assertEqual(g._snap_max_retry(SimpleNamespace(_max_retry=7)), 7)



class AbandonedResponseCheckpointsArePrunedTest(unittest.TestCase):
    """Bir namespace ancak koşusu tam başarıyla bitince temizleniyor; yarım
    kalan koşuların klasörü kalıcı oluyordu. Ölçüm: 52 namespace / 9.130
    dosya, 40'ı yedi günden eski. Her API yanıtı buraya fsync'li bir dosya
    yazıyor.
    """

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def _namespace(self, name, age_days):
        ns = self.dir / name
        ns.mkdir()
        entry = ns / "a.json"
        entry.write_text("{}", encoding="utf-8")
        stamp = time.time() - age_days * 86400
        os.utime(entry, (stamp, stamp))
        os.utime(ns, (stamp, stamp))
        return ns

    def test_an_abandoned_namespace_is_removed(self):
        old = self._namespace("eski", g.QUALITY_CKPT_MAX_AGE_DAYS + 5)
        self.assertEqual(g.prune_response_checkpoint_namespaces(self.dir), 1)
        self.assertFalse(old.exists())

    def test_a_live_namespace_survives(self):
        fresh = self._namespace("yeni", 0)
        g.prune_response_checkpoint_namespaces(self.dir)
        self.assertTrue(fresh.exists())

    def test_a_missing_root_is_not_an_error(self):
        self.assertEqual(
            g.prune_response_checkpoint_namespaces(self.dir / "yok"), 0)

    def test_it_runs_at_startup_next_to_log_rotation(self):
        source = inspect.getsource(g)
        marker = source.index("rotate_logs(_log_dir)")
        self.assertIn("prune_response_checkpoint_namespaces",
                      source[marker:marker + 600])

if __name__ == "__main__":
    unittest.main()
