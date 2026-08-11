import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui
import hybrid_translate as ht


def _request(items):
    return {
        "custom_id": "chunk_1",
        "body": {
            "model": "gpt-5.4",
            "messages": [
                {"role": "system", "content": "Translate."},
                {"role": "user", "content": json.dumps({"tr": items})},
            ],
        },
    }


class LiveRunRecoveryTest(unittest.TestCase):
    def _app(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = MagicMock()
        app._update_tokens = MagicMock()
        return app

    def test_non_turkish_leak_repairs_only_bad_cue_once(self):
        app = self._app()
        req = _request([
            {"i": 1, "t": "Healthy first source."},
            {"i": 2, "t": "This one was free."},
            {"i": 3, "t": "Healthy last source."},
        ])
        raw_map = {"chunk_1": json.dumps([
            {"i": 1, "t": "Sağlam ilk çeviri."},
            {"i": 2, "t": "Bu oùcretsizdi."},
            {"i": 3, "t": "Sağlam son çeviri."},
        ], ensure_ascii=False)}
        repaired = json.dumps([
            {"i": 1, "t": "Sağlam ilk çeviri."},
            {"i": 2, "t": "Bu ücretsizdi."},
            {"i": 3, "t": "Sağlam son çeviri."},
        ], ensure_ascii=False)

        def targeted(_client, _req, current_raw, max_sub=1):
            items = json.loads(current_raw)
            self.assertEqual(max_sub, 1)
            self.assertEqual(items[0]["t"], "Sağlam ilk çeviri.")
            self.assertEqual(items[1]["t"], "[HATA_NON_TURKISH_TARGET]")
            self.assertEqual(items[2]["t"], "Sağlam son çeviri.")
            return repaired

        app._resend_missing_blocks = MagicMock(side_effect=targeted)
        with patch.object(gui, "_safe_chat_create") as full_retry:
            unresolved = app._retry_hata(
                object(), raw_map, [req], max_rounds=3)

        self.assertEqual(unresolved, set())
        self.assertEqual(raw_map["chunk_1"], repaired)
        app._resend_missing_blocks.assert_called_once()
        full_retry.assert_not_called()

    def test_failed_targeted_leak_repair_is_report_only_without_full_retry(self):
        app = self._app()
        req = _request([
            {"i": 1, "t": "Healthy source."},
            {"i": 2, "t": "This one was free."},
        ])
        original = json.dumps([
            {"i": 1, "t": "Sağlam çeviri."},
            {"i": 2, "t": "Bu oùcretsizdi."},
        ], ensure_ascii=False)
        raw_map = {"chunk_1": original}
        app._resend_missing_blocks = MagicMock(return_value=None)

        with patch.object(gui, "_safe_chat_create") as full_retry:
            unresolved = app._retry_hata(
                object(), raw_map, [req], max_rounds=3)

        self.assertEqual(unresolved, set())
        self.assertEqual(raw_map["chunk_1"], original)
        app._resend_missing_blocks.assert_called_once()
        full_retry.assert_not_called()

    def test_owner_mismatch_is_logged_once_when_final_sweep_rechecks_same_map(self):
        app = self._app()
        req = _request([{"i": 1, "t": "Thousands came to Iquique."}])
        raw_map = {"chunk_1": json.dumps([
            {"i": 1, "t": "Binlercesi Iquique'ye geldi."},
        ], ensure_ascii=False)}

        with patch.object(
                gui, "_chunk_response_retry_reason",
                return_value="cue_content_owner_mismatch"):
            app._retry_hata(object(), raw_map, [req], max_rounds=1)
            app._retry_hata(object(), raw_map, [req], max_rounds=1)

        messages = [str(call.args[0]) for call in app._log.call_args_list]
        self.assertEqual(
            sum("şüpheli cue yalnız inceleme raporuna" in text for text in messages),
            1,
        )


class LiveRunFalsePositiveTest(unittest.TestCase):
    def test_nested_source_phrase_is_not_adjacent_duplicate(self):
        seq = [
            ("705", "Bay O'Brian'a söyleyin..."),
            ("712", "Bay O'Brian'a söyleyin, bir subayla konuşuyor..."),
        ]
        src = {
            "705": "Tell Mr. O'Brian...",
            "712": "Tell Mr. O'Brian that he's talking with an officer...",
        }
        self.assertEqual(gui._find_adjacent_duplicate_ids(seq, src), [])

    def test_quality_source_map_follows_timestamps_after_cue_ids_shift(self):
        cues = [
            SimpleNamespace(
                index=1, start="00:00:01,000", end="00:00:01,900",
                text="The army is here."),
            SimpleNamespace(
                index=2, start="00:00:02,000", end="00:00:02,900",
                text="The Pampa is wide."),
        ]
        final_blocks = [
            (2, "00:00:01,000 --> 00:00:01,900", "Ordu burada."),
            (3, "00:00:02,000 --> 00:00:02,900", "Pampa geniş."),
        ]
        self.assertEqual(
            gui._source_map_for_quality_blocks(final_blocks, cues),
            {"2": "The army is here.", "3": "The Pampa is wide."},
        )

    def test_analysis_glossary_repairs_ascii_turkish_before_locking(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "big strike": "buyuk grev",
            "workers": "isciler",
            "fellow": "yoldas",
            "little brother": "kardesim",
            "private property": "ozel mulkiyet",
            "What do we have to do?": "Ne yapmaliyiz?",
        })
        self.assertEqual(cleaned, {
            "big strike": "büyük grev",
            "workers": "işçiler",
            "fellow": "yoldaş",
            "little brother": "kardeşim",
            "private property": "özel mülkiyet",
            "What do we have to do?": "Ne yapmalıyız?",
        })


if __name__ == "__main__":
    unittest.main()
