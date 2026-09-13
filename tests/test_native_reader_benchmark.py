import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import native_reader_benchmark as benchmark


class _FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        return object()


class _FakeClient:
    def __init__(self, completions=None):
        self.base_url = "https://example.invalid/v1"
        self.completions = completions or _FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)

    def with_options(self, **_options):
        return _FakeClient(self.completions)


class NativeReaderBenchmarkTest(unittest.TestCase):
    def test_corpus_has_twenty_bad_and_fifteen_positive_controls(self):
        cases = benchmark.build_native_reader_corpus()
        self.assertEqual(
            benchmark.validate_corpus(cases),
            {"case_count": 35, "translationese": 20, "positive_controls": 15})
        self.assertEqual(len({row["source"] for row in cases}), 35)
        self.assertEqual(len({row["current"] for row in cases}), 35)

    def test_only_enhanced_prompt_contains_new_rules(self):
        cases = benchmark.build_native_reader_corpus()
        baseline = benchmark.build_variant_prompt(cases, enhanced=False)
        enhanced = benchmark.build_variant_prompt(cases, enhanced=True)
        self.assertNotIn("DOĞAL TÜRKÇE KONTROLÜ", baseline)
        self.assertIn("DOĞAL TÜRKÇE KONTROLÜ", enhanced)
        self.assertIn("cue birleştirme", baseline)
        self.assertIn("konuşmacı veya sahne sınırını asla geçme", enhanced)

    def test_prepare_never_uses_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = benchmark.prepare(tmp)
            self.assertEqual(result["case_count"], 35)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["live_api_used"])
            self.assertTrue((Path(tmp) / "corpus.json").exists())

    def test_budget_blocks_before_network(self):
        raw = _FakeClient()
        client = benchmark.BudgetedClient(raw, "model", 0.000001, 1.0, 1.0)
        with self.assertRaisesRegex(ValueError, "budget_exhausted"):
            client.chat.completions.create(
                model="model", messages=[{"role": "user", "content": "x"}],
                max_tokens=100)
        self.assertEqual(raw.completions.calls, 0)
        with self.assertRaisesRegex(ValueError, "route_or_key_change"):
            client.with_options(base_url="https://other.invalid/v1")

    def test_blind_review_is_deterministic_and_scoring_unblinds(self):
        cases = benchmark.build_native_reader_corpus()
        baseline = {row["id"]: row["current"] for row in cases}
        enhanced = {row["id"]: row["current"] + "!" for row in cases}
        review = benchmark.build_blind_review(cases, baseline, enhanced, "seed")
        self.assertEqual(review, benchmark.build_blind_review(cases, baseline, enhanced, "seed"))
        self.assertEqual({row["_enhanced_side"] for row in review}, {"X", "Y"})
        for row in review:
            row["fidelity_X_1_to_5"] = 4
            row["fidelity_Y_1_to_5"] = 4
            row["naturalness_X_1_to_5"] = 4
            row["naturalness_Y_1_to_5"] = 4
            row["preferred"] = row["_enhanced_side"]
        score = benchmark.score_review(review)
        self.assertEqual(score["enhanced"]["preferred_wins"], 35)
        self.assertEqual(score["positive_controls"]["baseline_changed"], 0)
        self.assertEqual(score["positive_controls"]["enhanced_changed"], 15)

    def test_live_preflight_rejects_insufficient_budget_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "hiçbir API çağrılmadı"), \
                    patch("openai.OpenAI") as openai:
                benchmark.run_live_ab(
                    tmp, "model", "https://example.invalid/v1", "secret",
                    0.000000001, 1.0, 1.0)
            openai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
