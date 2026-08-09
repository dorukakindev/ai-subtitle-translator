import unittest

import hybrid_translate as ht


class SourceBoundCleanupTest(unittest.TestCase):
    def test_source_aware_final_normalizer_does_not_apply_corpus_rewrites(self):
        raw = "Rat, Collection, Client ve Macabre doğru özel adlardır."
        normalized = ht._normalize_output_text(
            raw, "Turkish", source_text="Rat, Collection, Client and Macabre are proper names.")
        self.assertEqual(normalized, raw)

    def test_source_aware_local_fix_requires_matching_source_and_respects_lock(self):
        untouched, count = ht._apply_local_fixes(
            "Bu detonatör özel addır.", source_text="This is a named device.")
        self.assertEqual((untouched, count), ("Bu detonatör özel addır.", 0))

        fixed, count = ht._apply_local_fixes(
            "Bir detonator bulundu.", source_text="A detonator was found.")
        self.assertEqual((fixed, count), ("Bir patlatıcı bulundu.", 1))

        locked, count = ht._apply_local_fixes(
            "Boy King geldi.", source_text="The Boy King arrived.",
            locked_terms={"Boy King": "Boy King"})
        self.assertEqual((locked, count), ("Boy King geldi.", 0))

    def test_source_preserved_foreign_terms_are_not_garble_or_target_leaks(self):
        self.assertEqual(
            ht.find_garble_tokens("coquiando ve bratwurst", "coquiando and bratwurst"), [])
        self.assertFalse(ht.has_non_turkish_target_leak(
            "Wichí konuşuyor.", source_text="Wichí is speaking."))
        self.assertEqual(
            ht.find_translatable_english_residue(
                "Jesus Christ appeared.", "Jesus Christ göründü.",
                {"Jesus Christ": "Jesus Christ"}), [])

    def test_real_english_residue_remains_detectable(self):
        self.assertEqual(
            ht.find_translatable_english_residue(
                "Christianity spread.", "Christianity yayıldı."), ["Christianity"])
        self.assertEqual(
            ht.find_translatable_english_residue(
                "The French colonists arrived.", "French colonists geldi."),
            ["French colonists"])


class ShortReactionAlignmentSafetyTest(unittest.TestCase):
    class Cue:
        def __init__(self, index, text):
            self.index = index
            self.text = text
            self.start = f"00:00:0{index},000"
            self.end = f"00:00:0{index},900"

    def test_oh_god_variants_sharing_translation_are_not_neighbor_echo(self):
        cues = [self.Cue(1, "Oh, God."), self.Cue(2, "Oh, my God.")]
        blocks = [
            ("1", "00:00:01,000 --> 00:00:01,900", "Aman Tanrım."),
            ("2", "00:00:02,000 --> 00:00:02,900", "Aman Tanrım."),
        ]
        reasons = ht.run_validators(blocks, cues)
        self.assertFalse(any("NEIGHBOR_ECHO" in row[3] for row in reasons))


if __name__ == "__main__":
    unittest.main()
