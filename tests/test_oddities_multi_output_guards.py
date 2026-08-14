"""
S04E02/E05/E09/E16 polish regression guards.

1. Oddities title: "ODDITIES"'E / "ODDITIES"E / "ODDITIES. " fix + guard
2. Intro: BU İŞİ... İŞİ İYİCE... / işin bilimini çıkardık fix + guard
3. English residue: deal eden
4. Deneyim → Dene regression guard
5. Broken sentence: böyle şeylere.
6. Typo: mikrofom, ONA DE, Woodstoc'a
7. Fragment redistribution: yarattığım yarasayı → seni göstermeyi
"""

import unittest

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]
_VALIDATE = lambda o, n: __import__("hybrid_translate").validate_polish_candidate(o, n)


# ── 1. Oddities title ─────────────────────────────────────────────────

class OdditiesTitleFixTest(unittest.TestCase):
    def test_oddities_e_fixed(self):
        r = _APPLY('"ODDITIES"E')
        self.assertIn('"ODDITIES"in', r)

    def test_oddities_apostrophe_e_fixed(self):
        r = _APPLY('"ODDITIES"\'E')
        self.assertIn('"ODDITIES"in', r)

    def test_oddities_dot_fixed(self):
        r = _APPLY('"ODDITIES. "')
        self.assertNotIn('"ODDITIES. "', r)

    def test_mike_prefix_fixed(self):
        r = _APPLY('Mike: TUHAF DÜNYAYA HOŞ GELDİNİZ\n"ODDITIES"\'E')
        self.assertNotIn('"ODDITIES"\'E', r)
        self.assertIn('ODDITIES', r)

    def test_guard_rejects_e(self):
        ok, reason = _VALIDATE('"ODDITIES"in', '"ODDITIES"E')
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_title_case_regression")

    def test_guard_rejects_apostrophe_e(self):
        ok, reason = _VALIDATE('"ODDITIES"in', '"ODDITIES"\'E')
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_title_case_regression")

    def test_guard_rejects_dot(self):
        ok, reason = _VALIDATE('"ODDITIES"in', '"ODDITIES. "')
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_title_case_regression")

    def test_guard_allows_unchanged(self):
        ok, _ = _VALIDATE('"ODDITIES"in', '"ODDITIES"in')
        self.assertTrue(ok)


# ── 2. Intro / mastery phrase ─────────────────────────────────────────

class IntroPhraseFixTest(unittest.TestCase):
    def test_bu_isi_tekrari_fixed(self):
        r = _APPLY('BU İŞİ... İŞİ İYİCE USTALIĞA DÖKMEYE')
        self.assertNotIn('İŞİ... İŞİ', r)
        self.assertIn('ustalaşmaya', r)

    def test_isin_bilimini_cikardik_fixed(self):
        r = _APPLY('işin bilimini çıkardık')
        self.assertNotIn('bilimini çıkardık', r)
        self.assertIn('tekniğini oturttuk', r)

    def test_guard_rejects_bilimini_cikardik(self):
        ok, reason = _VALIDATE('tekniğini oturttuk', 'işin bilimini çıkardık')
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_guard_rejects_ustaliga_dokmek(self):
        ok, reason = _VALIDATE('ustalaştık', 'ustalığa dökmek')
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_guard_allows_normal(self):
        ok, _ = _VALIDATE('ustalaştık', 'iyice ustalaştık')
        self.assertTrue(ok)


# ── 3. English residue: deal eden ─────────────────────────────────────

class DealEdenFixTest(unittest.TestCase):
    def test_deal_eden_fixed(self):
        r = _APPLY('böyle tuhaf şeylerle deal eden birine danışmak isterim.')
        self.assertNotIn('deal eden', r)
        self.assertIn('uğraşan', r)

    def test_deal_eden_in_en_leftover(self):
        import hybrid_translate as ht
        self.assertTrue(ht._EN_LEFTOVER.search("deal eden"))
        self.assertTrue(ht._EN_LEFTOVER.search("DEAL EDEN"))


# ── 4. Deneyim → Dene ────────────────────────────────────────────────

class DeneyimDeneTest(unittest.TestCase):
    def test_guard_rejects_deneyim_to_dene(self):
        ok, reason = _VALIDATE('Neden olmasın? Deneyim.', 'Neden olmasın? Dene.')
        self.assertFalse(ok)
        self.assertEqual(reason, "first_person_intent_shift")

    def test_guard_rejects_deneyeyim_to_dene(self):
        ok, reason = _VALIDATE('bir deneyeyim', 'dene bir')
        self.assertFalse(ok)

    def test_guard_allows_unchanged(self):
        ok, _ = _VALIDATE('bir deneyeyim', 'bir deneyeyim')
        self.assertTrue(ok)

    def test_guard_allows_dene_when_no_old_intent(self):
        ok, _ = _VALIDATE('şunu dene', 'bunu dene')
        self.assertTrue(ok)


# ── 5. Broken sentence ───────────────────────────────────────────────

class BrokenSentenceFixTest(unittest.TestCase):
    def test_boyle_seylere_fixed(self):
        r = _APPLY('kanser, tümörler, enfeksiyonlar,\nböyle şeylere.')
        self.assertNotIn('şeylere.', r)
        self.assertIn('şeyler yani', r)


# ── 6. Typo cleanup ──────────────────────────────────────────────────

class TypoFixTest(unittest.TestCase):
    def test_mikrofom_fixed(self):
        r = _APPLY('mikrofom')
        self.assertEqual(r, 'mikrofon')

    def test_ona_de_imperative_preserved(self):
        r = _APPLY('ona de ki')
        self.assertEqual(r, 'ona de ki')

    def test_ona_de_uppercase_imperative_preserved(self):
        r = _APPLY('ONA DE')
        self.assertEqual(r, 'ONA DE')

    def test_woodstoc_a_fixed(self):
        r = _APPLY("Woodstoc'a")
        self.assertEqual(r, "Woodstock'a")

    def test_guard_rejects_woodstoc(self):
        ok, reason = _VALIDATE('WOODSTOCK festivali', 'Woodstoc festivali')
        self.assertFalse(ok)
        self.assertEqual(reason, "proper_noun_regression")

    def test_guard_allows_woodstock_unchanged(self):
        ok, _ = _VALIDATE('WOODSTOCK', 'Woodstock')
        self.assertTrue(ok)


# ── 7. Fragment redistribution ───────────────────────────────────────

class FragmentRedistributionTest(unittest.TestCase):
    def test_guard_rejects_fragment_shift(self):
        ok, reason = _VALIDATE(
            'yarattığım yarasayı göstereceğimi',
            'seni göstermeyi',
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "fragment_redistribution_regression")

    def test_guard_allows_normal_change(self):
        ok, _ = _VALIDATE('yarattığım yarasayı', 'yarattığım yarasayı')
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
