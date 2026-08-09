import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


def _response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        )],
        usage=None,
    )


def _raw_response(raw):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))], usage=None)


class FinalSemanticPartialResponseTest(unittest.TestCase):
    def test_truncated_response_retries_only_missing_clusters_and_keeps_coverage_honest(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bir."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Iki."),
        ]
        clusters = [
            {"cluster": "c1", "items": [{"id": "1", "source": "One.", "translation": "Bir.",
                                               "suspect": True, "reasons": ["POST_PASS_CHANGED"]}],
             "suspect_ids": ["1"]},
            {"cluster": "c2", "items": [{"id": "2", "source": "Two.", "translation": "Iki.",
                                               "suspect": True, "reasons": ["POST_PASS_CHANGED"]}],
             "suspect_ids": ["2"]},
        ]
        with patch("hybrid_translate.build_semantic_reconciliation_clusters", return_value=clusters), \
             patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", side_effect=[
                 _raw_response('[{"cluster":"c1","fixes":[]},'), _response([]),
             ]) as create:
            _result, stats = ht.semantic_reconciliation_pass(
                {"1": "One.", "2": "Two."}, blocks, api_key="k", model="m",
                changed_ids={"1", "2"})

        self.assertEqual(create.call_count, 2)
        self.assertEqual(stats["processed_cues"], 2)
        self.assertEqual(stats["api_requests"], 2)
        self.assertTrue(any(
            row.get("status") == "partial_retry_completed" for row in stats["details"]))


class CommonGuardRegressionTest(unittest.TestCase):
    def test_rejects_subject_object_and_fact_swaps(self):
        cases = [
            ("Beni gördü.", "Onu gördü.", "He saw me."),
            ("John geldi.", "Mary geldi.", "John arrived."),
            ("Kırmızı düğme.", "Mavi düğme.", "The red button."),
            ("Sola dön.", "Sağa dön.", "Turn left."),
            ("Şimdi git.", "Sonra git.", "Go now."),
            ("John geldi.", "John gelecek.", "John arrived."),
        ]
        for old, new, source in cases:
            with self.subTest(old=old, new=new):
                ok, reason = ht.validate_polish_candidate(old, new, source_text=source)
                self.assertFalse(ok)
                self.assertIn(reason, {"critical_fact_swap", "person_drift"})

    def test_consistency_does_not_replace_bare_formal_imperative_with_informal(self):
        cues = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Come here."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Come here."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Come here."),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Gel."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Gel."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Gelin."),
        ]
        result, fixes = ht.consistency_sweep(cues, blocks, min_words=1)
        self.assertEqual(fixes, 0)
        self.assertEqual(result, blocks)


class BacktranslationContextTest(unittest.TestCase):
    def test_compare_payload_contains_neighbor_context_for_split_sentences(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bunu sana dün söylemek istemiştim."),
            ("2", "00:00:02,000 --> 00:00:03,000", "Ama zaman bulamadım."),
        ]
        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", side_effect=[
                 _response([
                     {"id": "1", "en": "I wanted to tell you this yesterday."},
                     {"id": "2", "en": "But I could not find the time."},
                 ]),
                 _response([]),
             ]) as create:
            ht.back_translation_check(
                {"1": "I wanted to tell you this", "2": "but I could not find the time."},
                blocks, api_key="k", model="m", chunk_size=10)

        compare_user = create.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn('"prev"', compare_user)
        self.assertIn('"next"', compare_user)


if __name__ == "__main__":
    unittest.main()
