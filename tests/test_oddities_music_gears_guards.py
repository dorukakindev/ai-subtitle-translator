"""
S05E13 "Music to My Gears" verified quality fixes.

1. Odities title case regression ("ODDITIES"E → "ODDITIES"in)
2. Obscura grandma typo variants (BÜYÜKANANEMİN/BÜYÜKANANENİN)
3. Neighbor semantic copy guard
4. Turkish question loss guard
5. Untranslated detector: music-only lines ignored
"""

import tempfile
import unittest
from pathlib import Path

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]


# ── 1. Title case regression ──────────────────────────────────────────────

class TitleCaseRegressionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_oddities_e(self):
        ok, reason = self._validate(
            'ODDITIES"İN',
            'ODDITIES"E',
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_title_case_regression")

    def test_local_fix_oddities_e(self):
        result = _APPLY('ODDITIES"E')
        self.assertIn("ODDITIES", result)
        self.assertNotIn('"E', result)

    def test_allows_unchanged(self):
        ok, _ = self._validate(
            'ODDITIES"İN',
            'ODDITIES"İN',
        )
        self.assertTrue(ok)

    def test_title_local_fix_with_context(self):
        result = _APPLY('Mike: TUHAF DÜNYAYA HOŞ GELDİNİZ\n"ODDITIES"E')
        self.assertIn("ODDITIES", result)
        self.assertNotIn('"E', result)


# ── 2. Grandma typo variants ──────────────────────────────────────────────

class GrandmaTypoVariantsTest(unittest.TestCase):
    def test_buyukananemin_fixed(self):
        result = _APPLY('OBSCURA, BÜYÜKANANEMİN ANTİKA DÜKKANI DEĞİL')
        self.assertEqual(result, 'Obscura, anneannenizin antikacısı değil')

    def test_buyukananenin_fixed(self):
        result = _APPLY('OBSCURA, BÜYÜKANANENİN ANTİKA DÜKKANI DEĞİL')
        self.assertEqual(result, 'Obscura, anneannenizin antikacısı değil')

    def test_original_obscura_still_fixed(self):
        result = _APPLY('OBSCURA annenizin antika dükkânı değil')
        self.assertIn('Obscura', result)
        self.assertIn('anneannenizin', result)

    def test_grandma_guard_catches_buyukanane_variants(self):
        _validate = lambda o, n: __import__("hybrid_translate").validate_polish_candidate(o, n)
        ok, reason = _validate(
            "BÜYÜKANANEMİN ANTİKA DÜKKANI",
            "annenizin antika dükkânı",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "grandma_to_mother_regression")


# ── 3. Neighbor semantic copy ─────────────────────────────────────────────

class NeighborSemanticCopyTest(unittest.TestCase):
    def _validate(self, old, new, neighbors=None):
        return __import__("hybrid_translate").validate_polish_candidate(
            old, new, neighbor_texts=neighbors
        )

    def test_rejects_copying_neighbor(self):
        ok, reason = self._validate(
            "bunları toplardı",
            "Zenginler bunları toplardı misafirlerini eğlendirmek için",
            neighbors=["Zenginler bunları misafirlerini eğlendirmek için toplardı"],
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "neighbor_semantic_copy")

    def test_allows_original_already_similar(self):
        ok, _ = self._validate(
            "Zenginler bunları misafirlerini eğlendirmek için toplardı",
            "Zenginler bunları toplardı misafirlerini eğlendirmek için",
            neighbors=["Zenginler bunları misafirlerini eğlendirmek için toplardı"],
        )
        self.assertTrue(ok)

    def test_allows_no_neighbors(self):
        ok, _ = self._validate(
            "bunları toplardı",
            "bunları hep toplardı",
        )
        self.assertTrue(ok)

    def test_allows_unrelated_change(self):
        ok, _ = self._validate(
            "bir şey",
            "başka bir şey",
            neighbors=["tamamen farklı bir konu"],
        )
        self.assertTrue(ok)


# ── 4. Turkish question loss ──────────────────────────────────────────────

class TurkishQuestionLossTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_mi_loss(self):
        ok, reason = self._validate(
            "Mekanik olarak hâlâ çalışıyor mu, yoksa...",
            "Viktorya dönemi koleksiyon parçalarından bazıları.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "turkish_question_loss")

    def test_allows_question_unchanged(self):
        ok, _ = self._validate(
            "Mekanik olarak hâlâ çalışıyor mu?",
            "Mekanik olarak hâlâ çalışıyor mu?",
        )
        self.assertTrue(ok)

    def test_allows_no_question_in_old(self):
        ok, _ = self._validate(
            "Normal bir cümle.",
            "Başka bir cümle.",
        )
        self.assertTrue(ok)

    def test_rejects_yoksa_loss(self):
        ok, reason = self._validate(
            "çalışıyor mu yoksa durdu mu",
            "çalışıyor ve durdu",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "turkish_question_loss")

    def test_allows_mi_in_new_too(self):
        ok, _ = self._validate(
            "çalışıyor mu",
            "hâlâ çalışıyor mu",
        )
        self.assertTrue(ok)


# ── 5. Music-only lines ───────────────────────────────────────────────────

class MusicOnlyUntranslatedTest(unittest.TestCase):
    def test_do_do_do_not_untranslated(self):
        _is_untranslated = __import__(
            "subtitle_translator_gui", fromlist=["_is_untranslated"]
        )._is_untranslated
        self.assertFalse(_is_untranslated("* DO DO-DO *", "* DO DO-DO *"))

    def test_la_la_not_untranslated(self):
        _is_untranslated = __import__(
            "subtitle_translator_gui", fromlist=["_is_untranslated"]
        )._is_untranslated
        self.assertFalse(_is_untranslated("♪ la la ♪", "♪ la la ♪"))

    def test_muzik_not_untranslated(self):
        _is_untranslated = __import__(
            "subtitle_translator_gui", fromlist=["_is_untranslated"]
        )._is_untranslated
        self.assertFalse(_is_untranslated("[MÜZİK]", "[MÜZİK]"))

    def test_music_line_skipped_in_run_validators(self):
        run_validators = __import__(
            "hybrid_translate", fromlist=["run_validators"]
        ).run_validators
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "* DO DO-DO *")]
        result = run_validators(blocks)
        self.assertEqual(len(result), 0)

    def test_real_english_still_detected(self):
        _is_untranslated = __import__(
            "subtitle_translator_gui", fromlist=["_is_untranslated"]
        )._is_untranslated
        self.assertTrue(_is_untranslated("Hello everyone here", "Hello everyone here"))


if __name__ == "__main__":
    unittest.main()
