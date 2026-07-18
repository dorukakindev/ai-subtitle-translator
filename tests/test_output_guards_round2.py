"""Tests for 5 small output-driven guards (King Tut round 2)."""
import unittest
import hybrid_translate as ht


class SingleLetterTargetTest(unittest.TestCase):
    def test_single_letter_b_flagged(self):
        class FakeCue:
            index = 1
            text = "This is a very important scene in the movie"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "B")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "SINGLE_LETTER_TARGET" in r]
        self.assertEqual(len(reasons), 1)

    def test_single_letter_short_source_not_flagged(self):
        class FakeCue:
            index = 1
            text = "Hi"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "B")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "SINGLE_LETTER_TARGET" in r]
        self.assertEqual(len(reasons), 0)

    def test_single_digit_not_flagged(self):
        class FakeCue:
            index = 1
            text = "This is a very important scene in the movie"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "5")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "SINGLE_LETTER_TARGET" in r]
        self.assertEqual(len(reasons), 0)


class OrphanFragmentExtended2Test(unittest.TestCase):
    def test_orphan_artik_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "Now we need to consider the full implications of this finding",
                "Artık",
            )
        )

    def test_orphan_dedigimizde_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "This is what we mean when we talk about the ancient tradition",
                "dediğimizde,",
            )
        )

    def test_orphan_sonra_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "The king then ordered his guards to bring the prisoner forward",
                "sonra",
            )
        )

    def test_not_orphan_valid_turkish(self):
        self.assertFalse(
            ht._has_orphan_fragment(
                "the ones",
                "olanlar",
            )
        )


class PolishQuestionRegressionTest(unittest.TestCase):
    def test_question_regression_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Kafası kesilmiş halde gömülen adam kim?",
            "Kafası kesik adam gömülü halde kim?",
        )
        self.assertFalse(ok)
        self.assertIn("question_regression", reason)

    def test_question_no_false_positive_same_structure(self):
        ok, reason = ht.validate_polish_candidate(
            "Kafası kesilmiş halde gömülen adam kim?",
            "Kafası kesilmiş gömülen adam kim?",
        )
        self.assertTrue(ok)

    def test_question_no_kim_not_affected(self):
        ok, reason = ht.validate_polish_candidate(
            "Nasıl gidiyor?",
            "N'aber?",
        )
        self.assertTrue(ok)


class HoldsWaterIdiomTest(unittest.TestCase):
    def test_holds_water_bad_translation_flagged(self):
        self.assertTrue(
            ht._has_idiom_holds_water(
                "that theory doesn't hold water",
                "bu teori ayakta duran değil",
            )
        )

    def test_holds_water_empty_not_flagged(self):
        self.assertFalse(
            ht._has_idiom_holds_water("", "geçerli")
        )

    def test_holds_water_no_source_not_flagged(self):
        self.assertFalse(
            ht._has_idiom_holds_water(
                "the building stands tall",
                "bina ayakta duruyor",
            )
        )

    def test_holds_water_in_run_validators(self):
        class FakeCue:
            index = 1
            text = "that theory doesn't hold water"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "bu teori ayakta duran değil")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "HOLDS" in r or "holds" in r]
        self.assertEqual(len(reasons), 1)


class NeighborPrefixEchoAggressiveTest(unittest.TestCase):
    def test_single_word_prefix_echo_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "bunu dediğimizde"),
            ("2", "00:00:05 --> 00:00:08", "dediğimizde başka şey"),
        ]
        self.assertTrue(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_single_word_no_echo_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "bunu dediğimizde"),
            ("2", "00:00:05 --> 00:00:08", "şimdi başka şey"),
        ]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_short_word_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "bu da"),
            ("2", "00:00:05 --> 00:00:08", "da ne"),
        ]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_single_word_in_run_validators(self):
        class FakeCue:
            index = 1
            text = "some text"
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "sonra dediğimizde"),
            ("2", "00:00:05 --> 00:00:08", "dediğimizde başka"),
        ]
        suspicious = ht.run_validators(blocks, cues=[FakeCue(), FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "NEIGHBOR_PREFIX_ECHO" in r]
        self.assertGreaterEqual(len(reasons), 1)


if __name__ == "__main__":
    unittest.main()
