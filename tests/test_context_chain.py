"""
Zincirleme bağlam (prev_tr), ön-bağlam hint'i ve tuple'lı consistency_sweep testleri.
API çağrısı yapan fonksiyonlar test edilmez; sadece saf yardımcılar.
"""
import json
import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _CtkStub(SimpleNamespace):
    def __getattr__(self, name):
        if name.startswith("CTk"):
            return _DummyWidget
        return lambda *args, **kwargs: None


with patch.dict(sys.modules, {
    "customtkinter": _CtkStub(),
    "openai": SimpleNamespace(OpenAI=object),
}):
    import subtitle_translator_gui as gui


class InjectPrevTrTest(unittest.TestCase):
    def _payload(self, with_ctx=True):
        p = {"tr": [{"i": 10, "t": "Hello there.", "d": 2.0}]}
        if with_ctx:
            p["ctx"] = [{"i": 9, "t": "Previous line."}]
        return json.dumps(p, ensure_ascii=False)

    def test_injects_prev_tr_when_ctx_present(self):
        pairs = [{"i": 9, "tr": "Önceki satır."}]
        out = json.loads(gui._inject_prev_tr(self._payload(), pairs))
        self.assertEqual(out["prev_tr"], pairs)

    def test_skips_injection_on_scene_break(self):
        # ctx yoksa sahne sınırıdır — çeviri bağlamı da taşınmamalı
        content = self._payload(with_ctx=False)
        pairs = [{"i": 9, "tr": "y"}]
        self.assertEqual(gui._inject_prev_tr(content, pairs), content)

    def test_empty_pairs_returns_unchanged(self):
        content = self._payload()
        self.assertEqual(gui._inject_prev_tr(content, []), content)

    def test_trims_to_max_pairs(self):
        pairs = [{"i": n, "tr": f"t{n}"} for n in range(20)]
        payload = {"tr": [{"i": 20, "t": "Now."}],
                   "ctx": [{"i": n, "t": f"s{n}"} for n in range(20)]}
        out = json.loads(gui._inject_prev_tr(
            json.dumps(payload), pairs, max_pairs=5))
        self.assertEqual(len(out["prev_tr"]), 5)
        self.assertEqual(out["prev_tr"][-1]["i"], 19)  # en son satırlar korunur

    def test_filters_stale_pairs_not_present_in_source_context(self):
        pairs = [
            {"i": 8, "tr": "Eski sahne."},
            {"i": 9, "tr": "Önceki satır."},
            {"i": 10, "tr": "Yanlış gelecek satır."},
        ]
        out = json.loads(gui._inject_prev_tr(self._payload(), pairs))
        self.assertEqual(out["prev_tr"], [{"i": 9, "tr": "Önceki satır."}])

    def test_rejects_invalid_chain_pairs(self):
        pairs = [
            {"i": 9, "tr": 123},
            {"i": 9, "tr": "[HATA]"},
            "bad",
        ]
        content = self._payload()
        self.assertEqual(gui._inject_prev_tr(content, pairs), content)

    def test_skips_unresolved_translation_marker(self):
        content = self._payload()
        pairs = [{"i": 9, "tr": "[ÇEVİRİ EKSİK]"}]
        self.assertEqual(gui._inject_prev_tr(content, pairs), content)

    def test_invalid_json_returns_unchanged(self):
        self.assertEqual(gui._inject_prev_tr("not json", [{"i": 1}]), "not json")


class BuildRequestsBlockCacheTest(unittest.TestCase):
    SRT = ("1\n00:00:01,000 --> 00:00:02,000\nHello.\n\n"
           "2\n00:00:02,100 --> 00:00:03,000\nWorld.\n")

    def _write(self):
        import os
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        from pathlib import Path
        Path(fp).write_text(self.SRT, encoding="utf-8")
        return fp

    def test_block_cache_skips_parse(self):
        import os
        fp = self._write()
        try:
            cached = list(gui.parse_subtitle(fp))
            orig = gui.parse_subtitle
            calls = [0]
            def spy(p):
                calls[0] += 1
                return orig(p)
            gui.parse_subtitle = spy
            try:
                reqs, _ = gui.build_requests([fp], "English", "Turkish",
                                             "gpt-4.1-mini", block_cache={fp: cached})
                self.assertEqual(calls[0], 0, "cache varken parse edildi")
                self.assertGreaterEqual(len(reqs), 1)
            finally:
                gui.parse_subtitle = orig
        finally:
            os.unlink(fp)

    def test_no_cache_parses(self):
        import os
        fp = self._write()
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-4.1-mini")
            self.assertGreaterEqual(len(reqs), 1)
        finally:
            os.unlink(fp)

    def test_gui_build_requests_injects_scene_context(self):
        import os
        fp = self._write()
        try:
            reqs, _ = gui.build_requests(
                [fp],
                "English",
                "Turkish",
                "gpt-4.1-mini",
                scene_emotions=[{"start": "1", "end": "2", "arc": "customer asks casually; tone is light"}],
            )
            payload = json.loads(reqs[0]["body"]["messages"][1]["content"])
            # Eski (legacy) tek-satır 'arc' şekli — 'summary' yoksa 'tone' alanına düşer.
            self.assertEqual(
                payload["scene"][0]["tone"],
                "customer asks casually; tone is light",
            )
        finally:
            os.unlink(fp)

    def test_quality_context_defaults_are_larger(self):
        # 2026-07-09: chunk/context/lookahead küçültüldü (desync azaltma —
        # bkz. fable5-planning-protocol / mini-main-model-quality hafızası).
        # Test'in amacı DEĞİŞMEDİ: gui.py ile hybrid_translate.py'nin kopyaları
        # SENKRON kalmalı — yalnızca hedef değerler güncellendi.
        self.assertEqual(gui.CONTEXT_LINES, 30)
        self.assertEqual(gui.LOOKAHEAD_LINES, 15)
        self.assertEqual(ht.CONTEXT_LINES, 30)
        self.assertEqual(ht.LOOKAHEAD_LINES, 15)


class ChainPairsFromResultTest(unittest.TestCase):
    def test_builds_pairs_and_skips_hata(self):
        content = json.dumps({"tr": [
            {"i": 1, "t": "One."}, {"i": 2, "t": "Two."}, {"i": 3, "t": "Three."}]})
        tmap = {"1": "Bir.", "2": "[HATA]"}  # 3 hiç yok
        pairs = gui._chain_pairs_from_result(content, tmap)
        self.assertEqual(pairs, [{"i": 1, "tr": "Bir."}])

    def test_invalid_json_returns_empty(self):
        self.assertEqual(gui._chain_pairs_from_result("garbage", {"1": "Bir."}), [])

    def test_extend_keeps_rolling_accepted_translations(self):
        first = [{"i": i, "tr": f"ilk-{i}"} for i in range(1, 11)]
        second = [{"i": i, "tr": f"ikinci-{i}"} for i in range(11, 21)]
        pairs = gui._extend_chain_pairs(first, second, max_pairs=15)
        self.assertEqual([pair["i"] for pair in pairs], list(range(6, 21)))
        self.assertEqual(pairs[-1]["tr"], "ikinci-20")

    def test_failed_chunk_keeps_older_pairs_for_the_next_context(self):
        # İkinci chunk ağ/sağlayıcı hatasıyla hiç sonuç vermediyse, üçüncü
        # chunk'ın ctx'sinde kalan ilk chunk çevirisi kaybolmamalı.
        previous = [{"i": 1, "tr": "Önceki sağlam çeviri."}]
        carried = gui._extend_chain_pairs(previous, [], max_pairs=30)
        content = json.dumps({
            "tr": [{"i": 3, "t": "Current line."}],
            "ctx": [{"i": 1, "t": "Earlier."}, {"i": 2, "t": "Failed."}],
        }, ensure_ascii=False)
        payload = json.loads(gui._inject_prev_tr(content, carried, max_pairs=30))
        self.assertEqual(payload["prev_tr"], previous)


class ChainRecoveryOrderTest(unittest.TestCase):
    def test_sync_and_hybrid_inject_chain_context_before_reused_raw_can_retry(self):
        # Checkpoint/TM'den gelen hatalı ham yanıt tekrar denenecekse, retry
        # aynı scene'deki önceki çevirileri görmelidir.
        sync_source = inspect.getsource(gui.App._run_sync)
        sync_chain = sync_source[sync_source.index("def chain_file"):]
        self.assertLess(
            sync_chain.index('user_msg["content"] = _inject_prev_tr'),
            sync_chain.index("if cid not in api_ids"),
        )

        hybrid_source = inspect.getsource(gui.App._run_sync_hybrid)
        hybrid_chain = hybrid_source[hybrid_source.index("if App._run_setting(self, \"chain_ctx\""):]
        self.assertLess(
            hybrid_chain.index('user_msg["content"] = _inject_prev_tr'),
            hybrid_chain.index("if cid_hint in raw_map"),
        )

    def test_report_only_owner_warning_still_feeds_prev_translation(self):
        req = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [{"i": 1, "t": "Hello."}]
        })}]}}
        with patch.object(
                gui, "_chunk_response_retry_reason",
                return_value="cue_content_owner_mismatch"):
            pairs = gui._chain_pairs_from_chunk_response(
                req, '[{"i":1,"t":"Merhaba."}]',
                [(1, "00:00:00,000 --> 00:00:01,000", "source.srt")])
        self.assertEqual(pairs, [{"i": 1, "tr": "Merhaba."}])
        self.assertNotIn("_chain_break_reason", req)

    def test_owner_mismatched_translation_does_not_feed_chain(self):
        req = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [
                {"i": 1, "t": "Alpha says hello."},
                {"i": 2, "t": "Bravo says hello."},
            ]
        })}]}}
        raw = json.dumps([
            {"i": 1, "t": "Bravo diyor."},
            {"i": 2, "t": "Bravo diyor."},
        ])
        pairs = gui._chain_pairs_from_chunk_response(
            req, raw,
            [(1, "00:00:00,000 --> 00:00:01,000", "source.srt"),
             (2, "00:00:01,000 --> 00:00:02,000", "source.srt")])
        self.assertEqual(pairs, [{"i": 2, "tr": "Bravo diyor."}])
        self.assertNotIn("_chain_break_reason", req)

    def test_real_invalid_response_is_recorded_as_chain_break(self):
        req = {"body": {"messages": [{}, {"role": "user", "content": "{}"}]}}
        with patch.object(
                gui, "_chunk_response_retry_reason", return_value="empty_dialogue"):
            pairs = gui._chain_pairs_from_chunk_response(req, "[]", [])
        self.assertEqual(pairs, [])
        self.assertEqual(req["_chain_break_reason"], "empty_dialogue")

    def test_chain_rejects_non_string_translation(self):
        req = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [{"i": 1, "t": "Hello."}]
        })}]}}
        self.assertEqual(
            gui._chunk_response_retry_reason('[{"i":1,"t":123}]', req),
            "invalid_text_type",
        )

    def test_chain_rejects_missing_dialogue_id(self):
        req = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [{"i": 1, "t": "Hello."}, {"i": 2, "t": "World."}]
        })}]}}
        self.assertEqual(
            gui._chunk_response_retry_reason('[{"i":1,"t":"Merhaba."}]', req),
            "id_integrity",
        )


class BuildPrecontextHintTest(unittest.TestCase):
    def test_full_data_renders_all_sections(self):
        data = {
            "summary": "A detective hunts a killer.",
            "tone": "dark thriller",
            "characters": [{"name": "Sam", "role": "detective", "style": "blunt, informal"}],
            "address_map": [{"a": "Sam", "b": "Chief", "register": "siz"}],
            "terms": {"the Precinct": "Karakol"},
        }
        hint = gui.build_precontext_hint(data)
        self.assertIn("FILE PRE-ANALYSIS", hint)
        self.assertIn("A detective hunts a killer.", hint)
        self.assertIn("dark thriller", hint)
        self.assertIn("- Sam (detective): speaks blunt, informal", hint)
        self.assertIn("- Sam → Chief: 'siz'", hint)
        self.assertIn("'the Precinct' → 'Karakol'", hint)

    def test_empty_data_returns_empty_string(self):
        self.assertEqual(gui.build_precontext_hint({}), "")
        self.assertEqual(gui.build_precontext_hint(None), "")

    def test_malformed_entries_are_skipped(self):
        data = {"characters": ["not a dict", {"role": "no name"}],
                "address_map": [{"a": "X"}],
                "terms": {"": "bos", "ok": ""}}
        # Hiç geçerli içerik yok → başlık tek başına kalır → boş dönmeli
        self.assertEqual(gui.build_precontext_hint(data), "")


class SrcMapFromCuesTest(unittest.TestCase):
    def test_tuple_cues(self):
        cues = [("1", "00:00:01,000 --> 00:00:02,000", "<i>Hello.</i>")]
        self.assertEqual(gui._src_map_from_cues(cues), {"1": "Hello."})

    def test_object_cues(self):
        class Cue:
            def __init__(self, index, text):
                self.index, self.text = index, text
        self.assertEqual(gui._src_map_from_cues([Cue(5, "Hi.")]), {"5": "Hi."})

    def test_empty_and_none(self):
        self.assertEqual(gui._src_map_from_cues(None), {})
        self.assertEqual(gui._src_map_from_cues([]), {})


class ConsistencySweepTupleTest(unittest.TestCase):
    def test_accepts_tuple_cues_and_preserves_unverified_paraphrase(self):
        ts = "00:00:01,000 --> 00:00:02,000"
        cues = [
            ("1", ts, "I will be back soon."),
            ("2", ts, "Something else entirely."),
            ("3", ts, "I will be back soon."),
            ("4", ts, "I will be back soon."),
        ]
        tr_blocks = [
            ("1", ts, "Yakında dönerim."),
            ("2", ts, "Tamamen başka bir şey."),
            ("3", ts, "Yakında dönerim."),
            ("4", ts, "Birazdan geri geleceğim."),
        ]
        fixed, n = ht.consistency_sweep(cues, tr_blocks)
        self.assertEqual(n, 0)
        self.assertEqual(fixed[3][2], "Birazdan geri geleceğim.")

    def test_no_majority_no_change(self):
        ts = "00:00:01,000 --> 00:00:02,000"
        cues = [("1", ts, "See you next time."), ("2", ts, "See you next time.")]
        tr_blocks = [("1", ts, "Sonra görüşürüz."), ("2", ts, "Bir dahakine görüşürüz.")]
        fixed, n = ht.consistency_sweep(cues, tr_blocks)
        self.assertEqual(n, 0)
        self.assertEqual([b[2] for b in fixed],
                         ["Sonra görüşürüz.", "Bir dahakine görüşürüz."])

    def test_adjustable_threshold_and_min_words_allow_two_word_source(self):
        ts = "00:00:01,000 --> 00:00:02,000"
        cues = [
            ("1", ts, "Come back."),
            ("2", ts, "Come back."),
            ("3", ts, "Come back."),
            ("4", ts, "Come back."),
            ("5", ts, "Come back."),
        ]
        tr_blocks = [
            ("1", ts, "Geri gel."),
            ("2", ts, "Geri gel."),
            ("3", ts, "Geri gel."),
            ("4", ts, "Dön."),
            ("5", ts, "Dön."),
        ]

        default_fixed, default_n = ht.consistency_sweep(cues, tr_blocks)
        self.assertEqual(default_n, 0)
        self.assertEqual(default_fixed[3][2], "Dön.")

        tuned_fixed, tuned_n = ht.consistency_sweep(
            cues,
            tr_blocks,
            minority_threshold=0.4,
            min_words=2,
        )
        self.assertEqual(tuned_n, 2)
        self.assertEqual([b[2] for b in tuned_fixed], ["Geri gel."] * 5)


class EllipsisFragmentGuiTest(unittest.TestCase):
    TS = "00:00:01,000 --> 00:00:02,000"

    def _tags(self, *texts):
        blocks = [(str(i + 1), self.TS, t) for i, t in enumerate(texts)]
        return gui._tag_fragments_gui(blocks)

    def test_ellipsis_pair_is_fragment_group(self):
        # 'Düşünüyordum...' / '...dün olanları.' → tek cümle olarak gruplanmalı
        tags = self._tags("I was thinking...", "...about what you said.")
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags["2"], "end")

    def test_ellipsis_then_lowercase_is_fragment_group(self):
        tags = self._tags("Wait...", "what do you mean?")
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags["2"], "end")

    def test_ellipsis_then_uppercase_stays_standalone(self):
        # Sonraki satır büyük harfle başlıyorsa yeni cümledir — gruplanmaz
        tags = self._tags("I was thinking...", "Anyway, forget it.")
        self.assertEqual(tags["1"], "none")
        self.assertEqual(tags["2"], "none")

    def test_plain_continuation_still_works(self):
        tags = self._tags("You can only leave this island,",
                          "as the strongest one",
                          "alive.")
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags["2"], "mid")
        self.assertEqual(tags["3"], "end")

    def test_trailing_quote_after_ellipsis(self):
        tags = self._tags('"I was thinking..."', "...about leaving.")
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags["2"], "end")

    def test_closing_parenthesis_preserves_sentence_boundary(self):
        tags = self._tags("(Is that true?)", "Yes.")
        self.assertEqual(tags["1"], "none")
        self.assertEqual(tags["2"], "none")


class EllipsisFragmentHybridTest(unittest.TestCase):
    class Cue:
        def __init__(self, index, text):
            self.index, self.text = index, text

    def _tags(self, *texts):
        cues = [self.Cue(i + 1, t) for i, t in enumerate(texts)]
        return ht._tag_fragments(cues)

    def test_ellipsis_pair_is_fragment_group(self):
        tags = self._tags("I was thinking...", "...about what you said.")
        self.assertEqual(tags[1], "start")
        self.assertEqual(tags[2], "end")

    def test_ellipsis_then_uppercase_stays_standalone(self):
        tags = self._tags("I was thinking...", "Anyway, forget it.")
        self.assertEqual(tags[1], "none")
        self.assertEqual(tags[2], "none")

    def test_three_line_ellipsis_chain(self):
        tags = self._tags("If we don't leave now...",
                          "...before the storm hits...",
                          "...we will never make it.")
        self.assertEqual(tags[1], "start")
        self.assertEqual(tags[2], "mid")
        self.assertEqual(tags[3], "end")

    def test_closing_parenthesis_preserves_sentence_boundary(self):
        tags = self._tags("(Is that true?)", "Yes.")
        self.assertEqual(tags[1], "none")
        self.assertEqual(tags[2], "none")


class FragmentSyntaxHintPayloadTest(unittest.TestCase):
    SRT = (
        "1\n00:00:01,000 --> 00:00:02,000\nYou can only leave this island,\n\n"
        "2\n00:00:02,100 --> 00:00:03,000\nas the strongest one\n\n"
        "3\n00:00:03,100 --> 00:00:04,000\nalive.\n\n"
        "4\n00:00:04,100 --> 00:00:05,000\nOkay.\n"
    )

    def test_gui_build_requests_compacts_fragment_payload(self):
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        Path(fp).write_text(self.SRT, encoding="utf-8")
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish", "gpt-5.4-mini")
            payload = json.loads(reqs[0]["body"]["messages"][1]["content"])
            items = payload["tr"]
            self.assertEqual([it.get("frag") for it in items[:3]], ["start", "mid", "end"])
            self.assertEqual([it.get("frag_group") for it in items[:3]], ["fg_1_3"] * 3)
            self.assertEqual(payload["sentence_groups"][0]["id"], "fg_1_3")
            self.assertEqual(payload["sentence_groups"][0]["items"], ["1", "2", "3"])
            self.assertNotIn("source_sentence", payload["sentence_groups"][0])
            self.assertNotIn("syntax_hint", items[0])
            self.assertNotIn("syntax_hint", items[1])
            self.assertNotIn("syntax_hint", items[2])
            self.assertNotIn("syntax_hint", items[3])
        finally:
            os.unlink(fp)

    class Cue:
        def __init__(self, index, start, end, text):
            self.index = index
            self.start = start
            self.end = end
            self.text = text

    def test_hybrid_build_batch_requests_compacts_fragment_payload(self):
        cues = [
            self.Cue(1, "00:00:01,000", "00:00:02,000", "You can only leave this island,"),
            self.Cue(2, "00:00:02,100", "00:00:03,000", "as the strongest one"),
            self.Cue(3, "00:00:03,100", "00:00:04,000", "alive."),
            self.Cue(4, "00:00:04,100", "00:00:05,000", "Okay."),
        ]
        reqs, _ = ht.build_batch_requests(cues, "system", "gpt-5.4-mini")
        payload = json.loads(reqs[0]["body"]["messages"][1]["content"])
        items = payload["tr"]
        self.assertEqual([it.get("frag") for it in items[:3]], ["start", "mid", "end"])
        self.assertEqual([it.get("frag_group") for it in items[:3]], ["fg_1_3"] * 3)
        self.assertEqual(payload["sentence_groups"][0]["id"], "fg_1_3")
        self.assertEqual(payload["sentence_groups"][0]["items"], [1, 2, 3])
        self.assertNotIn("source_sentence", payload["sentence_groups"][0])
        self.assertNotIn("syntax_hint", items[0])
        self.assertNotIn("syntax_hint", items[1])
        self.assertNotIn("syntax_hint", items[2])
        self.assertNotIn("syntax_hint", items[3])

    def test_hybrid_duration_is_clamped_for_invalid_timestamps(self):
        cues = [
            self.Cue(1, "00:00:02,000", "00:00:02,000", "Still here."),
            self.Cue(2, "00:00:04,000", "00:00:03,000", "Backwards."),
        ]
        reqs, _ = ht.build_batch_requests(cues, "system", "gpt-5.4-mini")
        payload = json.loads(reqs[0]["body"]["messages"][1]["content"])
        self.assertTrue(all(item["d"] >= 0.5 for item in payload["tr"]))

    def test_dialogue_dash_starts_a_new_fragment_boundary(self):
        cues = [
            self.Cue(1, "00:00:01,000", "00:00:02,000", "- Take the road"),
            self.Cue(2, "00:00:02,100", "00:00:03,000", "- No!"),
        ]
        self.assertEqual(ht._tag_fragments(cues), {1: "none", 2: "none"})
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "- Take the road"),
            (2, "00:00:02,100 --> 00:00:03,000", "- No!"),
        ]
        self.assertEqual(gui._tag_fragments_gui(blocks), {1: "none", 2: "none"})

    def test_gui_build_requests_respects_context_and_lookahead_params(self):
        srt = "".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\nLine {i}.\n\n"
            for i in range(1, 6)
        )
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        Path(fp).write_text(srt, encoding="utf-8")
        try:
            reqs, _ = gui.build_requests(
                [fp],
                "English",
                "Turkish",
                "gpt-4.1-mini",
                chunk_size=2,
                context_lines=1,
                lookahead_lines=1,
            )
            first = json.loads(reqs[0]["body"]["messages"][1]["content"])
            second = json.loads(reqs[1]["body"]["messages"][1]["content"])
            self.assertEqual([it["i"] for it in first["next_ctx"]], ["3"])
            self.assertEqual([it["i"] for it in second["ctx"]], ["2"])
            self.assertEqual([it["i"] for it in second["next_ctx"]], ["5"])
        finally:
            os.unlink(fp)

    def test_hybrid_build_batch_requests_respects_context_and_lookahead_params(self):
        cues = [
            self.Cue(i, f"00:00:{i:02d},000", f"00:00:{i:02d},900", f"Line {i}.")
            for i in range(1, 6)
        ]
        reqs, _ = ht.build_batch_requests(
            cues,
            "system",
            "gpt-4.1-mini",
            chunk_size=2,
            context_lines=1,
            lookahead_lines=1,
        )
        first = json.loads(reqs[0]["body"]["messages"][1]["content"])
        second = json.loads(reqs[1]["body"]["messages"][1]["content"])
        self.assertEqual([it["i"] for it in first["next_ctx"]], [3])
        self.assertEqual([it["i"] for it in second["ctx"]], [2])
        self.assertEqual([it["i"] for it in second["next_ctx"]], [5])

    def test_gui_context_window_rolls_across_small_chunks(self):
        srt = "".join(
            f"{i}\n00:00:{i:02d},000 --> 00:00:{i:02d},900\nLine {i}.\n\n"
            for i in range(1, 36)
        )
        fd, fp = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        Path(fp).write_text(srt, encoding="utf-8")
        try:
            reqs, _ = gui.build_requests(
                [fp], "English", "Turkish", "gpt-4.1-mini",
                chunk_size=10, context_lines=30, lookahead_lines=0)
            fourth = json.loads(reqs[3]["body"]["messages"][1]["content"])
            self.assertEqual(
                [item["i"] for item in fourth["ctx"]],
                [str(i) for i in range(1, 31)])
        finally:
            os.unlink(fp)

    def test_hybrid_context_window_rolls_across_small_chunks(self):
        cues = [
            self.Cue(i, f"00:00:{i:02d},000", f"00:00:{i:02d},900", f"Line {i}.")
            for i in range(1, 36)
        ]
        reqs, _ = ht.build_batch_requests(
            cues, "system", "gpt-4.1-mini",
            chunk_size=10, context_lines=30, lookahead_lines=0)
        fourth = json.loads(reqs[3]["body"]["messages"][1]["content"])
        self.assertEqual(
            [item["i"] for item in fourth["ctx"]], list(range(1, 31)))

    def test_hybrid_chain_context_does_not_inject_contextless_tm_text(self):
        class TM:
            def __init__(self):
                self.lookups = 0

            def lookup(self, *_args, **_kwargs):
                self.lookups += 1
                return "Eski bağlamsız çeviri"

            def fuzzy_lookup(self, *_args, **_kwargs):
                return None

            def record_hit(self):
                pass

        cues = [
            self.Cue(i, f"00:00:{i:02d},000", f"00:00:{i:02d},900", f"Line {i}.")
            for i in range(1, 5)
        ]
        tm = TM()
        reqs, _ = ht.build_batch_requests(
            cues, "system", "gpt-5.4-mini", chunk_size=2,
            context_lines=1, tm=tm, use_tm_context=False)
        second = json.loads(reqs[1]["body"]["messages"][1]["content"])
        self.assertNotIn("tr", second["ctx"][0])
        self.assertEqual(tm.lookups, 0)


def _mk_ts(start_s: float, end_s: float) -> str:
    def f(sec):
        h = int(sec // 3600)
        m = int(sec % 3600 // 60)
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
    return f"{f(start_s)} --> {f(end_s)}"


class SceneAlignedChunkGuiTest(unittest.TestCase):
    def _blocks(self, n, gap_after=None, gap=10.0):
        """n blok; gap_after verilirse o bloktan sonra 'gap' saniyelik sahne boşluğu."""
        blocks, t = [], 0.0
        for i in range(1, n + 1):
            blocks.append((str(i), _mk_ts(t, t + 1.5), f"Line {i}."))
            t += 2.0
            if gap_after is not None and i == gap_after:
                t += gap
        return blocks

    def test_cut_lands_on_scene_break(self):
        # 12 blok, chunk hedefi 5 — 7. bloktan sonra sahne boşluğu var (±5 pencerede)
        blocks = self._blocks(12, gap_after=7)
        chunks = gui._make_smart_chunks_gui(blocks, 5)
        # İlk chunk sahne sınırında bitmeli: 7 blok (1..7)
        self.assertEqual(len(chunks[0]), 7)
        self.assertEqual(chunks[0][-1][0], "7")
        self.assertEqual(chunks[1][0][0], "8")

    def test_no_scene_break_falls_back_to_sentence(self):
        blocks = self._blocks(12)  # boşluk yok
        chunks = gui._make_smart_chunks_gui(blocks, 5)
        # Her satır nokta ile bittiği için hedef boyutta kesilir
        self.assertEqual(len(chunks[0]), 5)

    def test_all_blocks_preserved(self):
        blocks = self._blocks(23, gap_after=11)
        chunks = gui._make_smart_chunks_gui(blocks, 5)
        flat = [b[0] for c in chunks for b in c]
        self.assertEqual(flat, [str(i) for i in range(1, 24)])

    def test_scene_gap_breaks_fragment_group_even_without_punctuation(self):
        blocks = [
            ("1", _mk_ts(0.0, 1.0), "The first clause"),
            ("2", _mk_ts(8.0, 9.0), "continues grammatically."),
        ]
        grouped = gui._tag_fragments_gui(blocks, scene_gap_sec=30.0)
        broken = gui._tag_fragments_gui(blocks, scene_gap_sec=3.0)
        self.assertEqual([grouped["1"], grouped["2"]], ["start", "end"])
        self.assertEqual([broken["1"], broken["2"]], ["none", "none"])

    def test_scene_aligned_cut_keeps_late_fragment_group_whole(self):
        blocks = self._blocks(40, gap_after=30)
        tags = {block[0]: "none" for block in blocks}
        for cue_id in range(28, 38):
            tags[str(cue_id)] = (
                "start" if cue_id == 28 else "end" if cue_id == 37 else "mid")
        chunks = gui._make_smart_chunks_gui(blocks, 25, frag_tags=tags)
        first_ids = {block[0] for block in chunks[0]}
        self.assertTrue({str(i) for i in range(28, 38)}.issubset(first_ids))


class SceneAlignedChunkHybridTest(unittest.TestCase):
    class Cue:
        def __init__(self, index, start_s, end_s, text):
            self.index = index
            self.text  = text
            def f(sec):
                h = int(sec // 3600)
                m = int(sec % 3600 // 60)
                s = sec % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
            self.start = f(start_s)
            self.end   = f(end_s)

    def _cues(self, n, gap_after=None, gap=10.0):
        cues, t = [], 0.0
        for i in range(1, n + 1):
            cues.append(self.Cue(i, t, t + 1.5, f"Line {i}."))
            t += 2.0
            if gap_after is not None and i == gap_after:
                t += gap
        return cues

    def test_cut_lands_on_scene_break(self):
        cues = self._cues(12, gap_after=7)
        chunks = ht._make_smart_chunks(cues, 5)
        self.assertEqual(chunks[0][-1].index, 7)
        self.assertEqual(chunks[1][0].index, 8)

    def test_all_cues_preserved(self):
        cues = self._cues(23, gap_after=11)
        chunks = ht._make_smart_chunks(cues, 5)
        flat = [c.index for ch in chunks for c in ch]
        self.assertEqual(flat, list(range(1, 24)))

    def test_scene_gap_breaks_fragment_group_even_without_punctuation(self):
        cues = [
            self.Cue(1, 0.0, 1.0, "The first clause"),
            self.Cue(2, 8.0, 9.0, "continues grammatically."),
        ]
        grouped = ht._tag_fragments(cues, scene_gap_sec=30.0)
        broken = ht._tag_fragments(cues, scene_gap_sec=3.0)
        self.assertEqual([grouped[1], grouped[2]], ["start", "end"])
        self.assertEqual([broken[1], broken[2]], ["none", "none"])

    def test_scene_aligned_cut_keeps_late_fragment_group_whole(self):
        cues = self._cues(40, gap_after=30)
        tags = {cue.index: "none" for cue in cues}
        for cue_id in range(28, 38):
            tags[cue_id] = (
                "start" if cue_id == 28 else "end" if cue_id == 37 else "mid")
        chunks = ht._make_smart_chunks(cues, 25, frag_tags=tags)
        first_ids = {cue.index for cue in chunks[0]}
        self.assertTrue(set(range(28, 38)).issubset(first_ids))


class UnpunctuatedGuardGuiTest(unittest.TestCase):
    """Noktalamasız dosya koruması (MAX_FRAG_GROUP): kapanmayan uzun dizi tek dev
    'cümle' sayılıp chunk'ı şişirmemeli. (Helsreach gibi %2 noktalamalı dosyalar)"""
    TS = "00:00:01,000 --> 00:00:02,000"

    def _blocks(self, n):
        return [(str(i + 1), self.TS, f"line number {i + 1} without any period") for i in range(n)]

    def test_long_unpunctuated_run_becomes_standalone(self):
        tags = gui._tag_fragments_gui(self._blocks(50))
        self.assertTrue(all(v == "none" for v in tags.values()),
                        "noktasız uzun dizi 'none' olmalı (mid balonu değil)")

    def test_group_within_cap_still_grouped(self):
        # MAX_FRAG_GROUP içindeki gerçek fragman grubu korunur (davranış değişmedi)
        n = gui.MAX_FRAG_GROUP
        texts = [f"part {i}" for i in range(1, n)] + ["the final part."]
        tags = gui._tag_fragments_gui([(str(i + 1), self.TS, t) for i, t in enumerate(texts)])
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags[str(n)], "end")

    def test_oversized_group_not_grouped(self):
        # Cap'i bir aşan kapanan grup bile (noktalama çok seyrek) bağımsız bırakılır
        n = gui.MAX_FRAG_GROUP + 2
        texts = [f"part {i}" for i in range(1, n)] + ["the final part."]
        tags = gui._tag_fragments_gui([(str(i + 1), self.TS, t) for i, t in enumerate(texts)])
        self.assertTrue(all(v == "none" for v in tags.values()))

    def test_chunks_do_not_balloon(self):
        blocks = self._blocks(200)
        chunks = gui._make_smart_chunks_gui(blocks, gui.CHUNK)
        biggest = max(len(c) for c in chunks)
        self.assertLessEqual(biggest, gui.CHUNK + gui.MAX_FRAG_GROUP)
        # tüm satırlar korunur
        flat = [b[0] for c in chunks for b in c]
        self.assertEqual(flat, [str(i + 1) for i in range(200)])


class UnpunctuatedGuardHybridTest(unittest.TestCase):
    class Cue:
        def __init__(self, index, text):
            self.index, self.text = index, text

    def test_long_unpunctuated_run_becomes_standalone(self):
        cues = [self.Cue(i + 1, f"line {i + 1} no period") for i in range(50)]
        tags = ht._tag_fragments(cues)
        self.assertTrue(all(v == "none" for v in tags.values()))

    def test_group_within_cap_still_grouped(self):
        n = ht.MAX_FRAG_GROUP
        texts = [f"part {i}" for i in range(1, n)] + ["the final part."]
        cues = [self.Cue(i + 1, t) for i, t in enumerate(texts)]
        tags = ht._tag_fragments(cues)
        self.assertEqual(tags[1], "start")
        self.assertEqual(tags[n], "end")


if __name__ == "__main__":
    unittest.main()
