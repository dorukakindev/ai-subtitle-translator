import inspect
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class HybridBatchTermIsolationTests(unittest.TestCase):
    def test_locked_term_source_merge_keeps_uppercase_acronym_distinct(self):
        terms = gui._merge_locked_term_sources(
            {"Us": "Bizi"},
            {"US": "ABD"},
            {"us": "biz"},
        )

        self.assertEqual(terms, {"us": "biz", "US": "ABD"})

    def test_tm_fingerprint_changes_with_locked_term_policy(self):
        source_hash = "a" * 64
        first = gui._tm_context_fingerprint(
            source_hash, {"US": "ABD", "Parish": "Cemaat"})
        reordered = gui._tm_context_fingerprint(
            source_hash, {"Parish": "Cemaat", "US": "ABD"})
        changed = gui._tm_context_fingerprint(
            source_hash, {"US": "bize", "Parish": "Cemaat"})

        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)
        self.assertEqual(gui._tm_context_fingerprint("", {"US": "ABD"}), "")

    def test_all_translation_flows_bind_tm_to_current_term_policy(self):
        source = inspect.getsource(gui.App)

        self.assertNotIn("context_fingerprint=_expected_source_hash", source)
        self.assertGreaterEqual(source.count("_tm_context_fingerprint("), 7)

    def test_each_file_builds_an_isolated_locked_term_set(self):
        first = gui._hybrid_file_locked_terms(
            {"Empire": "İmparatorluk"},
            (SimpleNamespace(recurring_terms={"Captain": "Yüzbaşı"}),),
            {"Mary": "Mary"},
            "Turkish",
        )
        second = gui._hybrid_file_locked_terms(
            {"Parish": "Cemaat"},
            (SimpleNamespace(recurring_terms={"Priest": "Rahip"}),),
            {"John": "John"},
            "Turkish",
        )

        self.assertEqual(
            first,
            {"Empire": "İmparatorluk", "Captain": "Yüzbaşı", "Mary": "Mary"},
        )
        self.assertEqual(
            second,
            {"Parish": "Cemaat", "Priest": "Rahip", "John": "John"},
        )
        self.assertNotIn("Priest", first)
        self.assertNotIn("Captain", second)

    def test_phase_two_reuses_current_file_terms_for_every_quality_pass(self):
        source = inspect.getsource(gui.App._run_hybrid)
        phase_two = source.split("FAZ 2", 1)[1]

        self.assertIn("_file_locked_terms = _hybrid_file_locked_terms(", phase_two)
        self.assertIn("locked_terms=_file_locked_terms", phase_two)
        self.assertIn("glossary=_file_locked_terms", phase_two)
        self.assertNotIn("dict(glossary or {})", phase_two)
        self.assertNotIn('getattr(context, "recurring_terms"', phase_two)


if __name__ == "__main__":
    unittest.main()
