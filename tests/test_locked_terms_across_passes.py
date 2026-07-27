import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class LockedTermGuardTest(unittest.TestCase):
    def test_rejects_missing_required_rendering(self):
        ok, reason = ht.validate_polish_candidate(
            "İmparator geliyor.",
            "Hükümdar geliyor.",
            source_text="The Emperor is coming.",
            locked_terms={"Emperor": "İmparator"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked_term_violation")

    def test_source_boundary_does_not_match_substring(self):
        ok, _reason = ht.validate_polish_candidate(
            "Arthur geliyor.",
            "Arthur nihayet geliyor.",
            source_text="Arthur is coming.",
            locked_terms={"art": "sanat"},
        )
        self.assertTrue(ok)

    def test_accepts_turkish_inflection_of_locked_target(self):
        ok, reason = ht.validate_polish_candidate(
            "İmparatorluğun sınırı.",
            "İmparatorluğun doğu sınırı.",
            source_text="The Imperium's eastern border.",
            locked_terms={"Imperium": "İmparatorluk"},
        )
        self.assertTrue(ok, reason)

    def test_semantic_cluster_selects_existing_locked_term_miss(self):
        blocks = [("1", "00:00:00,000 --> 00:00:01,000", "Hükümdar geliyor.")]
        src_map = {"1": "The Emperor is coming."}
        clusters = ht.build_semantic_reconciliation_clusters(
            src_map,
            blocks,
            locked_terms={"Emperor": "İmparator"},
        )
        self.assertEqual(clusters[0]["suspect_ids"], ["1"])
        self.assertTrue(any(
            reason.startswith("GLOSS_MISS")
            for reason in clusters[0]["items"][0]["reasons"]
        ))

    def test_condense_cannot_drop_locked_term(self):
        ok, reason = ht.validate_condense_candidate(
            "İmparator bugün saraya doğru geliyor.",
            "Hükümdar saraya geliyor.",
            source_text="The Emperor is coming to the palace today.",
            locked_terms={"Emperor": "İmparator"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked_term_violation")

    def test_final_consistency_cannot_replace_locked_term(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "İmparator geliyor.")]
        swept = [(1, blocks[0][1], "Hükümdar geliyor.")]
        cues = [(1, blocks[0][1], "The Emperor is coming.")]
        with patch("hybrid_translate.consistency_sweep", return_value=(swept, 1)):
            result, fixed = ht.final_consistency_sweep(
                cues,
                blocks,
                locked_terms={"Emperor": "İmparator"},
            )
        self.assertEqual(result, blocks)
        self.assertEqual(fixed, 0)

    def test_fragment_group_enforces_split_multiword_term(self):
        proposals = {
            "1": ("Büyük", True, "", "fg"),
            "2": ("şehir.", True, "", "fg"),
        }
        originals = {"1": "New", "2": "York."}
        result, rejected, reasons = ht.apply_polish_group_atomic(
            proposals,
            originals,
            group_expected={"fg": ["1", "2"]},
            src_map={"1": "New", "2": "York"},
            locked_terms={"New York": "New York"},
        )
        self.assertEqual(result, {})
        self.assertEqual(rejected, 2)
        self.assertEqual(
            reasons.get("group_atomic_joined:locked_term_violation"), 2)

    def test_term_normalizer_prefers_locked_target(self):
        blocks = [
            ("1", "", "Troy kuşatması başladı."),
            ("2", "", "Sonra Troy yıkıldı."),
            ("3", "", "İlion'un kalıntıları bulundu."),
            ("4", "", "Ama Troy hâlâ tartışmalı."),
            ("5", "", "İlion'a dair kanıtlar var."),
        ]
        src_map = {
            "1": "The Troy siege began.",
            "2": "Then Troy fell.",
            "3": "The ruins of Troy were found.",
            "4": "But Troy is still disputed.",
            "5": "Evidence about Troy exists.",
        }
        plan = gui._mixed_term_autofix_plan(
            blocks,
            src_map,
            locked_terms={"Troy": "Truva"},
        )
        self.assertEqual(plan["1"], [("Troy", "Truva")])
        self.assertEqual(plan["2"], [("Troy", "Truva")])
        self.assertEqual(plan["4"], [("Troy", "Truva")])


class LockedTermNativeIntegrationTest(unittest.TestCase):
    def test_native_reader_cannot_replace_locked_term(self):
        fixes = [{"id": "1", "fixed": "Hükümdar geliyor."}]

        class FakeCompletions:
            def create(self, **_kwargs):
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(
                            content=ht.json.dumps(fixes, ensure_ascii=False)
                        )
                    )],
                )

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        fake_module = SimpleNamespace(OpenAI=FakeOpenAI)
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "İmparator geliyor.")]
        with patch.dict(sys.modules, {"openai": fake_module}):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="test",
                src_map={"1": "The Emperor is coming."},
                locked_terms={"Emperor": "İmparator"},
            )

        self.assertEqual(result, blocks)

    def test_qc_api_and_fallback_cannot_replace_locked_term(self):
        issue = {
            "id": "1",
            "original": "The Emperor is coming.",
            "current": "İmparator geliyor.",
            "problem": "wording",
            "suggestion": "Hükümdar geliyor.",
        }

        class FakeCompletions:
            def create(self, **_kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content="Hükümdar geliyor.")
                    )]
                )

        class FakeOpenAI:
            def __init__(self, **_kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        fake_module = SimpleNamespace(OpenAI=FakeOpenAI)
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "İmparator geliyor.")]
        with patch.dict(sys.modules, {"openai": fake_module}):
            result = ht.qc_auto_fix(
                [issue],
                blocks,
                helper_api_key="test",
                model="gpt-5.4-mini",
                locked_terms={"Emperor": "İmparator"},
            )
        self.assertEqual(result, blocks)


if __name__ == "__main__":
    unittest.main()
