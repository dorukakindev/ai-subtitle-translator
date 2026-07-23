import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class RetryQualityGuardTest(unittest.TestCase):
    def test_retry_hata_retries_parsed_non_turkish_target_leak(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None

        raw_map = {
            "chunk_1": json.dumps(
                [{"i": 1, "t": "Bir bäýram/holidaý oturylyşyğı."}],
                ensure_ascii=False,
            )
        }
        requests = [{
            "custom_id": "chunk_1",
            "body": {
                "model": "gpt-4.1-mini",
                "messages": [
                    {"role": "system", "content": "Translate to Turkish."},
                    {"role": "user", "content": "[]"},
                ],
                "temperature": 0.3,
            },
        }]
        calls = []

        def fake_chat_create(_client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                usage=None,
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps([{"i": 1, "t": "Bir yılbaşı partisi."}], ensure_ascii=False)
                        )
                    )
                ],
            )

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

        self.assertEqual(
            json.loads(raw_map["chunk_1"]),
            [{"i": 1, "t": "Bir yılbaşı partisi."}],
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["temperature"], 0.2)
        guard_messages = [m["content"] for m in calls[0]["messages"]]
        self.assertTrue(any("QUALITY RETRY" in msg for msg in guard_messages))


class RetryHataAdjacentDuplicateTest(unittest.TestCase):
    """Fix C: _retry_hata artık chunk'ın KENDİ çıktısında adjacent_duplicate
    tetiklenirse (bkz. detect_alignment_issues) dosya yazılmadan ÖNCE, chunk'ı
    ID INTEGRITY guard mesajıyla yeniden dener — Explorer 1 #171/#172 gerçek
    olayına dayanan senaryo."""

    def _req(self, cid, tr_items):
        return {
            "custom_id": cid,
            "body": {
                "model": "gpt-5.4-mini",
                "messages": [
                    {"role": "system", "content": "Translate to Turkish."},
                    {"role": "user", "content": json.dumps({"tr": tr_items}, ensure_ascii=False)},
                ],
                "temperature": 0.3,
            },
        }

    def test_retries_chunk_internal_duplicate_with_id_integrity_guard(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None

        raw_map = {
            "chunk_1": json.dumps([
                {"i": 171, "t": "yolları düşünüldüğünde, benzer bir işi yapacak kadar güçlü değildir."},
                {"i": 172, "t": "yolları düşünüldüğünde, benzer bir işi yapacak kadar güçlü değildir."},
            ], ensure_ascii=False)
        }
        requests = [self._req("chunk_1", [
            {"i": 171, "t": "THE HUGE SIZE OF THE STONES AND THE DIFFICULT MOUNTAIN", "d": 3.0},
            {"i": 172, "t": "PATHS THEY TRAVELED OVER.", "d": 2.0},
        ])]
        calls = []

        def fake_chat_create(_client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                    {"i": 171, "t": "Taşların büyüklüğü ve zorlu dağ yolları düşünüldüğünde,"},
                    {"i": 172, "t": "benzer bir işi yapacak kadar güçlü değildir."},
                ], ensure_ascii=False)))],
            )

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

        self.assertEqual(len(calls), 1, "chunk-içi tekrar tespit edilip yeniden denenmeliydi")
        guard_messages = [m["content"] for m in calls[0]["messages"]]
        self.assertTrue(any("ID INTEGRITY" in msg for msg in guard_messages))
        result = json.loads(raw_map["chunk_1"])
        self.assertNotEqual(result[0]["t"], result[1]["t"])

    def test_clean_chunk_not_retried_for_duplicate_reason(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None

        raw_map = {
            "chunk_1": json.dumps([
                {"i": 1, "t": "Merhaba, nasılsın?"},
                {"i": 2, "t": "İyiyim, teşekkürler."},
            ], ensure_ascii=False)
        }
        requests = [self._req("chunk_1", [
            {"i": 1, "t": "HELLO, HOW ARE YOU?", "d": 2.0},
            {"i": 2, "t": "I'M GOOD, THANKS.", "d": 2.0},
        ])]

        def fake_chat_create(_client, **kwargs):
            raise AssertionError("temiz chunk yeniden denenmemeli")

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

        self.assertEqual(
            json.loads(raw_map["chunk_1"]),
            [{"i": 1, "t": "Merhaba, nasılsın?"}, {"i": 2, "t": "İyiyim, teşekkürler."}],
        )

    def test_source_also_repeats_not_retried(self):
        # Kaynağın kendisi tekrarlıyorsa (refrain) çevirinin aynı olması meşru.
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None

        raw_map = {
            "chunk_1": json.dumps([
                {"i": 1, "t": "Bunu oraya koymak istemiyoruz."},
                {"i": 2, "t": "Bunu oraya koymak istemiyoruz."},
            ], ensure_ascii=False)
        }
        requests = [self._req("chunk_1", [
            {"i": 1, "t": "WE DON'T WANT THIS SORT OF STUFF IN THERE.", "d": 2.0},
            {"i": 2, "t": "WE DON'T WANT THIS SORT OF STUFF IN THERE.", "d": 2.0},
        ])]

        def fake_chat_create(_client, **kwargs):
            raise AssertionError("kaynağı da tekrarlayan chunk yeniden denenmemeli")

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

    def test_empty_dialogue_retries_whole_chunk_in_strict_id_mode(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None
        raw_map = {"chunk_1": json.dumps([
            {"i": 1, "t": "Sonraki satırın içeriği."},
            {"i": 2, "t": ""},
        ], ensure_ascii=False)}
        req = self._req("chunk_1", [
            {"i": 1, "t": "IS TEA GOOD FOR OUR HEALTH?", "d": 2.0,
             "frag": "start", "frag_group": "fg_1_2"},
            {"i": 2, "t": "OR IS IT HARMFUL?", "d": 2.0,
             "frag": "end", "frag_group": "fg_1_2"},
        ])
        payload = json.loads(req["body"]["messages"][1]["content"])
        payload["sentence_groups"] = [{"id": "fg_1_2", "items": [1, 2]}]
        req["body"]["messages"][1]["content"] = json.dumps(payload, ensure_ascii=False)
        calls = []

        def fake_chat_create(_client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                    {"i": 1, "t": "Çay sağlığımız için iyi mi?"},
                    {"i": 2, "t": "Yoksa zararlı mı?"},
                ], ensure_ascii=False)))],
            )

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, [req], max_rounds=1)

        self.assertEqual(len(calls), 1)
        guard_messages = [m["content"] for m in calls[0]["messages"]]
        self.assertTrue(any("STRICT ID RETRY" in msg for msg in guard_messages))
        retry_payload = json.loads(next(
            m["content"] for m in calls[0]["messages"] if m.get("role") == "user"
        ))
        self.assertNotIn("sentence_groups", retry_payload)
        self.assertTrue(all("frag" not in it and "frag_group" not in it
                            for it in retry_payload["tr"]))

    def test_missing_id_retries_whole_chunk(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None
        raw_map = {"chunk_1": json.dumps([{"i": 1, "t": "Merhaba."}], ensure_ascii=False)}
        requests = [self._req("chunk_1", [
            {"i": 1, "t": "HELLO.", "d": 1.0},
            {"i": 2, "t": "HOW ARE YOU?", "d": 1.0},
        ])]
        calls = []

        def fake_chat_create(_client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                    {"i": 1, "t": "Merhaba."},
                    {"i": 2, "t": "Nasılsın?"},
                ], ensure_ascii=False)))],
            )

        with patch.object(gui, "_safe_chat_create", fake_chat_create):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

        self.assertEqual(len(calls), 1)
        self.assertEqual([it["i"] for it in json.loads(raw_map["chunk_1"])], [1, 2])

    def test_empty_sfx_does_not_trigger_strict_retry(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None
        raw_map = {"chunk_1": json.dumps([{"i": 1, "t": ""}], ensure_ascii=False)}
        requests = [self._req("chunk_1", [{"i": 1, "t": "[MUSIC]", "d": 1.0}])]

        with patch.object(gui, "_safe_chat_create",
                          side_effect=AssertionError("SFX boşluğu yeniden denenmemeli")):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

    def test_failed_strict_retry_does_not_merge_partial_shifted_output(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = lambda *args, **kwargs: None
        app._update_tokens = lambda *args, **kwargs: None
        app._resend_missing_blocks = lambda *args, **kwargs: (
            self.fail("katı ID hatasında kısmi çıktı birleştirilmemeli")
        )
        raw_map = {"chunk_1": json.dumps([
            {"i": 1, "t": "Sonraki satırın içeriği."},
            {"i": 2, "t": ""},
        ], ensure_ascii=False)}
        requests = [self._req("chunk_1", [
            {"i": 1, "t": "FIRST SOURCE LINE.", "d": 1.0},
            {"i": 2, "t": "SECOND SOURCE LINE.", "d": 1.0},
        ])]

        def still_bad(_client, **kwargs):
            return SimpleNamespace(
                usage=None,
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                    {"i": 1, "t": "Hâlâ kaymış içerik."},
                    {"i": 2, "t": ""},
                ], ensure_ascii=False)))],
            )

        with patch.object(gui, "_safe_chat_create", still_bad):
            app._retry_hata(object(), raw_map, requests, max_rounds=1)

        self.assertEqual(json.loads(raw_map["chunk_1"]), [
            {"i": 1, "t": "[HATA]"},
            {"i": 2, "t": "[HATA]"},
        ])


class ChunkSrcMapFromRequestTest(unittest.TestCase):
    def test_extracts_source_map_from_well_formed_request(self):
        req = {
            "body": {
                "messages": [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": json.dumps({"tr": [
                        {"i": 5, "t": "HELLO."}, {"i": 6, "t": "WORLD."},
                    ]})},
                ]
            }
        }
        self.assertEqual(gui._chunk_src_map_from_request(req), {"5": "HELLO.", "6": "WORLD."})

    def test_missing_or_malformed_request_returns_empty_dict(self):
        self.assertEqual(gui._chunk_src_map_from_request({}), {})
        self.assertEqual(gui._chunk_src_map_from_request({"body": {"messages": []}}), {})
        bad = {"body": {"messages": [{"role": "user", "content": "not json"}]}}
        self.assertEqual(gui._chunk_src_map_from_request(bad), {})

    def test_no_user_role_returns_empty_dict(self):
        req = {"body": {"messages": [{"role": "system", "content": "sys"}]}}
        self.assertEqual(gui._chunk_src_map_from_request(req), {})


if __name__ == "__main__":
    unittest.main()
