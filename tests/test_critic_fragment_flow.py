import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class Cue:
    def __init__(self, index, text, start="", end=""):
        self.index = index
        self.text = text
        self.start = start
        self.end = end


class CriticFragmentFlowTest(unittest.TestCase):
    def test_custom_scene_gap_prevents_cross_scene_flow_warning(self):
        cues = [
            Cue(1, "I thought that", "00:00:01,000", "00:00:02,000"),
            Cue(2, "the other scene ended.", "00:00:04,000", "00:00:05,000"),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Sanmıştım"),
            (2, "00:00:04,000 --> 00:00:05,000", "Diğer sahne bitti."),
        ]

        hits = ht.run_validators(
            blocks, cues, scene_gap_sec=1.0)

        reasons = "|".join(str(hit[3]) for hit in hits)
        self.assertNotIn("EARLY_VERB_CLOSURE", reasons)
        self.assertNotIn("DANGLING_TURKISH_FRAGMENT", reasons)

    def test_critic_does_not_expand_flow_fix_across_custom_scene_gap(self):
        cues = [
            Cue(1, "I thought that", "00:00:01,000", "00:00:02,000"),
            Cue(2, "the other scene ended.", "00:00:04,000", "00:00:05,000"),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Sanmıştım"),
            (2, "00:00:04,000 --> 00:00:05,000", "Diğer sahne bitti."),
        ]
        prompts = []
        validator_hit = [(1, blocks[0][1], blocks[0][2], "EARLY_VERB_CLOSURE")]

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}), \
             patch("hybrid_translate.run_validators", return_value=validator_hit):
            ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
                scene_gap_sec=1.0,
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn('"id": "1"', prompts[0])
        self.assertNotIn('"id": "2"', prompts[0])

    def test_critic_omits_structural_neighbor_across_scene_gap(self):
        cues = [
            Cue(1, "OLD_SCENE_SENTINEL.", "00:00:01,000", "00:00:02,000"),
            Cue(2, "NEW_SCENE_SENTINEL.", "00:00:04,000", "00:00:05,000"),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Eski sahne."),
            (2, "00:00:04,000 --> 00:00:05,000", "Yeni sahne."),
        ]
        prompts = []
        validator_hit = [(2, blocks[1][1], blocks[1][2], "SPEAKER_LABEL_MISMATCH")]

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}), \
             patch("hybrid_translate.run_validators", return_value=validator_hit):
            ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                scene_gap_sec=1.0,
            )

        self.assertEqual(len(prompts), 1)
        self.assertIn('"id": "2"', prompts[0])
        self.assertNotIn('"prev": {"id": "1"', prompts[0])

    def test_critic_keeps_structural_neighbor_when_scene_gaps_disabled(self):
        cues = [
            Cue(1, "OLD_SCENE_SENTINEL.", "00:00:01,000", "00:00:02,000"),
            Cue(2, "NEW_SCENE_SENTINEL.", "00:00:04,000", "00:00:05,000"),
        ]
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "Eski sahne."),
            (2, "00:00:04,000 --> 00:00:05,000", "Yeni sahne."),
        ]
        prompts = []
        validator_hit = [(2, blocks[1][1], blocks[1][2], "SPEAKER_LABEL_MISMATCH")]

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}), \
             patch("hybrid_translate.run_validators", return_value=validator_hit):
            ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                scene_gap_sec=0,
            )

        self.assertIn('"prev": {"id": "1"', prompts[0])

    def test_critic_deduplicates_same_scene_context_within_chunk(self):
        cues = [
            Cue(1, "SOURCE_ONE."),
            Cue(2, "SOURCE_TWO."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Bir okay."),
            (2, "00:00:01,000 --> 00:00:02,000", "İki okay."),
        ]
        prompts = []
        validator_hits = [
            (1, blocks[0][1], blocks[0][2], "GARBLE_TOKEN"),
            (2, blocks[1][1], blocks[1][2], "GARBLE_TOKEN"),
        ]
        analysis = (SimpleNamespace(), {}, {}, {}, [{
            "start": 1, "end": 2, "summary": "SCENE_CONTEXT_SENTINEL",
        }])

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}), \
             patch("hybrid_translate.run_validators", return_value=validator_hits):
            ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                analysis_result=analysis,
            )

        self.assertEqual(prompts[0].count("SCENE_CONTEXT_SENTINEL"), 1)
        self.assertIn("applies to following lines", prompts[0])

    def test_critic_rejects_whole_fragment_group_when_one_member_fails_guard(self):
        cues = [
            Cue(1, "This is", "00:00:00,000", "00:00:01,000"),
            Cue(2, "a sentence.", "00:00:01,000", "00:00:02,000"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Bu"),
            (2, "00:00:01,000 --> 00:00:02,000", "bir cümledir."),
        ]
        fixes = [
            {"id": "1", "fixed": "Bu bir"},
            {"id": "2", "fixed": "cümledir."},
        ]
        validator_hits = [
            (1, blocks[0][1], blocks[0][2], "GARBLE_TOKEN"),
            (2, blocks[1][1], blocks[1][2], "GARBLE_TOKEN"),
        ]
        changes = []
        status = {}

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}), \
             patch("hybrid_translate.run_validators", return_value=validator_hits), \
             patch("hybrid_translate.validate_polish_candidate",
                   side_effect=[(True, ""), (False, "person_drift")]), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result = ht.critic_pass_with_helper(
                cues, blocks, "test", change_log=changes, status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(changes, [])
        self.assertEqual(status["rejected_count"], 2)
        self.assertEqual(status["rejected_candidates"][0]["reason"],
                         "fragment_group_member_rejected")
        self.assertEqual(status["rejected_candidates"][1]["reason"], "person_drift")

    def test_critic_rejects_cross_cue_obligation_to_possibility_swap(self):
        cues = [
            Cue(1, "You must", "00:00:00,000", "00:00:01,000"),
            Cue(2, "leave.", "00:00:01,000", "00:00:02,000"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Gitmek"),
            (2, "00:00:01,000 --> 00:00:02,000", "zorundasın."),
        ]
        fixes = [
            {"id": "1", "fixed": "Gitmek"},
            {"id": "2", "fixed": "isteyebilirsin."},
        ]
        validator_hits = [
            (1, blocks[0][1], blocks[0][2], "GARBLE_TOKEN"),
            (2, blocks[1][1], blocks[1][2], "GARBLE_TOKEN"),
        ]
        status = {}

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}), \
             patch("hybrid_translate.run_validators", return_value=validator_hits), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result = ht.critic_pass_with_helper(
                cues, blocks, "test", status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(status["rejected_count"], 1)
        self.assertEqual(status["rejected_candidates"][0]["reason"],
                         "fragment_group_semantic_rejection")

    def test_critic_does_not_count_unchanged_fragment_anchor_as_rejected(self):
        cues = [
            Cue(1, "This is", "00:00:00,000", "00:00:01,000"),
            Cue(2, "a sentence.", "00:00:01,000", "00:00:02,000"),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Bu"),
            (2, "00:00:01,000 --> 00:00:02,000", "bir cumle."),
        ]
        fixes = [
            {"id": "1", "fixed": "Bu bir"},
            {"id": "2", "fixed": "bir cumle."},
        ]
        validator_hits = [
            (1, blocks[0][1], blocks[0][2], "GARBLE_TOKEN"),
            (2, blocks[1][1], blocks[1][2], "GARBLE_TOKEN"),
        ]
        status = {}

        with patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}), \
             patch("hybrid_translate.run_validators", return_value=validator_hits), \
             patch("hybrid_translate.validate_polish_candidate",
                   return_value=(False, "person_drift")), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result = ht.critic_pass_with_helper(
                cues, blocks, "test", status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(status["rejected_count"], 1)
        self.assertEqual([item["id"] for item in status["rejected_candidates"]], ["1"])

    def test_critic_records_rejected_candidate_without_editing(self):
        cues = [Cue(1, "Mary arrived.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Mary geldi.")]
        prompts = []
        fixes = [{"id": "1", "fixed": "John geldi."}]
        status = {}
        validator_hit = [(1, blocks[0][1], blocks[0][2], "PERSON_DRIFT")]

        with patch.dict(
                sys.modules, {"openai": self._fake_openai_module(fixes, prompts)}), \
             patch("hybrid_translate.run_validators", return_value=validator_hit):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(status["rejected_count"], 1)
        record = status["rejected_candidates"][0]
        self.assertIn(record["reason"], {"critical_fact_swap", "person_drift"})
        self.assertEqual(record["source"], "Mary arrived.")
        self.assertEqual(record["before"], "Mary geldi.")
        self.assertEqual(record["candidate"], "John geldi.")

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

    def test_critic_receives_matching_scene_plan_and_full_analysis_context(self):
        cues = [Cue(7, "Give it back, okay?")]
        blocks = [(7, "00:00:00,000 --> 00:00:01,000", "Onu geri ver, okay?")]
        context = SimpleNamespace(
            tone="tense", setting="room", summary="A dispute over a key.",
            characters=[SimpleNamespace(name="Ayla", speaking_style="direct")])
        analysis = (
            context, {}, {"Ayla-Bora": "sen"},
            {"Ayla": {"register": "street", "dialect": "standard"}},
            [{"start": 5, "end": 9, "summary": "Ayla demands the key back.",
              "speakers": ["Ayla"], "speaker_goals": {"Ayla": "recover the key"},
              "referents": {"it": "the key"}, "tone": "angry"}],
            {}, [],
        )
        prompts = []

        with patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}):
            ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                analysis_result=analysis)

        self.assertIn("A dispute over a key.", prompts[0])
        self.assertIn("Ayla=street/standard", prompts[0])
        self.assertIn('"referents": {"it": "the key"}', prompts[0])

    def test_critic_expands_suspicious_line_to_full_sentence_context(self):
        cues = [
            Cue(1, "Although the rain had stopped,"),
            Cue(2, "the streets were still empty."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Yağmur okay durmuş olsa da,"),
            (2, "00:00:01,000 --> 00:00:02,000", "sokaklar hala boştu."),
        ]
        prompts = []

        with patch("hybrid_translate.run_validators", return_value=[]), \
             patch.dict(sys.modules, {"openai": self._fake_openai_module([], prompts)}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test")

        self.assertEqual(result, blocks)
        self.assertEqual(len(prompts), 1)
        self.assertIn("CROSS_CUE_SENTENCE_REVIEW", prompts[0])
        self.assertIn('"group_orig"', prompts[0])
        self.assertIn('"id": "1"', prompts[0])
        self.assertIn('"id": "2"', prompts[0])

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

    def test_critic_rejects_partial_fragment_rewrite_atomically(self):
        cues = [
            Cue(1, "Seeing them reminded me,"),
            Cue(2, "of an old love."),
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Onları görmek hatırlattı,"),
            (2, "00:00:01,000 --> 00:00:02,000", "eski bir aşkı."),
        ]
        fixes = [{"id": "1", "fixed": "Onları görünce işte,"}]
        logs = []

        with patch.dict(
                sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues,
                tr_blocks=blocks,
                helper_api_key="test",
                log_fn=lambda msg, level="info": logs.append((level, msg)),
            )

        self.assertEqual(result, blocks)
        self.assertTrue(any(
            "fragment_group_partial" in msg for _, msg in logs))


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

    def test_fragment_group_locked_term_is_validated_as_joined_source(self):
        cues = [Cue(1, "He visited New"), Cue(2, "York.")]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "New York'a gitti, okay."),
            (2, "00:00:01,000 --> 00:00:02,000", "Oradaydı, okay."),
        ]
        fixes = [
            {"id": "1", "fixed": "Başka kente gitti."},
            {"id": "2", "fixed": "Oradaydı."},
        ]
        hits = [
            (1, "", "", "GARBLE_TOKEN"),
            (2, "", "", "GARBLE_TOKEN"),
        ]

        with patch("hybrid_translate.run_validators", return_value=hits), \
             patch("hybrid_translate.validate_polish_candidate",
                   return_value=(True, "")), \
             patch("hybrid_translate._semantic_reason_map", side_effect=[{}, {}]), \
             patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                glossary={"New York": "New York"},
            )

        self.assertEqual(result, blocks)

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

    def test_combined_neighbor_regression_rejects_all_nearby_fixes(self):
        cues = [Cue(1, "He arrived."), Cue(2, "Then he left.")]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Buraya geldi, okay."),
            (2, "00:00:01,000 --> 00:00:02,000", "Sonra gitti, okay."),
        ]
        fixes = [
            {"id": "1", "fixed": "Buraya geldi."},
            {"id": "2", "fixed": "Buraya geldi."},
        ]
        hits = [
            (1, "", "", "GARBLE_TOKEN"),
            (2, "", "", "GARBLE_TOKEN"),
        ]
        changes = []
        with patch("hybrid_translate.run_validators", return_value=hits), \
             patch("hybrid_translate.validate_polish_candidate",
                   return_value=(True, "")), \
             patch("hybrid_translate._semantic_reason_map",
                   side_effect=[{}, {"2": {"NEIGHBOR_ECHO"}}]), \
             patch.dict(sys.modules, {"openai": self._fake_openai_module(fixes, [])}):
            result = ht.critic_pass_with_helper(
                cues=cues, tr_blocks=blocks, helper_api_key="test",
                change_log=changes,
            )

        self.assertEqual(result, blocks)
        self.assertEqual(changes, [])

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
