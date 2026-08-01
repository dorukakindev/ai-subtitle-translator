"""
Sync mod çökme kurtarma (per-chunk checkpoint):
- Tamamlanan chunk kaydedilir; aynı işte yeniden API'ye GİTMEZ.
- Kaynak içeriği değişirse (aynı cid) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Model/ayarlar değişirse (parmak izi) bayat çeviri KULLANILMAZ → yeniden çevrilir.
- Başarılı koşuda kayıt silinir.
- App() veya Tkinter penceresi OLUŞTURULMAZ; SimpleNamespace ile test edilir.
"""
import json
import inspect
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
        self.stage_path = Path(self.tmpdir.name) / ".sync_stage_checkpoint.json"
        self.fingerprint = "gpt-5.4-mini|tr|off|standard|Otomatik"

        self.app = SimpleNamespace(
            _sync_ckpt_path=lambda: self.ckpt_path,
            _ckpt_fingerprint=lambda: self.fingerprint,
            _chunk_src_hash=gui.App._chunk_src_hash,
            _load_sync_ckpt=lambda: gui.App._load_sync_ckpt(self.app),
            _save_sync_ckpt_entry=lambda cid, text, h: gui.App._save_sync_ckpt_entry(self.app, cid, text, h),
            _clear_sync_ckpt=lambda keys=None: gui.App._clear_sync_ckpt(self.app, keys),
            _log=MagicMock(),
            _active_snapshot={
                "crash_resume": True,
                "resume_origin_run_id": "run-original",
            },
            _sync_stage_ckpt_path=lambda: self.stage_path,
        )
        self.app._resume_from_sync_ckpt = gui.App._resume_from_sync_ckpt.__get__(self.app)
        self.app._prefill_sync_ckpt = gui.App._prefill_sync_ckpt.__get__(self.app)
        self.app._save_sync_stage_ckpt = gui.App._save_sync_stage_ckpt.__get__(self.app)
        self.app._load_sync_stage_ckpt = gui.App._load_sync_stage_ckpt.__get__(self.app)
        self.app._clear_sync_stage_ckpt = gui.App._clear_sync_stage_ckpt.__get__(self.app)

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

    def test_chain_resume_requires_same_previous_translation(self):
        second = _req("c2", ["What did she say?"])
        payload = json.loads(second["body"]["messages"][1]["content"])
        payload["ctx"] = [{"i": 1, "t": "Hello."}]
        second["body"]["messages"][1]["content"] = json.dumps(payload)
        content = second["body"]["messages"][1]["content"]
        second["body"]["messages"][1]["content"] = gui._inject_prev_tr(
            content, [{"i": 1, "tr": "Merhaba."}])
        saved_hash = self._hash(second)
        self.app._save_sync_ckpt_entry("c2", "Ne söyledi?", saved_hash)

        raw = {}
        count, _ = self.app._prefill_sync_ckpt([second], raw)
        self.assertEqual(count, 1)

        changed = _req("c2", ["What did she say?"])
        payload = json.loads(changed["body"]["messages"][1]["content"])
        payload["ctx"] = [{"i": 1, "t": "Hello."}]
        changed["body"]["messages"][1]["content"] = json.dumps(payload)
        changed_content = changed["body"]["messages"][1]["content"]
        changed["body"]["messages"][1]["content"] = gui._inject_prev_tr(
            changed_content, [{"i": 1, "tr": "Selam."}])
        raw = {}
        count, _ = self.app._prefill_sync_ckpt([changed], raw)
        self.assertEqual(count, 0)
        self.assertNotIn("c2", raw)

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

    def test_fingerprint_separates_provider_and_chain_mode(self):
        def var(value):
            return SimpleNamespace(get=lambda: value)

        app = SimpleNamespace(
            _main_model_name=lambda: "gpt-5.4",
            _main_api_base_url=lambda: "https://provider-a.example/v1/",
            tgt_var=var("Turkish"), profanity_var=var("Orta"),
            style_var=var("natural"), content_type_var=var("Film"),
            chain_ctx_var=var(True), _active_snapshot=None,
            _file_language_vars={},
        )
        first = gui.App._ckpt_fingerprint(app)
        app._main_api_base_url = lambda: "https://provider-b.example/v1"
        second = gui.App._ckpt_fingerprint(app)
        app.chain_ctx_var = var(False)
        third = gui.App._ckpt_fingerprint(app)
        self.assertNotEqual(first, second)
        self.assertNotEqual(second, third)

    def test_fingerprint_uses_worker_snapshot_without_tk_reads(self):
        forbidden = MagicMock(side_effect=AssertionError("Tk read"))
        app = SimpleNamespace(
            _main_model_name=lambda: "gpt-5.4",
            _main_api_base_url=lambda: "https://provider.example/v1",
            tgt_var=SimpleNamespace(get=forbidden),
            profanity_var=SimpleNamespace(get=forbidden),
            style_var=SimpleNamespace(get=forbidden),
            content_type_var=SimpleNamespace(get=forbidden),
            chain_ctx_var=SimpleNamespace(get=forbidden),
            _active_snapshot={
                "tgt_lang": "Turkish", "profanity": "Orta",
                "style": "natural", "content_type": "Film",
                "chain_ctx": True, "file_source_languages": {},
            },
        )
        result = gui.App._ckpt_fingerprint(app)
        self.assertIn("https://provider.example/v1", result)
        forbidden.assert_not_called()

    def test_stage_checkpoint_restores_complete_main_translation_on_crash_resume(self):
        raw = {"chunk_0": '[{"i":"1","t":"Merhaba"}]',
               "chunk_25": '[{"i":"2","t":"Dünya"}]'}
        self.assertTrue(self.app._save_sync_stage_ckpt("film.srt", "source-hash", raw))

        restored = self.app._load_sync_stage_ckpt(
            "film.srt", "source-hash", set(raw))

        self.assertEqual(restored, raw)
        self.assertTrue(any(
            "yeniden çevrilmeyecek" in str(call.args[0])
            for call in self.app._log.call_args_list))

    def test_stage_checkpoint_is_not_used_for_manual_rerun(self):
        raw = {"chunk_0": '[{"i":"1","t":"Merhaba"}]'}
        self.app._save_sync_stage_ckpt("film.srt", "source-hash", raw)
        self.app._active_snapshot["crash_resume"] = False

        self.assertEqual(
            self.app._load_sync_stage_ckpt("film.srt", "source-hash", set(raw)), {})

    def test_stage_checkpoint_is_bound_to_original_run(self):
        raw = {"chunk_0": '[{"i":"1","t":"Merhaba"}]'}
        self.app._save_sync_stage_ckpt("film.srt", "source-hash", raw)
        self.app._active_snapshot["resume_origin_run_id"] = "run-new"

        self.assertEqual(
            self.app._load_sync_stage_ckpt(
                "film.srt", "source-hash", set(raw)), {})

    def test_stage_completeness_rejects_missing_or_invalid_response(self):
        requests = [_req("chunk_0", ["Hello"]), _req("chunk_25", ["World"])]
        valid = {
            "chunk_0": '[{"i":"1","t":"Merhaba"}]',
            "chunk_25": '[{"i":"1","t":"Dünya"}]',
        }
        self.assertTrue(gui._sync_stage_is_complete(valid, requests))
        self.assertFalse(gui._sync_stage_is_complete(
            {"chunk_0": valid["chunk_0"]}, requests))
        invalid = dict(valid)
        invalid["chunk_25"] = "not json"
        self.assertFalse(gui._sync_stage_is_complete(invalid, requests))

    def test_stage_checkpoint_rejects_changed_source_or_incomplete_chunk_set(self):
        raw = {"chunk_0": '[{"i":"1","t":"Merhaba"}]'}
        self.app._save_sync_stage_ckpt("film.srt", "source-hash", raw)

        self.assertEqual(
            self.app._load_sync_stage_ckpt("film.srt", "changed", set(raw)), {})
        self.assertEqual(
            self.app._load_sync_stage_ckpt(
                "film.srt", "source-hash", {"chunk_0", "chunk_25"}), {})

    def test_stage_checkpoint_clears_after_successful_delivery(self):
        raw = {"chunk_0": '[{"i":"1","t":"Merhaba"}]'}
        self.app._save_sync_stage_ckpt("film.srt", "source-hash", raw)

        self.assertTrue(self.app._clear_sync_stage_ckpt("film.srt"))
        self.assertEqual(gui.load_sync_stage_store(self.stage_path)["entries"], {})

    def test_hybrid_flow_wires_stage_checkpoint_around_quality_passes(self):
        source = inspect.getsource(gui.App._run_sync_hybrid)

        load_at = source.index("_load_sync_stage_ckpt")
        save_at = source.index("_save_sync_stage_ckpt")
        clear_at = source.rindex("_clear_sync_stage_ckpt")
        quality_at = source.index("critic_pass_with_helper")
        stop_after_main_at = source.index(
            "if self._stop_flag:", save_at)

        self.assertLess(load_at, save_at)
        self.assertLess(save_at, stop_after_main_at)
        self.assertLess(save_at, quality_at)
        self.assertLess(quality_at, clear_at)


if __name__ == "__main__":
    unittest.main()
