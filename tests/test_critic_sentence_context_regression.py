import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class Cue:
    def __init__(self, index, text):
        self.index = index
        self.text = text
        self.start = ""
        self.end = ""


class CriticSentenceContextRegressionTest(unittest.TestCase):
    @staticmethod
    def _fake_openai(response, prompts):
        class Completions:
            def create(self, **kwargs):
                prompts.append(kwargs["messages"][0]["content"])
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        content=json.dumps(response, ensure_ascii=False)))],
                )

        class OpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=Completions())

        return SimpleNamespace(OpenAI=OpenAI)

    def _run(self, cues, blocks, response, prompts=None, changes=None):
        prompts = prompts if prompts is not None else []
        with patch.dict(sys.modules, {
                "openai": self._fake_openai(response, prompts)}), \
             patch("hybrid_translate.run_validators", return_value=[]), \
             patch("hybrid_translate.validate_polish_candidate",
                   return_value=(True, "")), \
             patch("hybrid_translate._semantic_reason_map",
                   side_effect=[{}, {}]):
            result = ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
                change_log=changes,
            )
        return result, prompts

    def test_all_cross_cue_sentences_are_reviewed_without_detector_hit(self):
        cues = [
            Cue(8, "I've been fascinated by psychoactive drugs"),
            Cue(9, "my whole life."),
        ]
        blocks = [
            (8, "00:00:01,000 --> 00:00:02,000",
             "Psikoaktif maddeler hep ilgimi çekmiştir."),
            (9, "00:00:02,000 --> 00:00:03,000", "Hayatım boyunca."),
        ]

        result, prompts = self._run(cues, blocks, [])

        self.assertEqual(result, blocks)
        self.assertEqual(len(prompts), 1)
        self.assertIn('"id": "8"', prompts[0])
        self.assertIn('"id": "9"', prompts[0])
        self.assertIn("CROSS_CUE_SENTENCE_REVIEW", prompts[0])
        self.assertIn("EVERY id in that frag_group", prompts[0])

    def test_unchanged_group_member_can_anchor_atomic_sentence_fix(self):
        cues = [Cue(1, "Maybe you start on mushrooms and"),
                Cue(2, "then you go to marijuana.")]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000",
             "Belki mantarla başlarsın, sonra esrara geçer,"),
            (2, "00:00:02,000 --> 00:00:03,000", "ve iş orada biter."),
        ]
        fixes = [
            {"id": "1", "fixed":
             "Belki mantarla başlarsın, sonra esrara geçersin,"},
            {"id": "2", "fixed": blocks[1][2]},
        ]
        changes = []

        result, _prompts = self._run(
            cues, blocks, fixes, changes=changes)

        self.assertEqual(
            result[0][2],
            "Belki mantarla başlarsın, sonra esrara geçersin,")
        self.assertEqual(result[1], blocks[1])
        self.assertEqual([item["id"] for item in changes], ["1"])

    def test_hamilton_sentence_is_rewritten_as_one_atomic_group(self):
        cues = [
            Cue(8, "I've been fascinated by psychoactive drugs"),
            Cue(9, "my whole life."),
        ]
        blocks = [
            (8, "00:00:01,000 --> 00:00:02,000",
             "Psikoaktif maddeler hep ilgimi çekmiştir."),
            (9, "00:00:02,000 --> 00:00:03,000", "Hayatım boyunca."),
        ]
        fixes = [
            {"id": "8", "fixed": "Psikoaktif maddelere"},
            {"id": "9", "fixed": "hayatım boyunca ilgi duydum."},
        ]

        result, _prompts = self._run(cues, blocks, fixes)

        self.assertEqual(result[0][2], "Psikoaktif maddelere")
        self.assertEqual(result[1][2], "hayatım boyunca ilgi duydum.")


if __name__ == "__main__":
    unittest.main()
