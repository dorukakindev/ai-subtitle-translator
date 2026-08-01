"""İki-Dalgalı Zincirli Batch (B3) — saf yardımcılar + save_results çoklu-id.

TASARIM (bkz. mini-main-model-quality-2026-07 hafızası, B3 kararı): batch API tek
partide çalıştığından tek batch içinde chunk N+1'e chunk N'in ÇEVİRİSİ verilemez. B3
dosyayı iki dalgaya böler; A biter, A'nın kuyruk çevirileri B'nin ilk chunk'ına prev_tr
enjekte edilir. Sync'in N-1 zincir sınırından yalnız 1'ini (dosya ortası) verir — bilinçli
dar kazanç. Bu testler saf çekirdeği kilitler (I/O kabuğu _run_twowave_batches ayrı)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui
import hybrid_translate as ht


def _req(cid, items, with_ctx=True):
    payload = {"tr": [{"i": i, "t": t} for i, t in items]}
    if with_ctx:
        payload["ctx"] = ["önceki satır"]
    return {"custom_id": cid,
            "body": {"messages": [{"role": "system", "content": "S"},
                                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}}


def _fmap(cid, idxs):
    return {cid: [(i, "00:00:01,000", "00:00:02,000") for i in idxs]}


class SplitWavesTest(unittest.TestCase):
    def test_too_few_chunks_no_split(self):
        reqs = [_req("c0", [(1, "a")]), _req("c1", [(2, "b")]), _req("c2", [(3, "c")])]
        wave_a, wave_b = gui._split_waves(reqs)   # 3 < 2*min(2)=4
        self.assertEqual(wave_a, [])
        self.assertEqual(wave_b, reqs)

    def test_splits_near_midpoint_and_concatenation_preserved(self):
        reqs = [_req(f"c{i}", [(i, f"t{i}")]) for i in range(6)]
        wave_a, wave_b = gui._split_waves(reqs)
        self.assertTrue(wave_a and wave_b)
        self.assertEqual(wave_a + wave_b, reqs)          # kayıp/tekrar yok
        # bölme ortaya yakın (2..4 arası)
        self.assertIn(len(wave_a), (2, 3, 4))

    def test_wave_b_first_chunk_has_ctx(self):
        reqs = [_req(f"c{i}", [(i, f"t{i}")]) for i in range(6)]
        wave_a, wave_b = gui._split_waves(reqs)
        self.assertTrue(gui._req_has_ctx(wave_b[0]))

    def test_split_avoids_scene_start_boundary(self):
        # Tam ortadaki chunk (index 3) ctx'siz (sahne başı); bölme ctx'li bir sınıra kaymalı.
        reqs = []
        for i in range(6):
            reqs.append(_req(f"c{i}", [(i, f"t{i}")], with_ctx=(i != 3)))
        wave_a, wave_b = gui._split_waves(reqs)
        self.assertTrue(gui._req_has_ctx(wave_b[0]),
                        "B'nin ilk chunk'ı ctx'li olmalı (enjeksiyon no-op olmasın)")
        self.assertEqual(wave_a + wave_b, reqs)


class ChainWavesTest(unittest.TestCase):
    def test_injects_tail_of_a_into_first_of_b(self):
        wave_a = [_req("c0", [(1, "a"), (2, "b")]), _req("c1", [(3, "c"), (4, "d")])]
        wave_b = [_req("c2", [(5, "e"), (6, "f")])]
        # A'nın SON chunk'ının (c1) ham çevirisi
        raw_a = {"c1": json.dumps([{"i": 3, "t": "Üç"}, {"i": 4, "t": "Dört"}], ensure_ascii=False)}
        fmap = {**_fmap("c0", [1, 2]), **_fmap("c1", [3, 4])}
        out_b = gui._chain_waves(wave_a, wave_b, raw_a, fmap, max_pairs=10)
        payload = json.loads(out_b[0]["body"]["messages"][1]["content"])
        self.assertIn("prev_tr", payload)
        # Kuyruk = A'nın SON chunk'ının çevirileri (3,4), ilk chunk'ınki (1,2) değil
        got = {p["i"]: p["tr"] for p in payload["prev_tr"]}
        self.assertEqual(got, {3: "Üç", 4: "Dört"})

    def test_empty_raw_map_leaves_b_unchanged(self):
        wave_a = [_req("c0", [(1, "a")])]
        wave_b = [_req("c1", [(2, "b")])]
        before = wave_b[0]["body"]["messages"][1]["content"]
        out_b = gui._chain_waves(wave_a, wave_b, {}, _fmap("c0", [1]), max_pairs=10)
        self.assertEqual(out_b[0]["body"]["messages"][1]["content"], before)

    def test_failed_tail_chunk_does_not_inject_older_translation(self):
        wave_a = [_req("c0", [(1, "a")]), _req("c1", [(2, "b")])]
        wave_b = [_req("c2", [(3, "c")])]
        raw_a = {"c0": json.dumps([{"i": 1, "t": "Bir"}], ensure_ascii=False)}
        fmap = {**_fmap("c0", [1]), **_fmap("c1", [2])}
        out_b = gui._chain_waves(wave_a, wave_b, raw_a, fmap, max_pairs=10)
        payload = json.loads(out_b[0]["body"]["messages"][1]["content"])
        self.assertNotIn("prev_tr", payload)

    def test_b_without_ctx_not_injected(self):
        # B'nin ilk chunk'ı ctx'siz → _inject_prev_tr no-op → prev_tr eklenmez.
        wave_a = [_req("c0", [(1, "a")])]
        wave_b = [_req("c1", [(2, "b")], with_ctx=False)]
        raw_a = {"c0": json.dumps([{"i": 1, "t": "Bir"}], ensure_ascii=False)}
        out_b = gui._chain_waves(wave_a, wave_b, raw_a, _fmap("c0", [1]), max_pairs=10)
        payload = json.loads(out_b[0]["body"]["messages"][1]["content"])
        self.assertNotIn("prev_tr", payload)


class RawMapFromContentTest(unittest.TestCase):
    def _line(self, cid, content, error=False, choices_empty=False):
        if error:
            return json.dumps({"custom_id": cid, "error": {"message": "x"}})
        choices = [] if choices_empty else [{"message": {"content": content}, "finish_reason": "stop"}]
        return json.dumps({"custom_id": cid, "response": {"body": {"choices": choices}}})

    def test_parses_multiple_lines(self):
        content = "\n".join([self._line("c0", "A"), self._line("c1", "B")])
        rm = gui._raw_map_from_batch_content(content)
        self.assertEqual(rm, {"c0": "A", "c1": "B"})

    def test_skips_error_empty_and_malformed(self):
        content = "\n".join([
            self._line("c0", "A"),
            self._line("c1", "", error=True),
            self._line("c2", "", choices_empty=True),
            "{bozuk json",
            self._line("c3", "D"),
        ])
        rm = gui._raw_map_from_batch_content(content)
        self.assertEqual(rm, {"c0": "A", "c3": "D"})

    def test_duplicate_custom_id_is_not_used_as_next_wave_context(self):
        content = "\n".join([
            self._line("c0", "Birinci çeviri"),
            self._line("c0", "Çelişkili ikinci çeviri"),
            self._line("c1", "Sağlam"),
        ])
        self.assertEqual(
            gui._raw_map_from_batch_content(content), {"c1": "Sağlam"})


class SaveResultsMultiIdTest(unittest.TestCase):
    """save_results output_file_id LİSTE alınca iki dalganın çıktısını TEK SRT'ye yazar."""

    def _batch_line(self, cid, items):
        arr = json.dumps([{"i": i, "t": t} for i, t in items], ensure_ascii=False)
        return json.dumps({"custom_id": cid, "response": {"body": {
            "choices": [{"message": {"content": arr}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 5},
        }}})

    def test_combined_write_from_two_output_ids(self):
        content_by_id = {
            "outA": self._batch_line("c0", [(1, "Bir"), (2, "İki")]),
            "outB": self._batch_line("c1", [(3, "Üç"), (4, "Dört")]),
        }

        class _Files:
            def content(self, fid):
                return SimpleNamespace(text=content_by_id[fid])

        class _FakeClient:
            files = _Files()

        fmap = {**_fmap("c0", [1, 2]), **_fmap("c1", [3, 4])}
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / "film.srt")
            with patch("openai.OpenAI", return_value=_FakeClient()):
                count, _ = ht.save_results("key", ["outA", "outB"], fmap, out)
            self.assertEqual(count, 4)   # her iki dalganın 4 cue'su da yazıldı
            text = Path(out).read_text(encoding="utf-8")
            for expect in ("Bir", "İki", "Üç", "Dört"):
                self.assertIn(expect, text)

    def test_single_str_id_still_works(self):
        # Geriye uyum: tek str id (eski çağrı biçimi) hâlâ çalışmalı.
        class _Files:
            def content(self, fid):
                return SimpleNamespace(text=json.dumps({"custom_id": "c0", "response": {"body": {
                    "choices": [{"message": {"content": '[{"i":1,"t":"Bir"}]'}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 3}}}}))

        class _FakeClient:
            files = _Files()

        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / "f.srt")
            with patch("openai.OpenAI", return_value=_FakeClient()):
                count, _ = ht.save_results("key", "outA", _fmap("c0", [1]), out)
            self.assertEqual(count, 1)


class TwoWaveStageSafetyTest(unittest.TestCase):
    def test_single_wave_writes_stage_and_keeps_recovery_for_caller(self):
        events = []
        stub = SimpleNamespace(
            _main_api_base_url=lambda: "https://reseller.example/v1",
            _log=lambda *args, **kwargs: None,
            _stop_flag=False,
            _register_batch=lambda *args: events.append(("register", args[0])),
            _unregister_batch=lambda bid: events.append(("unregister", bid)),
            _update_batch_tokens=lambda *args, **kwargs: None,
            _context_lines=20,
            _clear_batch_recovery=lambda ids: events.append(("clear", tuple(ids))),
        )
        reqs = [_req("c0", [(1, "source")])]
        fmap = _fmap("c0", [1])

        with tempfile.TemporaryDirectory() as td:
            final = Path(td) / "film.srt"
            final.write_text("ESKI SAGLAM FINAL", encoding="utf-8")
            stage = Path(td) / ".film.srt.twowave.stage.srt"

            def fake_save(_key, _oid, _fmap, output_path, *_args, **_kwargs):
                Path(output_path).write_text(
                    "1\n00:00:01,000 --> 00:00:02,000\n[HATA]\n\n",
                    encoding="utf-8",
                )
                return 1, 0

            with patch.object(ht, "submit_batch", return_value="batch-1"), \
                    patch.object(ht, "wait_for_batch", return_value="output-1"), \
                    patch.object(ht, "save_results", side_effect=fake_save):
                result = gui.App._run_twowave_batches(
                    stub, "key", reqs, fmap, str(final),
                    "source.srt", td, "film.srt", stage_path=stage)

            self.assertEqual(result, (str(stage), ["batch-1"]))
            self.assertEqual(final.read_text(encoding="utf-8"), "ESKI SAGLAM FINAL")
            self.assertIn("[HATA]", stage.read_text(encoding="utf-8"))
            self.assertFalse(any(event[0] == "clear" for event in events))


if __name__ == "__main__":
    unittest.main()
