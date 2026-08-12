import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class Cue:
    def __init__(self, index, text, start="00:00:00,000", end="00:00:01,000"):
        self.index = index
        self.text = text
        self.start = start
        self.end = end


class FakeOpenAI:
    def __init__(self, **_kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **_k: None))


def _response(content):
    return SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class QualityResponseOwnershipTest(unittest.TestCase):
    def test_condense_rejects_outside_chunk_and_conflicting_duplicate_id(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000",
             "This is an extremely long subtitle line that cannot be read."),
            ("2", "00:00:01,000 --> 00:00:11,000", "This line must stay."),
        ]
        response = _response('[{"id":"2","short":"Changed."},'
                             '{"id":"1","short":"Short."},'
                             '{"id":"1","short":"Other."}]')
        status = {}
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}), \
             patch("hybrid_translate._safe_chat_create", return_value=response):
            result, changed = ht.condense_fast_lines(
                blocks, "key", cps_limit=21, status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(changed, 0)
        self.assertEqual(status["status"], "completed")

    def test_critic_retries_only_tail_of_truncated_response(self):
        cues = [Cue(1, "Are you sure?"), Cue(2, "Are you ready?")]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Emin misin, okay?"),
            (2, "00:00:01,000 --> 00:00:02,000", "Hazir misin, okay?"),
        ]
        responses = iter([
            '[{"id":"1","fixed":"Emin misin?"},'
            '{"id":"2","fixed":"Hazir misin?"',
            "[]",
        ])
        status = {}
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}), \
             patch("hybrid_translate._safe_chat_create",
                   side_effect=lambda *_a, **_k: _response(next(responses))) as call:
            result = ht.critic_pass_with_helper(
                cues, blocks, "key", status_out=status)

        self.assertEqual(result[0][2], "Emin misin?")
        self.assertEqual(result[1][2], "Hazir misin, okay?")
        self.assertEqual(call.call_count, 2)
        self.assertEqual(status["status"], "completed")

    def test_critic_retry_prompt_excludes_already_recovered_items(self):
        cues = [
            Cue(1, "FIRST_ONLY_RETRY_SENTINEL."),
            Cue(2, "SECOND_ONLY_RETRY_SENTINEL."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Birinci okay."),
            (2, "00:00:01,000 --> 00:00:02,000", "İkinci okay."),
        ]
        responses = iter([
            '[{"id":"1","fixed":"Birinci."},'
            '{"id":"2","fixed":"İkinci."',
            "[]",
        ])
        prompts = []

        def fake_create(*_args, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            return _response(next(responses))

        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}), \
             patch("hybrid_translate._safe_chat_create", side_effect=fake_create):
            ht.critic_pass_with_helper(cues, blocks, "key")

        self.assertEqual(len(prompts), 2)
        self.assertNotIn("FIRST_ONLY_RETRY_SENTINEL", prompts[1])
        self.assertIn("SECOND_ONLY_RETRY_SENTINEL", prompts[1])

    def test_critic_retry_keeps_whole_sentence_context_for_remaining_fragment(self):
        cues = [
            Cue(1, "FIRST_FRAGMENT_SENTINEL", end="00:00:01,000"),
            Cue(2, "SECOND_FRAGMENT_SENTINEL.",
                "00:00:01,000", "00:00:02,000"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "İlk parça"),
            (2, "00:00:01,000 --> 00:00:02,000", "ikinci parça."),
        ]
        responses = iter([
            '[{"id":"1","fixed":"İlk parça"},'
            '{"id":"2","fixed":"ikinci parça."',
            "[]",
        ])
        prompts = []

        def fake_create(*_args, **kwargs):
            prompts.append(kwargs["messages"][0]["content"])
            return _response(next(responses))

        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}), \
             patch("hybrid_translate._safe_chat_create", side_effect=fake_create):
            ht.critic_pass_with_helper(cues, blocks, "key")

        self.assertEqual(len(prompts), 2)
        self.assertIn('"id": "2"', prompts[1])
        self.assertNotIn('"id": "1"', prompts[1])
        self.assertIn('"group_orig": "FIRST_FRAGMENT_SENTINEL SECOND_FRAGMENT_SENTINEL."', prompts[1])
        self.assertIn('"group_tr": "İlk parça ikinci parça."', prompts[1])

    def test_native_marks_unrecovered_truncated_response_partial(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000", "Bu garip bir cumle."),
            ("2", "00:00:01,000 --> 00:00:02,000", "Diger garip cumle."),
        ]
        responses = iter([
            '[{"id":"1","fixed":"Bu garip bir cumle!"},{"id":"2","fixed":"Diger',
            "",
        ])
        status = {}
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}), \
             patch("hybrid_translate._safe_chat_create",
                   side_effect=lambda *_a, **_k: _response(next(responses))):
            result = ht.native_reader_pass(blocks, "key", status_out=status)

        self.assertEqual(result[0][2], "Bu garip bir cumle!")
        self.assertEqual(result[1][2], "Diger garip cumle.")
        self.assertEqual(status["status"], "partial")

    def test_contextless_tm_is_not_injected_into_batch_context(self):
        tm = SimpleNamespace(
            lookup=lambda *_a, **_k: self.fail("contextless TM lookup must not run"),
            fuzzy_lookup=lambda *_a, **_k: self.fail("contextless TM fuzzy lookup must not run"),
            record_hit=lambda: self.fail("contextless TM must not record a hit"),
        )
        cues = [
            Cue(1, "Come in."),
            Cue(2, "Thank you.", "00:00:01,000", "00:00:02,000"),
        ]
        requests, _ = ht.build_batch_requests(
            cues, "system", "model", chunk_size=1, tm=tm,
            context_lines=1, use_tm_context=True,
        )
        payload = __import__("json").loads(
            requests[1]["body"]["messages"][1]["content"])
        self.assertNotIn("tr", payload["ctx"][0])


if __name__ == "__main__":
    unittest.main()
