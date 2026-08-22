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
        self.assertGreaterEqual(source.count("_tm_context_fingerprint("), 6)

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

    def test_effective_file_terms_resolve_casefold_conflicts_by_precedence(self):
        terms = gui._hybrid_file_locked_terms(
            {"Oracle": "Kahin"},
            (SimpleNamespace(recurring_terms={"oracle": "Kehanet"}),),
            {"oracle": "Kullanıcı Kararı"},
            "Turkish",
        )

        self.assertEqual(terms, {"oracle": "Kullanıcı Kararı"})

    def test_analysis_term_changes_tm_fingerprint(self):
        source_hash = "b" * 64
        static = {"Oracle": "Kahin"}
        first = gui._hybrid_file_locked_terms(
            static, (SimpleNamespace(recurring_terms={}),), {}, "Turkish")
        changed = gui._hybrid_file_locked_terms(
            static, (SimpleNamespace(recurring_terms={"Vessel": "Kap"}),), {}, "Turkish")

        self.assertNotEqual(
            gui._tm_context_fingerprint(source_hash, first),
            gui._tm_context_fingerprint(source_hash, changed),
        )

    def test_effective_locks_override_conflicting_analysis_terms_in_prompt(self):
        import hybrid_translate as ht

        context = SimpleNamespace(
            summary="", setting="", tone="", characters=[], scene_notes=[],
            recurring_terms={"Georgia": "GÃ¼rcistan"},
        )
        prompt = ht.build_system_prompt(
            context, "English", "Turkish",
            locked_terms={"Georgia": "Georgia eyaleti"},
        )

        self.assertIn("Georgia eyaleti", prompt)
        self.assertNotIn("rcistan", prompt)

    def test_phase_two_reuses_current_file_terms_for_every_quality_pass(self):
        source = inspect.getsource(gui.App._run_hybrid)
        phase_two = source.split("FAZ 2", 1)[1]

        self.assertIn("_file_locked_terms = _hybrid_file_locked_terms(", phase_two)
        self.assertIn("locked_terms=_file_locked_terms", phase_two)
        self.assertIn("glossary=_file_locked_terms", phase_two)
        # Aynı gerekçe: analiz katkısı kanonik bağlamda.
        self.assertIn("_analysis_fp = _analysis_prompt_fingerprint(", source)
        self.assertIn("filepath, tgt, _analysis_fp)", source)
        self.assertNotIn("dict(glossary or {})", phase_two)
        self.assertNotIn('getattr(context, "recurring_terms"', phase_two)

    def test_sync_hybrid_uses_effective_locks_for_tm_and_chunk_glossary(self):
        source = inspect.getsource(gui.App._run_sync_hybrid)

        self.assertIn("_locked_terms = _merge_locked_term_sources(", source)
        # Parmak izinin `locked_terms` yuvası GENİŞ sözlüğü taşıyordu; o
        # sözlük ARAMA anında yeniden üretilemediği için hybrid'in yazdığı
        # hiçbir TM kaydı bulunamıyordu (494.907 satır, ~58 isabet).
        # Analizin katkısı artık ayrı bir kanonik bağlam anahtarına giriyor:
        # izolasyon aynen korunuyor (aynı kaynak + farklı analiz -> farklı
        # parmak izi), anahtar ise yeniden üretilebilir hâle geldi.
        self.assertIn("_analysis_fp = _analysis_prompt_fingerprint(", source)
        self.assertIn(
            "self._tm_canonical_context(filepath, tgt, _analysis_fp)", source)
        self.assertIn("chunk_size=self._chunk_size, glossary=_locked_terms", source)
        self.assertIn("locked_terms=_locked_terms", source)

    def test_hybrid_batch_uses_effective_locks_in_system_prompt(self):
        source = inspect.getsource(gui.App._run_hybrid)
        phase_two = source.split("FAZ 2", 1)[1]

        self.assertIn("locked_terms=_file_locked_terms", phase_two)

    def test_hybrid_batch_stores_tm_with_the_same_effective_fingerprint(self):
        source = inspect.getsource(gui.App._run_hybrid)
        store = source.index("self._store_tm_pairs(")
        store_end = source.index("if (not _hybrid_quality_failed", store)
        self.assertIn(
            "context_fingerprint=_tm_fingerprint",
            source[store:store_end],
        )


if __name__ == "__main__":
    unittest.main()
