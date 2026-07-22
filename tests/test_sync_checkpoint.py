"""
Sync mod çökme kurtarma (per-chunk checkpoint):
- Tamamlanan chunk kaydedilir; aynı işte yeniden API'ye GİTMEZ.
- Kaynak içeriği değişirse (aynı cid) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Model/ayarlar değişirse (parmak izi) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Başarılı koşuda kayıt silinir.
Checkpoint yolu monkeypatch'lenir → gerçek .sync_checkpoint.jsonl'a dokunulmaz.
"""
import json
import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui
from tests._gui_app import make_app


def _req(cid, srcs):
    payload = {"tr": [{"i": i, "t": s} for i, s in enumerate(srcs, 1)]}
    return {"custom_id": cid, "body": {"messages": [{}, {"content": json.dumps(payload)}]}}


class SyncCheckpointTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()
        cls._tmp = tempfile.mkdtemp()
        cls.app._sync_ckpt_path = lambda: Path(cls._tmp) / "ckpt.jsonl"

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def setUp(self):
        self.app._clear_sync_ckpt()

    def _hash(self, req):
        """Kaydetme yolunun kullandığı imza: kaynak + güncel ayar parmak izi."""
        return gui.App._chunk_src_hash(req, self.app._ckpt_fingerprint())

    def test_save_load_roundtrip(self):
        r = _req("c1", ["hello", "world"])
        h = self._hash(r)
        self.app._save_sync_ckpt_entry("c1", "merhaba\ndünya", h)
        d = self.app._load_sync_ckpt()
        self.assertEqual(d["c1"], ("merhaba\ndünya", h))

    def test_resume_skips_matching_chunk(self):
        r = _req("c1", ["hello"])
        self.app._save_sync_ckpt_entry("c1", "merhaba", self._hash(r))
        raw = {}
        remaining = self.app._resume_from_sync_ckpt([r], raw)
        self.assertEqual(remaining, [])              # API'ye gitmeyecek
        self.assertEqual(raw["c1"], "merhaba")

    def test_resume_skips_matching_multiline_chunk(self):
        r = _req("c1", ["hello", "world"])
        self.app._save_sync_ckpt_entry("c1", "merhaba\ndünya", self._hash(r))
        raw = {}
        self.assertEqual(self.app._resume_from_sync_ckpt([r], raw), [])
        self.assertEqual(raw["c1"], "merhaba\ndünya")

    def test_resume_retranslates_on_content_change(self):
        r_old = _req("c1", ["hello"])
        self.app._save_sync_ckpt_entry("c1", "merhaba", self._hash(r_old))
        r_new = _req("c1", ["goodbye"])              # aynı cid, FARKLI içerik
        raw = {}
        remaining = self.app._resume_from_sync_ckpt([r_new], raw)
        self.assertEqual(len(remaining), 1)          # bayat çeviri kullanılmaz → yeniden çevrilir
        self.assertNotIn("c1", raw)

    def test_hash_stable_across_prev_tr_injection(self):
        """prev_tr enjeksiyonu payload'a alan ekler ama 'tr' değişmez → imza aynı
        kalmalı (zincir modunda kurtarma çalışsın diye)."""
        r = _req("c1", ["hello"])
        h1 = self._hash(r)
        pl = json.loads(r["body"]["messages"][1]["content"])
        pl["prev_tr"] = [{"src": "hi", "tr": "selam"}]
        r["body"]["messages"][1]["content"] = json.dumps(pl)
        self.assertEqual(self._hash(r), h1)

    def test_prefill_fills_rawmap_without_filtering(self):
        r = _req("c1", ["hi"])
        self.app._save_sync_ckpt_entry("c1", "selam", self._hash(r))
        raw = {}
        n = self.app._prefill_sync_ckpt([r], raw)
        self.assertEqual(n, 1)
        self.assertEqual(raw["c1"], "selam")

    def test_prefill_scope_prevents_cross_file_reuse(self):
        r = _req("chunk_0", ["Previously on..."])
        fp = self.app._ckpt_fingerprint()
        saved = gui.App._chunk_src_hash(r, fp, scope="A.srt")
        self.app._save_sync_ckpt_entry("chunk_0", "Önceki bölümde...", saved)
        raw = {}
        self.assertEqual(self.app._prefill_sync_ckpt([r], raw, scope="B.srt"), 0)
        self.assertNotIn("chunk_0", raw)

    def test_clear_removes_checkpoint(self):
        self.app._save_sync_ckpt_entry("c1", "x", "h")
        self.app._clear_sync_ckpt()
        self.assertEqual(self.app._load_sync_ckpt(), {})

    def test_corrupt_line_skipped(self):
        p = self.app._sync_ckpt_path()
        p.write_text('{"cid":"c1","t":"ok","h":"h1"}\nNOT JSON\n', encoding="utf-8")
        d = self.app._load_sync_ckpt()
        self.assertEqual(d, {"c1": ("ok", "h1")})    # bozuk satır atlandı


if __name__ == "__main__":
    unittest.main()
