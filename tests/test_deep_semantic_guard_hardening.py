"""Focused regressions for conservative Turkish semantic candidate guards."""

import unittest
import json
import sys
import tempfile
from pathlib import Path
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


class CondenseSourceNameGuardTest(unittest.TestCase):
    def test_allows_source_preserved_name_with_diacritic(self):
        ok, reason = ht.validate_condense_candidate(
            "Buñuel burada.", "Buñuel burada.",
            source_text="Buñuel is here.",
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

    def test_rejects_dative_recipient_swap_when_subject_is_retained(self):
        ok, reason = ht.validate_polish_candidate(
            "O ona verdi.", "O bana verdi.",
            source_text="He gave it to her.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "critical_fact_swap")

    def test_rejects_source_backed_obligation_to_possibility(self):
        ok, reason = ht.validate_polish_candidate(
            "Gitmek zorundasın.", "Gitmek isteyebilirsin.",
            source_text="You must leave.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_modality")

    def test_allows_unclassified_rephrasing_of_source_obligation(self):
        ok, reason = ht.validate_polish_candidate(
            "Gitmek zorundasın.", "Git.", source_text="You must leave.",
        )
        self.assertTrue(ok, reason)

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


class SemanticResponseIntegrityTest(unittest.TestCase):
    def test_salvages_complete_cluster_from_truncated_response(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:02,000", "Merhaba!"),
            ("2", "00:00:02,000 --> 00:00:04,000", "Elveda."),
        ]
        clusters = [
            {"cluster": "c1", "items": [{
                "id": "1", "source": "Hello!", "translation": "Merhaba!",
                "suspect": True, "reasons": ["POST_PASS_CHANGED"],
            }], "suspect_ids": ["1"]},
            {"cluster": "c2", "items": [{
                "id": "2", "source": "Goodbye.", "translation": "Elveda.",
                "suspect": True, "reasons": ["POST_PASS_CHANGED"],
            }], "suspect_ids": ["2"]},
        ]
        raw = (
            '[{"cluster":"c1","fixes":[{"id":"1","text":"Merhaba.",'
            '"reason":"punctuation"}]},{"cluster":"c2","fixes":[{"id":"2"'
        )
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
        )
        with patch("openai.OpenAI"), \
             patch("hybrid_translate.build_semantic_reconciliation_clusters", return_value=clusters), \
             patch("hybrid_translate._safe_chat_create", return_value=response):
            result, stats = ht.semantic_reconciliation_pass(
                {"1": "Hello!", "2": "Goodbye."}, blocks,
                api_key="k", model="m", changed_ids={"1", "2"},
            )
        self.assertEqual(result[0][2], "Merhaba.")
        self.assertEqual(result[1][2], "Elveda.")
        self.assertEqual(stats["fixed"], 1)
        self.assertTrue(any(
            detail.get("status") == "partial_response"
            for detail in stats["details"]
        ))

    def test_json_array_salvages_only_complete_objects_when_requested(self):
        raw = '[{"id":"1","fixed":"Merhaba."},{"id":"2","fixed":"yarım'
        self.assertEqual(ht._extract_json_array(raw), "")
        self.assertEqual(
            json.loads(ht._extract_json_array(raw, salvage_truncated=True)),
            [{"id": "1", "fixed": "Merhaba."}],
        )


class NativeFragmentAtomicityTest(unittest.TestCase):
    def test_rejects_entire_fragment_when_one_returned_fix_fails_guard(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:02,000", "<i>Onları görünce</i>"),
            ("2", "00:00:02,000 --> 00:00:04,000", "eski aşkım gelir aklıma."),
        ]
        fixes = [
            {"id": "1", "fixed": "Onları görünce"},
            {"id": "2", "fixed": "Aklıma eski aşkım geliyor."},
        ]
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=json.dumps(fixes, ensure_ascii=False)))],
        )
        fake_openai = SimpleNamespace(OpenAI=lambda **_kwargs: object())
        with patch.dict(sys.modules, {"openai": fake_openai}), \
             patch("hybrid_translate._safe_chat_create", return_value=response) as chat:
            result = ht.native_reader_pass(
                blocks, helper_api_key="k",
                src_map={"1": "Seeing them", "2": "of an old love."},
            )
        self.assertEqual(result, blocks)
        self.assertEqual(chat.call_count, 1)

    def test_native_pass_applies_complete_fix_before_truncated_tail(self):
        blocks = [("1", "00:00:00,000 --> 00:00:02,000", "Merhaba!")]
        raw = '[{"id":"1","fixed":"Merhaba."},{"id":"2","fixed":"yarım'
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
        )
        fake_openai = SimpleNamespace(OpenAI=lambda **_kwargs: object())
        with patch.dict(sys.modules, {"openai": fake_openai}), \
             patch("hybrid_translate._safe_chat_create", return_value=response):
            result = ht.native_reader_pass(blocks, helper_api_key="k")
        self.assertEqual(result[0][2], "Merhaba.")


class BatchSourcePreservationTest(unittest.TestCase):
    def test_batch_output_keeps_source_preserved_name(self):
        response_line = json.dumps({
            "custom_id": "c1",
            "response": {"body": {"choices": [{"message": {
                "content": '[{"i":"1","t":"Buñuel geldi."}]',
            }}]}},
        }, ensure_ascii=False)
        client = SimpleNamespace(
            files=SimpleNamespace(content=lambda _file_id: SimpleNamespace(text=response_line)),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out.srt"
            with patch("openai.OpenAI", return_value=client):
                written, marked = ht.save_results(
                    "k", "out", {"c1": [("1", "00:00:00,000", "00:00:02,000")]},
                    str(output),
                    src_cues=[SimpleNamespace(index="1", text="Buñuel arrived.")],
                )
            final = output.read_text(encoding="utf-8")
        self.assertEqual(written, 1)
        self.assertEqual(marked, 0)
        self.assertIn("Buñuel geldi.", final)
        self.assertNotIn("HATA_NON_TURKISH_TARGET", final)


if __name__ == "__main__":
    unittest.main()
