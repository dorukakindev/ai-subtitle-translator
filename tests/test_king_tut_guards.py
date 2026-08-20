"""Tests for King Tut output-driven guards."""
import unittest
import hybrid_translate as ht


class BoyKingPharaohResidueTest(unittest.TestCase):
    def test_boy_king_fixed_to_cocuk_kral(self):
        text, n = ht._apply_local_fixes("the Boy King")
        self.assertIn("Çocuk Kral", text)

    def test_boy_king_lowercase(self):
        text, n = ht._apply_local_fixes("boy king")
        self.assertIn("Çocuk Kral", text)

    def test_pharaoh_not_in_en_leftover(self):
        self.assertFalse(ht._EN_LEFTOVER.search("pharaoh"))

    def test_pharaoh_not_in_local_fixes(self):
        text, n = ht._apply_local_fixes("pharaoh")
        self.assertEqual(text, "pharaoh")

class NeighborPrefixEchoTest(unittest.TestCase):
    def test_prefix_echo_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "olmadığını anlamak için"),
            ("2", "00:00:05 --> 00:00:08", "olmadığını anlamak için denedi"),
        ]
        self.assertTrue(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_prefix_echo_different_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "olmadığını anlamak için"),
            ("2", "00:00:05 --> 00:00:08", "bunu anlamak için denedi"),
        ]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_prefix_echo_short_not_flagged(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "ha ha"),
            ("2", "00:00:05 --> 00:00:08", "ha ha ha"),
        ]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_prefix_echo_out_of_bounds(self):
        blocks = [("1", "00:00:01 --> 00:00:04", "test")]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_font_attributes_do_not_create_prefix_echo(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:04", '<font color="#fff">İlk cümle.</font>'),
            ("2", "00:00:05 --> 00:00:08", '<font color="#fff">Başka bir cümle.</font>'),
        ]
        self.assertFalse(ht._has_neighbor_prefix_echo(blocks, 0))

    def test_source_speaker_label_removal_is_not_a_mismatch(self):
        class FakeCue:
            index = 1
            text = "NTP: This is the real dialogue."

        suspicious = ht.run_validators(
            [("1", "00:00:01 --> 00:00:04", "Bu gerçek diyalogdur.")],
            cues=[FakeCue()],
            tgt_lang="Türkçe",
        )
        reasons = "|".join(reason for *_rest, reason in suspicious)
        self.assertNotIn("SPEAKER_LABEL_MISMATCH", reasons)

    def test_target_only_speaker_label_is_still_a_mismatch(self):
        class FakeCue:
            index = 1
            text = "This is the real dialogue."

        suspicious = ht.run_validators(
            [("1", "00:00:01 --> 00:00:04", "ANLATICI: Bu gerçek diyalogdur.")],
            cues=[FakeCue()],
            tgt_lang="Türkçe",
        )
        reasons = "|".join(reason for *_rest, reason in suspicious)
        self.assertIn("SPEAKER_LABEL_MISMATCH", reasons)

    def test_prefix_echo_in_run_validators(self):
        class FakeCue:
            index = 1
            text = "some text"
        blocks = [
            ("1", "00:00:01 --> 00:00:04", "inceleme gerekiyor"),
            ("2", "00:00:05 --> 00:00:08", "inceleme gerekiyor şimdi"),
        ]
        suspicious = ht.run_validators(blocks, cues=[FakeCue(), FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "NEIGHBOR_PREFIX_ECHO" in r]
        self.assertGreaterEqual(len(reasons), 1)

    def test_prefix_echo_polish_reject(self):
        ok, reason = ht.validate_polish_candidate(
            "bunu denedik",
            "anlamak için denedik",
            neighbor_texts=["olmadığını anlamak için"],
        )
        self.assertFalse(ok)
        self.assertIn("neighbor_prefix_echo", reason)

    def test_prefix_echo_polish_no_false_positive(self):
        ok, reason = ht.validate_polish_candidate(
            "bunu denedik",
            "denedik bunu",
            neighbor_texts=["olmadığını anlamak için"],
        )
        self.assertTrue(ok)


class OrphanFragmentExtendedTest(unittest.TestCase):
    def test_orphan_ve_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "this is a very important thing we must discuss",
                "ve",
            )
        )

    def test_orphan_sekilde_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "that had just the right pattern for the ceremony",
                "şekilde.",
            )
        )

    def test_orphan_olan_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "the captain must address the crew immediately",
                "olan",
            )
        )

    def test_orphan_oldugu_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "we need to understand what happened here",
                "olduğu",
            )
        )

    def test_orphan_hakkinda_flagged(self):
        self.assertTrue(
            ht._has_orphan_fragment(
                "we were talking about the new discovery",
                "hakkında",
            )
        )

    def test_orphan_ve_not_flagged_short_source(self):
        self.assertFalse(
            ht._has_orphan_fragment(
                "hi ve",
                "ve",
            )
        )

    def test_orphan_olan_not_flagged_valid(self):
        self.assertFalse(
            ht._has_orphan_fragment(
                "the ones that are good",
                "iyi olanlar",
            )
        )


class ReignMistranslationTest(unittest.TestCase):
    def test_reign_tahta_cikti_flagged(self):
        self.assertTrue(
            ht._has_reign_mistranslation(
                "just ten years into his reign",
                "yalnızca on yıl sonra tahta çıktı",
            )
        )

    def test_reign_no_source_match_not_flagged(self):
        self.assertFalse(
            ht._has_reign_mistranslation(
                "he ruled for many years",
                "tahta çıktı",
            )
        )

    def test_reign_correct_translation_not_flagged(self):
        self.assertFalse(
            ht._has_reign_mistranslation(
                "just ten years into his reign",
                "hükümdarlığının onuncu yılında",
            )
        )

    def test_reign_in_run_validators(self):
        class FakeCue:
            index = 1
            text = "just ten years into his reign"
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "tahta çıktı")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious if "REIGN_MISTRANSLATION" in r]
        self.assertEqual(len(reasons), 1)


class LocalCleanupYuzlerTest(unittest.TestCase):
    def test_yuzleri_fixed(self):
        text, n = ht._apply_local_fixes("bir oğlanın yüzleri")
        self.assertEqual(text, "bir oğlanın yüzü")

    def test_yuzleri_caps(self):
        text, n = ht._apply_local_fixes("Bir oğlanın Yüzleri")
        self.assertEqual(text, "bir oğlanın yüzü")

    def test_yuzleri_not_affected_normal(self):
        text, n = ht._apply_local_fixes("yüzleri güzel")
        self.assertEqual(text, "yüzleri güzel")


if __name__ == "__main__":
    unittest.main()
