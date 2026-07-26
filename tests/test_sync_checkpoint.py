"""
Sync mod çökme kurtarma (per-chunk checkpoint):
- Tamamlanan chunk kaydedilir; aynı işte yeniden API'ye GİTMEZ.
- Kaynak içeriği değişirse (aynı cid) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Model/ayarlar değişirse (parmak izi) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Başarılı koşuda kayıt silinir.
- App() veya Tkinter penceresi OLUŞTURULMAZ; SimpleNamespace ile test edilir.
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


def _req(cid, srcs):
    payload = {"tr": [{"i": i, "t": s} for i, s in enumerate(srcs, 1)]}
    return {"custom_id": cid, "body": {"messages": [{}, {"content": json.dumps(payload)}]}}


class SyncCheckpointTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.ckpt_path = Path(self.tmpdir.name) / ".sync_checkpoint.json"
        self.fingerprint = "gpt-5.4-mini|tr|off|standard|Otomatik"

        self.app = SimpleNamespace(
            _sync_ckpt_path=lambda: self.ckpt_path,
            _ckpt_fingerprint=lambda: self.fingerprint,
            _chunk_src_hash=gui.App._chunk_src_hash,
            _load_sync_ckpt=lambda: gui.App._load_sync_ckpt(self.app),
            _save_sync_ckpt_entry=lambda cid, text, h: gui.App._save_sync_ckpt_entry(self.app, cid, text, h),
            _clear_sync_ckpt=lambda keys=None: gui.App._clear_sync_ckpt(self.app, keys),
            _log=MagicMock(),
        )
        self.app._resume_from_sync_ckpt = gui.App._resume_from_sync_ckpt.__get__(self.app)
        self.app._prefill_sync_ckpt = gui.App._prefill_sync_ckpt.__get__(self.app)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _hash(self, req, scope=""):
        return gui.App._chunk_src_hash(req, self.fingerprint, scope=scope)

    def test_save_load_roundtrip(self):
        r = _req("c1", ["hello", "world"])
        h = self._hash(r)
        self.app._save_sync_ckpt_entry("c1", "merhaba\ndünya", h)
        d = self.app._load_sync_ckpt()
        key = f"c1:{h}"
        self.assertIn(key, d)
        self.assertEqual(d[key]["t"], "merhaba\ndünya")
        self.assertEqual(d[key]["h"], h)

    def test_resume_skips_matching_chunk(self):
        r = _req("c1", ["hello"])
        h = self._hash(r)
        self.app._save_sync_ckpt_entry("c1", "merhaba", h)
        raw = {}
        remaining, resumed_keys = self.app._resume_from_sync_ckpt([r], raw)
        self.assertEqual(remaining, [])              # API'ye gitmeyecek
        self.assertEqual(raw["c1"], "merhaba")
        self.assertEqual(resumed_keys, {f"c1:{h}"})

    def test_resume_skips_matching_multiline_chunk(self):
        r = _req("c1", ["hello", "world"])
        h = self._hash(r)
        self.app._save_sync_ckpt_entry("c1", "merhaba\ndünya", h)
        raw = {}
        remaining, resumed_keys = self.app._resume_from_sync_ckpt([r], raw)
        self.assertEqual(remaining, [])
        self.assertEqual(raw["c1"], "merhaba\ndünya")
        self.assertEqual(resumed_keys, {f"c1:{h}"})

    def test_resume_retranslates_on_content_change(self):
        r_old = _req("c1", ["hello"])
        h_old = self._hash(r_old)
        self.app._save_sync_ckpt_entry("c1", "merhaba", h_old)
        r_new = _req("c1", ["goodbye"])              # aynı cid, FARKLI içerik
        raw = {}
        remaining, resumed_keys = self.app._resume_from_sync_ckpt([r_new], raw)
        self.assertEqual(len(remaining), 1)          # bayat çeviri kullanılmaz → yeniden çevrilir
        self.assertNotIn("c1", raw)
        self.assertEqual(resumed_keys, set())

    def test_hash_changes_across_prev_tr_injection(self):
        """Zincir bağlamı değişirse bayat checkpoint kullanılmamalı."""
        r = _req("c1", ["hello"])
        h1 = self._hash(r)
        pl = json.loads(r["body"]["messages"][1]["content"])
        pl["prev_tr"] = [{"src": "hi", "tr": "selam"}]
        r["body"]["messages"][1]["content"] = json.dumps(pl)
        self.assertNotEqual(self._hash(r), h1)

    def test_prefill_fills_rawmap_without_filtering(self):
        r = _req("c1", ["hi"])
        h = self._hash(r)
        self.app._save_sync_ckpt_entry("c1", "selam", h)
        raw = {}
        n, resumed_keys = self.app._prefill_sync_ckpt([r], raw)
        self.assertEqual(n, 1)
        self.assertEqual(raw["c1"], "selam")
        self.assertEqual(resumed_keys, {f"c1:{h}"})

    def test_prefill_scope_prevents_cross_file_reuse(self):
        r = _req("chunk_0", ["Previously on..."])
        h = self._hash(r, scope="A.srt")
        self.app._save_sync_ckpt_entry("chunk_0", "Önceki bölümde...", h)
        raw = {}
        n, resumed_keys = self.app._prefill_sync_ckpt([r], raw, scope="B.srt")
        self.assertEqual(n, 0)
        self.assertNotIn("chunk_0", raw)
        self.assertEqual(resumed_keys, set())

    def test_clear_removes_checkpoint(self):
        self.app._save_sync_ckpt_entry("c1", "x", "h")
        self.app._clear_sync_ckpt(None)
        self.assertEqual(self.app._load_sync_ckpt(), {})

    def test_corrupt_line_skipped(self):
        p_jsonl = Path(self.tmpdir.name) / ".sync_checkpoint.jsonl"
        p_jsonl.write_text('{"cid":"c1","t":"ok","h":"h1"}\nNOT JSON\n', encoding="utf-8")
        d = self.app._load_sync_ckpt()
        self.assertIn("c1:h1", d)
        self.assertEqual(d["c1:h1"]["t"], "ok")


if __name__ == "__main__":
    unittest.main()
