"""
5 küçük guard/test: drug residue, psychochemical, to NAME reimport,
ORPHAN_FRAGMENT, NEIGHBOR_ECHO, Dar person-drift, local cleanup.
"""
import unittest
import hybrid_translate as ht


class EnglishResidueDrugReimportTest(unittest.TestCase):
    def test_drug_flagged_en_leftover(self):
        self.assertTrue(ht._EN_LEFTOVER.search("She took a drug"))

    def test_drugs_flagged_en_leftover(self):
        self.assertTrue(ht._EN_LEFTOVER.search("illegal drugs"))

    def test_drug_in_local_fix(self):
        text, n = ht._apply_local_fixes("a drug")
        self.assertEqual(text, "bir ilaç")

    def test_drugs_in_local_fix(self):
        text, n = ht._apply_local_fixes("drugs")
        self.assertEqual(text, "ilaçlar")

    def test_drug_residue_blocked_in_polish(self):
        ok, reason = ht.validate_polish_candidate(
            "Bir ilaç aldı.",
            "She took a drug.",
            source_text="She took a drug.",
        )
        self.assertFalse(ok)
        self.assertIn("english_residue", reason or "non_turkish_target")

    def test_psychochemical_fixed(self):
        text, n = ht._apply_local_fixes("psychochemical")
        self.assertEqual(text, "psikokimyasal")

    def test_psychochemicals_fixed(self):
        text, n = ht._apply_local_fixes("psychochemicals")
        self.assertEqual(text, "psikokimyasallar")


class ToNameReimportTest(unittest.TestCase):
    def test_to_name_reimport_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Dün John'a hikayeyi anlattım.",
            "Dün hikayeyi to John anlattım.",
            source_text="Yesterday I told the story to John.",
        )
        self.assertFalse(ok)
        self.assertIn("to_name_reimport", reason)

    def test_to_name_no_false_positive(self):
        ok, reason = ht.validate_polish_candidate(
            "John'a anlattım.",
            "John'a söyledim.",
            source_text="I told to John.",
        )
        self.assertTrue(ok)

    def test_to_name_with_possessive(self):
        ok, reason = ht.validate_polish_candidate(
            "Dün Mary'nin evine gittim.",
            "Dün to Mary'nin evine gittim.",
            source_text="Yesterday I went to Mary's house.",
        )
        self.assertFalse(ok)
        self.assertIn("to_name_reimport", reason)


class OrphanFragmentValidatorTest(unittest.TestCase):
    def test_orphan_filler_only(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "This is a very important message for everyone",
                "şey",
            )
        )

    def test_orphan_short_garbage(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "The captain must address the crew immediately",
                "da",
            )
        )

    def test_not_orphan_valid_translation(self):
        self.assertFalse(
            ht._has_orphan_fragment(
                "The captain addresses the crew",
                "Kaptan ekibe sesleniyor",
            )
        )

    def test_not_orphan_short_source(self):
        self.assertFalse(
            ht._has_orphan_fragment(
                "Hi there",
                "şey",
            )
        )

    def test_run_validators_includes_orphan(self):
        class FakeCue:
            index = 1
            text = "This is a very important message for everyone"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "şey")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "ORPHAN_FRAGMENT" in r]
        self.assertEqual(len(reasons), 1)


class NeighborEchoValidatorTest(unittest.TestCase):
    def test_neighbor_echo_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "orada da"),
            ("2", "00:00:05 --> 00:00:08", "orada da"),
        ]
        self.assertTrue(ht._has_consecutive_echo(blocks, 0))

    def test_neighbor_echo_different_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "orada da"),
            ("2", "00:00:05 --> 00:00:08", "burada da"),
        ]
        self.assertFalse(ht._has_consecutive_echo(blocks, 0))

    def test_neighbor_echo_short_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "ha"),
            ("2", "00:00:05 --> 00:00:08", "ha"),
        ]
        self.assertFalse(ht._has_consecutive_echo(blocks, 0))

    def test_neighbor_echo_out_of_bounds(self):
        blocks = [("1", "00:00:01 --> 00:00:04", "orada da")]
        self.assertFalse(ht._has_consecutive_echo(blocks, 0))

    def test_run_validators_includes_neighbor_echo(self):
        class FakeCue:
            index = 1
            text = "Some text"
        tr_blocks = [
            ("1", "00:00:01 --> 00:00:04", "orada da"),
            ("2", "00:00:05 --> 00:00:08", "orada da"),
        ]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue(), FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "NEIGHBOR_ECHO" in r]
        self.assertGreaterEqual(len(reasons), 1)


class DarPersonDriftValidatorTest(unittest.TestCase):
    def test_he_would_not_know_bilmeme_ihtimali(self):
        self.assertTrue(
            ht._has_dar_person_drift(
                "He would not know the answer",
                "Cevabı bilmeme ihtimali",
            )
        )

    def test_she_wouldnt_know_bilmeme_ihtimali(self):
        self.assertTrue(
            ht._has_dar_person_drift(
                "She wouldn't know the truth",
                "Gerçeği bilmeme ihtimali",
            )
        )

    def test_possibility_he_would_not_know_flagged(self):
        self.assertTrue(
            ht._has_dar_person_drift(
                "Possibility he would not know the result",
                "Sonucu bilmeme ihtimali",
            )
        )

    def test_normal_bilmiyor_not_flagged(self):
        self.assertFalse(
            ht._has_dar_person_drift(
                "He would not know the answer",
                "Cevabı bilmiyor",
            )
        )

    def test_no_source_match_not_flagged(self):
        self.assertFalse(
            ht._has_dar_person_drift(
                "He will go to school",
                "Okula gitme ihtimali",
            )
        )

    def test_run_validators_includes_dar_drift(self):
        class FakeCue:
            index = 1
            text = "He would not know the answer"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "Cevabı bilmeme ihtimali")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "DAR_PERSON_DRIFT" in r]
        self.assertEqual(len(reasons), 1)


class LocalCleanupTest(unittest.TestCase):
    def test_yasadiklari_fixed(self):
        text, n = ht._apply_local_fixes("yasadıkları")
        self.assertEqual(text, "yaşadıkları")

    def test_yasadigi_fixed(self):
        text, n = ht._apply_local_fixes("yaşadığı")
        # already correct
        self.assertEqual(text, "yaşadığı")
        self.assertEqual(n, 0)

    def test_yasadigi_dotless_fixed(self):
        text, n = ht._apply_local_fixes("yasadığı")
        self.assertEqual(text, "yaşadığı")

    def test_iyi_olmayan_muamele_fixed(self):
        text, n = ht._apply_local_fixes("iyi olmayan muamele")
        self.assertEqual(text, "kötü muamele")


if __name__ == "__main__":
    unittest.main()
