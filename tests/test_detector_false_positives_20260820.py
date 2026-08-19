# -*- coding: utf-8 -*-
"""2026-08-20 ikinci tur: kendi eklediğimiz tespitçilerin yanlış pozitifleri."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class MissingPredicateTest(unittest.TestCase):
    def test_ordinary_verb_final_sentences_are_not_flagged(self):
        blocks = [
            ("1", "ts", "Bugün eve gitti."),
            ("2", "ts", "Sonra kapıyı açtı."),
            ("3", "ts", "Adam bahçeye çıktı."),
            ("4", "ts", "Herkes onu bekliyordu."),
            ("5", "ts", "Çocuk okula başladı."),
            ("6", "ts", "Annesi çok sevindi."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), [])

    def test_noun_case_ending_alone_is_not_enough(self):
        blocks = [("1", "ts", "Sabah erkenden şehre."), ("2", "ts", "Yola çıktık.")]
        self.assertEqual(g._missing_predicate_ids(blocks), [])

    def test_verbal_noun_ending_is_flagged(self):
        blocks = [
            ("80", "ts", "Kalabalığı denetleyip ölüm arabasının hastaneye gitmesine."),
            ("81", "ts", "Sonraki cümle burada başlıyor."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), ["80"])

    def test_infinitive_ending_is_flagged(self):
        blocks = [
            ("10", "ts", "Tek amaçları o kapıyı açmak."),
            ("11", "ts", "Ama başaramadılar."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), ["10"])

    def test_continuation_cue_is_not_flagged(self):
        blocks = [
            ("10", "ts", "Tek amaçları o kapıyı açmak."),
            ("11", "ts", "ve içeri girmekti."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), [])


class AddressRegisterMixTest(unittest.TestCase):
    def test_false_stems_do_not_count_as_informal(self):
        blocks = [(str(i), "ts", "Bu bir reçine ve resin karışımıdır.")
                  for i in range(1, 26)]
        result = g.detect_address_register_mix(blocks)
        self.assertEqual((result["informal"], result["formal"]), (0, 0))
        self.assertFalse(result["mixed"])

    def test_other_false_stems(self):
        for word in ("kesin", "bütün", "basın", "düşün", "üstün"):
            blocks = [(str(i), "ts", "Bu %s bir şey." % word) for i in range(1, 20)]
            with self.subTest(word=word):
                self.assertEqual(g.detect_address_register_mix(blocks)["informal"], 0)

    def test_real_mix_is_still_detected(self):
        blocks = ([(str(i), "ts", "Sen ne yaptın?") for i in range(1, 21)]
                  + [(str(i), "ts", "Siz ne yaptınız?") for i in range(21, 31)])
        result = g.detect_address_register_mix(blocks)
        self.assertEqual((result["informal"], result["formal"]), (20, 10))
        self.assertTrue(result["mixed"])

    def test_uniform_formal_file_is_not_mixed(self):
        blocks = [(str(i), "ts", "Siz ne düşünüyorsunuz?") for i in range(1, 31)]
        result = g.detect_address_register_mix(blocks)
        self.assertEqual(result["informal"], 0)
        self.assertFalse(result["mixed"])


class ScanLockedTermsTest(unittest.TestCase):
    def test_locked_proper_noun_is_not_source_residue(self):
        blocks = [("1", "ts", "Ocidente'de yaşayanlar."), ("2", "ts", "Sun'ın evi.")]
        cues = [(1, "ts", "In the Ocidente."), (2, "ts", "Sun's house.")]
        source_cues = [type("C", (), {"index": i, "text": t})()
                       for i, _ts, t in cues]
        loose = g._scan_delivery_blocks(blocks, source_cues)
        tight = g._scan_delivery_blocks(
            blocks, source_cues, locked_terms={"Ocidente": "Ocidente", "Sun": "Sun"})
        self.assertGreaterEqual(loose["source_residue"], tight["source_residue"])


if __name__ == "__main__":
    unittest.main()
