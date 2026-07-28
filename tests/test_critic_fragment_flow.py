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

    def test_critic_accepts_parser_tuple_cues(self):
        cues = [("1", "00:00:00,000 --> 00:00:01,000", "Hello.")]
        blocks = [("1", "00:00:00,000 --> 00:00:01,000", "Merhaba.")]

        with patch("hybrid_translate.run_validators", return_value=[]):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test")

        self.assertEqual(result, blocks)

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

    def test_critic_rejects_dangling_fragment_fix_that_deletes_words(self):
        cues = [
            Cue(1, "He has had the same dream again,"),
            Cue(2, "a dream that haunts him,"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:02,000", "Yine aynı rüyayı görmüştür,"),
            (2, "00:00:02,000 --> 00:00:04,000", "peşini bırakmayan o rüyayı,"),
        ]
        fixes = [{"id": "2", "fixed": "peşini bırakmayan,"}]
        logs = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[1][2], "peşini bırakmayan o rüyayı,")
        self.assertTrue(any("dangling_fragment_word_deletion" in msg for _, msg in logs))

    def test_rejected_group_member_cannot_authorize_dangling_deletion(self):
        cues = [
            Cue(1, "He has had the same dream again,"),
            Cue(2, "a dream that haunts him,"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:02,000", "Aynı rüyayı yeniden görmüştür,"),
            (2, "00:00:02,000 --> 00:00:04,000", "peşini bırakmayan o rüyayı,"),
        ]
        fixes = [
            {"id": "1", "fixed": "Aynı rüyayı yeniden görmüştür,"},
            {"id": "2", "fixed": "peşini bırakmayan,"},
        ]

        def validate(_old, candidate, **_kwargs):
            if candidate.startswith("Aynı"):
                return False, "test_rejection"
            return True, ""

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}), \
             patch("hybrid_translate.validate_polish_candidate", side_effect=validate):
            result = ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
            )

        self.assertEqual(result, blocks)

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



    def test_reflow_recovers_linebreak_count_mismatch(self):
        # Gerçek olay (2026-07-21, 5 dosyalık koşu): Critic önerilerinin
        # reddedilen kısmının büyük çoğunluğu (Metamorfose'da 181 reddin 165'i)
        # SADECE satır SAYISI orijinalden farklı diye atılıyordu -- içerik iyi
        # olsa bile. Artık atmadan önce orijinalin satır sayısına yeniden
        # sarmayı dener.
        cues = [Cue(1, "This is really important, okay?")]
        blocks = [(1, "00:00:00,000 --> 00:00:02,000", "Bu gerçekten önemli,\nokay?")]
        fixes = [{"id": "1", "fixed": "Bu gerçekten önemli, tamam mı?"}]
        change_log = []
        logs = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                change_log=change_log,
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[0][2].count("\n"), 1)
        self.assertNotIn("okay", result[0][2].lower())
        self.assertTrue(any("yeniden sarılarak kurtarıldı" in msg for _, msg in logs))
        self.assertEqual(len(change_log), 1)
        self.assertEqual(change_log[0]["id"], "1")
        self.assertEqual(change_log[0]["before"], "Bu gerçekten önemli,\nokay?")
        self.assertEqual(change_log[0]["after"], result[0][2])

    def test_reason_stats_logged(self):
        cues = [Cue(1, "Are you sure?")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Emin misin, okay?")]
        fixes = [{"id": "1", "fixed": "Emin misin?"}]
        logs = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertTrue(any("sebep-bazlı isabet" in msg for _, msg in logs))

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

    def test_short_locked_term_is_not_skipped(self):
        cues = [Cue(1, "Troy fell.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Troy düştü.")]

        hits = ht.run_validators(blocks, cues, glossary={"Troy": "Truva"})

        self.assertTrue(any("GLOSS_MISS:Troy=>Truva" in hit[3] for hit in hits))

    def test_uppercase_short_term_does_not_match_lowercase_pronoun(self):
        cues = [Cue(1, "Tell us now.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Bize şimdi söyle.")]

        hits = ht.run_validators(blocks, cues, glossary={"US": "ABD"})

        self.assertFalse(any("GLOSS_MISS:US=>ABD" in hit[3] for hit in hits))

    def test_fragment_group_is_not_split_at_critic_chunk_boundary(self):
        suspicious = [
            (i, "00:00:00,000 --> 00:00:01,000", f"Satır {i}")
            for i in range(1, 102)
        ]
        groups = {
            "100": ["100", "101"],
            "101": ["100", "101"],
        }

        chunks = ht._critic_suspicious_chunks(suspicious, groups, max_size=100)

        containing = [
            {str(item[0]) for item in chunk}
            for chunk in chunks
            if any(str(item[0]) in {"100", "101"} for item in chunk)
        ]
        self.assertEqual(len(containing), 1)
        self.assertTrue({"100", "101"}.issubset(containing[0]))

    def test_duplicate_and_noop_fixes_do_not_inflate_change_log(self):
        cues = [Cue(1, "Are you sure?")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Emin misin, okay?")]
        duplicate = [
            {"id": "1", "fixed": "Emin misin?"},
            {"id": "1", "fixed": "Emin misin?"},
        ]
        changes = []
        with patch.dict(sys.modules, {"openai": self._fake_openai_module(duplicate, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                change_log=changes,
            )
        self.assertEqual(result[0][2], "Emin misin?")
        self.assertEqual(len(changes), 1)

        no_op_changes = []
        no_op = [{"id": "1", "fixed": blocks[0][2]}]
        with patch.dict(sys.modules, {"openai": self._fake_openai_module(no_op, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                change_log=no_op_changes,
            )
        self.assertEqual(result, blocks)
        self.assertEqual(no_op_changes, [])

    def test_local_fix_is_reported_and_fragment_context_is_fresh(self):
        cues = [
            Cue(1, "This metaphor,"),
            Cue(2, "is okay?"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Bu metafoor,"),
            (2, "00:00:01,000 --> 00:00:02,000", "okay?"),
        ]
        prompts = []
        changes = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                change_log=changes,
            )

        self.assertEqual(result[0][2], "Bu metafor,")
        self.assertTrue(any(item["reason"] == "local_regex" for item in changes))
        self.assertTrue(prompts)
        self.assertIn("Bu metafor,", prompts[0])
        self.assertNotIn("Bu metafoor,", prompts[0])


class ReflowToLineCountTest(unittest.TestCase):
    def test_single_line_target_joins_all_words(self):
        self.assertEqual(ht._reflow_to_line_count("Bu\nbir\ncümle.", 1), "Bu bir cümle.")

    def test_empty_text_returns_empty(self):
        self.assertEqual(ht._reflow_to_line_count("", 2), "")

    def test_two_line_target_splits_at_balanced_point(self):
        result = ht._reflow_to_line_count("Bu gerçekten önemli, tamam mı?", 2)
        self.assertEqual(result.count("\n"), 1)
        # Kelime kaybı olmamalı.
        self.assertEqual(
            "".join(result.split()),
            "".join("Bu gerçekten önemli, tamam mı?".split()),
        )


class CriticChunkErrorLoggingTest(unittest.TestCase):
    """Boş/kesik yanıt artık SESSİZCE atlanmıyor -- bkz. critic_pass_with_helper
    docstring, 2026-07-21: bir chunk'ın JSON'ı bozuksa o chunk'taki TÜM satırlar
    (100'e kadar) hiç log görünmeden kayboluyordu."""

    def test_empty_response_logged_not_silent(self):
        cues = [Cue(1, "Are you sure?")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Emin misin, okay?")]

        class FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(usage=None, choices=[
                    SimpleNamespace(message=SimpleNamespace(content=""))
                ])

        class FakeOpenAI:
            def __init__(self, api_key=None, base_url=None):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        logs = []
        with patch.dict(sys.modules, {"openai": SimpleNamespace(OpenAI=FakeOpenAI)}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result[0][2], "Emin misin, okay?")
        self.assertTrue(any("boş yanıt döndü" in msg for _, msg in logs))


if __name__ == "__main__":
    unittest.main()
