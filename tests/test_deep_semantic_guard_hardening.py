"""Focused regressions for conservative Turkish semantic candidate guards."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class NumericGuardTest(unittest.TestCase):
    def test_rejects_number_invented_by_polish(self):
        ok, reason = ht.validate_polish_candidate(
            "Yarın geliyorum.", "Yarın saat 3'te geliyorum."
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "numbers")

    def test_rejects_extra_number_not_in_source(self):
        ok, reason = ht.validate_polish_candidate(
            "2 elmam var.", "2 değil 3 elmam var.",
            source_text="I have 2 apples.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "numbers")

    def test_allows_equivalent_thousands_format(self):
        ok, reason = ht.validate_polish_candidate(
            "1.000 kişi geldi.", "1000 kişi geldi."
        )
        self.assertTrue(ok, reason)


class TurkishMeaningGuardTest(unittest.TestCase):
    def test_rejects_because_negation_scope_reversal(self):
        ok, reason = ht.validate_polish_candidate(
            "O, kadın kaldığı için gitmedi.",
            "O gitti çünkü kadın kalmadı.",
            source_text="He did not leave because she stayed.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "negation_scope")

    def test_rejects_first_person_to_third_person(self):
        ok, reason = ht.validate_polish_candidate("Geldim.", "Geldi.")
        self.assertFalse(ok)
        self.assertEqual(reason, "person_drift")

    def test_rejects_source_backed_plural_loss(self):
        ok, reason = ht.validate_polish_candidate(
            "Çocuklar geldi.", "Çocuk geldi.",
            source_text="The children arrived.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "plural_drift")

    def test_rejects_source_backed_possessive_person_swap(self):
        ok, reason = ht.validate_polish_candidate(
            "Arabam bozuldu.", "Arabası bozuldu.",
            source_text="My car broke down.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "possessive_drift")

    def test_rejects_comparative_to_superlative(self):
        ok, reason = ht.validate_polish_candidate(
            "Bu daha ucuz.", "Bu en ucuz."
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "comparison_degree")

    def test_rejects_question_predicate_swap(self):
        ok, reason = ht.validate_polish_candidate(
            "O ayrıldı mı?", "O geldi mi?", source_text="Did he leave?"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "question_content_drift")

    def test_allows_relative_clause_question_rewrite(self):
        ok, reason = ht.validate_polish_candidate(
            "Bunu kim yaptı?", "Bunu yapan kim?", source_text="Who did this?"
        )
        self.assertTrue(ok, reason)


class LockedTermAndLeakGuardTest(unittest.TestCase):
    def test_rejects_locked_proper_name_derivation(self):
        ok, reason = ht.validate_polish_candidate(
            "Mars'a gittik.", "Marslılara gittik.",
            source_text="We went to Mars.", locked_terms={"Mars": "Mars"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "locked_term_violation")

    def test_flags_capitalized_foreign_common_noun_when_not_in_source(self):
        ok, reason = ht.validate_polish_candidate(
            "Kız gitti.", "Mädchen gitti.", source_text="The girl left."
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "non_turkish_target")

    def test_preserves_capitalized_source_name_with_diacritic(self):
        ok, reason = ht.validate_polish_candidate(
            "Buñuel geldi.", "Buñuel nihayet geldi.",
            source_text="Buñuel finally arrived.",
        )
        self.assertTrue(ok, reason)

    def test_semantic_guard_allows_source_licensed_case_correction(self):
        blocks = [("1", "00:00:00,000 --> 00:00:02,000", "Babil'in yaşadılar.")]
        src_map = {"1": "They lived in Babylon."}
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=ht.json.dumps([{
                "cluster": "c1",
                "fixes": [{"id": "1", "text": "Babil'de yaşadılar.", "reason": "case"}],
            }], ensure_ascii=False)))],
        )
        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=response):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                locked_terms={"Babylon": "Babil"},
            )
        self.assertEqual(result[0][2], "Babil'de yaşadılar.")
        self.assertEqual(stats["fixed"], 1)

    def test_semantic_guard_rejects_wrong_case_vowel_for_locked_name(self):
        blocks = [("1", "00:00:00,000 --> 00:00:02,000", "Sweet Seventeen'den geldiler.")]
        src_map = {"1": "They came from Sweet Seventeen."}
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=ht.json.dumps([{
                "cluster": "c1",
                "fixes": [{"id": "1", "text": "Sweet Seventeen'dan geldiler.", "reason": "case"}],
            }], ensure_ascii=False)))],
        )
        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=response):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                locked_terms={"Sweet Seventeen": "Sweet Seventeen"},
            )
        self.assertEqual(result[0][2], "Sweet Seventeen'den geldiler.")
        self.assertEqual(stats["rejected"], 1)


class SemanticFallbackGuardTest(unittest.TestCase):
    def test_rejects_unverified_semantic_rewrite_instead_of_self_comparing(self):
        ok, reason = ht.validate_semantic_reconciliation_candidate(
            "Kayıp çocuğu ormanda buldular.",
            "Kayıp çocuğu şehirde bıraktılar.",
            source_text="They found the missing child in the forest.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "semantic_rewrite_unverified")


if __name__ == "__main__":
    unittest.main()
