import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class Cue:
    def __init__(self, index, text):
        self.index = index
        self.text = text


class CriticFragmentFlowTest(unittest.TestCase):
    def _fake_openai_module(self, fixes, prompts):
        class FakeCompletions:
            def create(self, **kwargs):
                prompts.append(kwargs["messages"][0]["content"])
                return SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=ht.json.dumps(fixes, ensure_ascii=False))
                        )
                    ],
                )

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_validator_flags_early_verb_closure_on_fragment_start(self):
        cues = [
            Cue(1, "Throughout history, humanity has struggled,"),
            Cue(2, "with fears of Armageddon."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Tarih boyunca insanlık boğuştu,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Armageddon korkularıyla."),
        ]

        hits = ht.run_validators(blocks, cues)

        self.assertEqual(str(hits[0][0]), "1")
        self.assertIn("EARLY_VERB_CLOSURE", hits[0][3])

    def test_critic_sends_full_fragment_group_for_early_closure(self):
        cues = [
            Cue(1, "Throughout history, humanity has struggled,"),
            Cue(2, "with fears of Armageddon."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Tarih boyunca insanlık boğuştu,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Armageddon korkularıyla."),
        ]
        prompts = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}):
            ht.critic_pass_with_helper(cues=cues, tr_blocks=blocks, helper_api_key="test")

        self.assertEqual(len(prompts), 1)
        self.assertIn("CROSS-CUE FLOW", prompts[0])
        self.assertIn('"id": "1"', prompts[0])
        self.assertIn('"id": "2"', prompts[0])
        self.assertIn('"frag": "start"', prompts[0])
        self.assertIn('"frag": "end"', prompts[0])
        self.assertIn("EARLY_VERB_CLOSURE", prompts[0])
        self.assertIn('"must_fix_flow": true', prompts[0])
        self.assertIn("MANDATORY FLOW FIX", prompts[0])
        self.assertIn("Return [] only if", prompts[0])

    def test_critic_can_apply_group_rewrite_without_polish(self):
        cues = [
            Cue(1, "Throughout history, humanity has struggled,"),
            Cue(2, "with fears of Armageddon."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Tarih boyunca insanlık boğuştu,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Armageddon korkularıyla."),
        ]
        fixes = [
            {"id": "1", "fixed": "Tarih boyunca insanlık,"},
            {"id": "2", "fixed": "Armageddon korkularıyla boğuştu."},
        ]

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(cues=cues, tr_blocks=blocks, helper_api_key="test")

        self.assertEqual(result[0][2], "Tarih boyunca insanlık,")
        self.assertEqual(result[1][2], "Armageddon korkularıyla boğuştu.")


    def test_critic_sends_full_fragment_group_for_dangling_flow(self):
        cues = [
            Cue(1, "In order to show you the"),
            Cue(2, "importance of Saturn in religion."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Dunyanin genelinde,"),
            (2, "00:00:01,000 --> 00:00:02,000", "Saturn gezegeninin din icindeki onemini"),
        ]
        prompts = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}):
            ht.critic_pass_with_helper(cues=cues, tr_blocks=blocks, helper_api_key="test")

        self.assertEqual(len(prompts), 1)
        self.assertIn('"id": "1"', prompts[0])
        self.assertIn('"id": "2"', prompts[0])
        self.assertIn('"group_orig"', prompts[0])
        self.assertIn('"group_tr"', prompts[0])
        self.assertIn("DANGLING_TURKISH_FRAGMENT", prompts[0])
        self.assertIn('"must_fix_flow": true', prompts[0])

    def test_validator_flags_dominates_without_turkish_predicate(self):
        cues = [Cue(1, "Saturn dominates the Hebrew religion.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Saturn, Ibranice dini")]

        hits = ht.run_validators(blocks, cues)

        self.assertEqual(str(hits[0][0]), "1")
        self.assertIn("DOMINATES_MISSING_PREDICATE", hits[0][3])

    def test_validator_allows_dominates_with_turkish_predicate(self):
        cues = [Cue(1, "Saturn dominates the Hebrew religion.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Saturn Ibrani dinini etkiler.")]

        hits = ht.run_validators(blocks, cues)

        self.assertFalse(any("DOMINATES_MISSING_PREDICATE" in hit[3] for hit in hits))



    def test_critic_rejects_fix_that_breaks_source_question(self):
        cues = [Cue(1, "Are you sure?")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Emin misin, okay?")]
        fixes = [{"id": "1", "fixed": "Eminsin."}]
        logs = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[0][2], "Emin misin, okay?")
        self.assertTrue(any("source_question" in msg for _, msg in logs))


if __name__ == "__main__":
    unittest.main()
