# -*- coding: utf-8 -*-
"""Chunk içi sahne kesimleri ve etiket sahipliği.

Ölçümler 208 gerçek kaynak dosya / 6.237 chunk üzerinde yapıldı.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompt_constants as pc
import subtitle_translator_gui as g

NL = chr(10)


def _srt(rows):
    out = []
    for idx, start, end, text in rows:
        out.append("%s%s%s --> %s%s%s%s" % (idx, NL, start, end, NL, text, NL))
    return NL.join(out)


class SceneCutInsideChunkTest(unittest.TestCase):
    """Sahne kesimi yalnız chunk'lar ARASINDA aranıyordu.

    Gerçek ölçüm (chunk=25, ctx=30, lookahead=15, gap=3sn):
    6.237 chunk'ın 1.309'unda (%21) `ctx`, 936'sında (%15) `next_ctx`
    sahne sınırını aşıyordu; 3.614 sahne başlangıcının 1.405'inde (%38,9)
    `prev_scene` birden çok eski sahneyi taşıyordu. Düzeltmeden sonra
    üçü de 0/6.237.
    """

    @staticmethod
    def _ts(seconds):
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return "%02d:%02d:%02d,000" % (h, m, s)

    def _build(self, cue_count, cut_at, tmpdir):
        rows = []
        clock = 0.0
        for i in range(1, cue_count + 1):
            if i in cut_at:
                clock += 30.0          # sahne kesimi
            rows.append((str(i), self._ts(clock), self._ts(clock + 1.5),
                         "Line %d." % i))
            clock += 2.0
        path = os.path.join(tmpdir, "scene.srt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_srt(rows))
        reqs, _fmap = g.build_requests(
            [path], "English", "Turkish", "gpt-5.4",
            chunk_size=5, context_lines=30, lookahead_lines=15,
            scene_gap_sec=3.0)
        return [json.loads(r["body"]["messages"][1]["content"]) for r in reqs]

    def _spans(self, cue_count, cut_at, tmpdir):
        """(payload listesi, id -> (baslangic, bitis))"""
        rows = []
        clock = 0.0
        spans = {}
        for i in range(1, cue_count + 1):
            if i in cut_at:
                clock += 30.0
            spans[str(i)] = (clock, clock + 1.5)
            rows.append((str(i), self._ts(clock), self._ts(clock + 1.5),
                         "Line %d." % i))
            clock += 2.0
        path = os.path.join(tmpdir, "scene.srt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_srt(rows))
        reqs, _fmap = g.build_requests(
            [path], "English", "Turkish", "gpt-5.4",
            chunk_size=5, context_lines=30, lookahead_lines=15,
            scene_gap_sec=3.0)
        payloads = [json.loads(r["body"]["messages"][1]["content"])
                    for r in reqs]
        return payloads, spans

    @staticmethod
    def _crosses(ids, spans):
        prev_end = None
        for i in ids:
            span = spans.get(str(i))
            if span is None:
                prev_end = None
                continue
            if prev_end is not None and (span[0] - prev_end) >= 3.0:
                return True
            prev_end = span[1]
        return False

    def test_no_context_window_ever_crosses_a_cut(self):
        # Kesimleri sikca koy: chunk'layici hepsini sinir olarak kullanamaz,
        # bir kismi zorunlu olarak chunk'in ICINDE kalir.
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            payloads, spans = self._spans(40, {4, 7, 9, 13, 17, 22, 26, 31}, td)
        checked = 0
        for payload in payloads:
            body = [str(x["i"]) for x in payload.get("tr", [])]
            ctx = [str(x["i"]) for x in payload.get("ctx", [])]
            nxt = [str(x["i"]) for x in payload.get("next_ctx", [])]
            ps = [str(x["i"]) for x in payload.get("prev_scene", [])]
            if ctx:
                checked += 1
                self.assertFalse(self._crosses(ctx + body[:1], spans), ctx)
            if nxt:
                checked += 1
                self.assertFalse(self._crosses(body[-1:] + nxt, spans), nxt)
            if ps:
                checked += 1
                self.assertFalse(self._crosses(ps, spans), ps)
        self.assertGreater(checked, 0)

    def test_context_is_still_produced(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            payloads, _spans = self._spans(40, {4, 7, 9, 13, 17, 22, 26, 31}, td)
        self.assertTrue(any(p.get("ctx") for p in payloads))
        self.assertTrue(any(p.get("next_ctx") for p in payloads))

    def test_a_file_without_cuts_is_unchanged(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            payloads = self._build(12, set(), td)
        second = payloads[1]
        ctx_ids = [str(x["i"]) for x in second.get("ctx", [])]
        self.assertEqual(ctx_ids, [str(i) for i in range(1, 6)])

    def test_the_hybrid_twin_has_the_same_reset(self):
        import inspect
        import hybrid_translate as ht
        source = inspect.getsource(ht.build_batch_requests)
        self.assertIn("_ctx_prev_end", source)
        self.assertIn("_nxt_prev_end", source)


class RepairPromptParityTest(unittest.TestCase):
    """`repair_neighbors` yalnız düz sync prompt'unda belgeliydi."""

    def test_the_shared_instruction_documents_it(self):
        self.assertIn("repair_neighbors", pc.JSON_INSTRUCTION)

    def test_a_prompt_without_the_key_list_gets_it(self):
        import inspect
        source = inspect.getsource(g._repair_untranslated_sync)
        self.assertIn('if "Input JSON keys" not in base_sys_prompt:', source)
        self.assertIn("base_sys_prompt += JSON_INSTRUCTION", source)

    def test_the_sync_prompt_is_not_doubled(self):
        prompt = g._build_sync_system_prompt("English", "Turkish")
        self.assertEqual(prompt.count("Input JSON keys"), 1)


class TagRestoreBeforeMergeTest(unittest.TestCase):
    """Birleştirme cue'ları 1..N yeniden numaralandırıyor.

    Etiket geri yükleme cue KİMLİĞİNE göre çalıştığı için manuel
    post-işlemde etiketler yanlış cue'ya taşınıyordu: 208 gerçek dosyanın
    190'ında birleştirme oluyor ve 134.101 cue'nun 9.249'u (%6,9) sonucu
    değişen yanlış etiket alıyordu.
    """

    def test_manual_post_process_restores_before_merging(self):
        import inspect
        source = inspect.getsource(g.App._run_post_process)
        self.assertLess(source.index("_restore_tags_blocks"),
                        source.index("merge_fragmented_cues"))

    def test_the_normal_flows_already_did(self):
        import inspect
        # `_finalize_translation_blocks` restore'u içerir ve dört akışta da
        # cue birleştirmeden ÖNCE çağrılır.
        self.assertIn("_restore_tags_blocks",
                      inspect.getsource(g._finalize_translation_blocks))
        for method in (g.App._run_sync_hybrid, g.App._write_results,
                       g.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertLess(source.index("_finalize_translation_blocks("),
                                source.index("_maybe_merge_cues("))


if __name__ == "__main__":
    unittest.main()
