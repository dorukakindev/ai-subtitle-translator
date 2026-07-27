import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


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


if __name__ == "__main__":
    unittest.main()
