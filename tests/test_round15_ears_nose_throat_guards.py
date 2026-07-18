import unittest

import hybrid_translate as ht


class EarsNoseThroatResidueFixTest(unittest.TestCase):
    def test_ent_phrase_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("gulak, burun we bokurdak doktoru")[0],
            "kulak, burun ve boğaz doktoru",
        )

    def test_ent_with_suffix_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("bir gulak, burun we bokurdakla")[0],
            "bir kulak, burun ve boğazla",
        )

    def test_sentence_initial_gulak_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Gulak 450 dolarsa")[0],
            "Kulak 450 dolarsa",
        )


    def test_sentence_initial_bokurdak_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Bokurdak ilginç bir parça")[0],
            "Boğaz ilginç bir parça",
        )

    def test_all_caps_ent_phrase_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("GULAK, BURUN WE BOKURDAK DOKTORU")[0],
            "KULAK, BURUN VE BOĞAZ DOKTORU",
        )

    def test_all_caps_single_word_cleanup(self):
        self.assertEqual(ht._apply_local_fixes("GULAK 450 DOLARSA")[0], "KULAK 450 DOLARSA")
        self.assertEqual(ht._apply_local_fixes("BOKURDAK ILGINC")[0], "BOĞAZ ILGINC")
    def test_source_lang_leftover_matches_ent_family(self):
        for word in ("gulak", "gulah", "gulagy", "gulakla", "bokurdak", "bokurdag", "bogurdak", "we"):
            self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search(word), word)

    def test_turkic_drift_matches_ent_family(self):
        for word in ("gulak", "gulah", "gulagy", "bokurdak", "bokurdag", "bogurdak", "we"):
            self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search(word), word)


class OdditiesIntroCleanupTest(unittest.TestCase):
    def test_intro_cleanup_one_line(self):
        self.assertEqual(
            ht._apply_local_fixes('TUHAF DÜNYASINA HOŞ GELDİNİZ "ODDITIES"İN')[0],
            '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz',
        )

    def test_intro_cleanup_with_line_break(self):
        self.assertEqual(
            ht._apply_local_fixes('TUHAF DÜNYASINA HOŞ GELDİNİZ\n"ODDITIES"İN')[0],
            '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz',
        )


class ElimizdeGecenCleanupTest(unittest.TestCase):
    def test_specific_phrase_only(self):
        self.assertEqual(ht._apply_local_fixes("elimizde geçen")[0], "elimizden geçen")
        self.assertEqual(ht._apply_local_fixes("elimizde duruyor")[0], "elimizde duruyor")


class FinalConsistencySafetyTest(unittest.TestCase):
    class _Cue:
        def __init__(self, index, start, end, text):
            self.index = index
            self.start = start
            self.end = end
            self.text = text

    def test_final_sweep_rejects_content_loss_candidate(self):
        cues = [
            self._Cue("1", "00:00:01,000", "00:00:02,000", "Marketed as toys, but"),
            self._Cue("2", "00:00:02,100", "00:00:03,000", "Other line."),
            self._Cue("3", "00:00:03,100", "00:00:04,000", "Marketed as toys, but"),
        ]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Oyuncak diye pazarlanıyor ama"),
            ("2", "00:00:02,100 --> 00:00:03,000", "Başka satır."),
            ("3", "00:00:03,100 --> 00:00:04,000", "ama 19. yüzyılda"),
        ]
        swept, fixes = ht.final_consistency_sweep(cues, blocks)
        self.assertEqual(fixes, 0)
        self.assertEqual(swept[2][2], "ama 19. yüzyılda")


if __name__ == "__main__":
    unittest.main()
