# -*- coding: utf-8 -*-
"""Tamami-buyuk-harf kapisi bicim etiketiyle kandirilmasin.

`<i>FOR</i> A LONG TIME` icindeki `<i>` bir kucuk 'i' getirdigi icin cue
'tamami buyuk harf' sayilmiyordu. Bastan sona buyuk harfle yazilmis ama
italik kullanan bir kapali-altyazi kaynagi boylece esigin altinda kaliyor,
kapi tam da kapatmasi gereken yerde acik kaliyor ve caps sezgisi gercek
replikleri 'silinebilir SDH' isaretliyordu.
"""
import unittest

import hybrid_translate as ht
import subtitle_translator_gui as g

CAPS_WITH_ITALICS = [
    "<i>FOR</i> A LONG TIME. THE ANSWER WAS",
    "AN IMMORTAL SOUL. <i>OR</i> SPIRIT:",
    "SOMETHING THAT GOES BEYOND MERE MATTER",
    "BUT THE MODERN STUDY <i>OF</i> THE BRAIN",
    "<i>WHO</i> WE ARE CAN ONLY BE <i>UNDERSTOOD</i>",
    "THE STORY <i>OF</i> BECOMING <i>YOU</i>",
    "AND THIS HELPLESSNESS LASTS LONGER",
    "COMPARE HUMAN BABIES <i>TO</i> OUR COUSINS",
    "IN CONTRAST. MY <i>SON</i> ARRI IS <i>TWO</i>",
    "BUT ONE DAY HE COULD LIVE IN ALASKA",
]

MIXED_CASE = [
    "For a long time, the answer was",
    "an immortal soul, or spirit:",
    "something that goes beyond mere matter",
    "But the modern study of the brain",
    "who we are can only be understood",
    "The story of becoming you",
    "And this helplessness lasts longer",
    "Compare human babies to our cousins",
    "In contrast, my son Arri is two",
    "But one day he could live in Alaska",
]


class CapsGateMarkupTest(unittest.TestCase):
    def test_italic_tags_do_not_reopen_the_gate(self):
        self.assertFalse(g._source_caps_heuristic_allowed(CAPS_WITH_ITALICS))

    def test_mixed_case_file_still_allows_the_heuristic(self):
        self.assertTrue(g._source_caps_heuristic_allowed(MIXED_CASE))

    def test_twin_detector_agrees(self):
        caps_cues = [("1", "", t) for t in CAPS_WITH_ITALICS]
        mixed_cues = [("1", "", t) for t in MIXED_CASE]
        self.assertTrue(ht.source_is_all_caps_file(caps_cues))
        self.assertFalse(ht.source_is_all_caps_file(mixed_cues))

    def test_caps_dialogue_is_not_marked_removable(self):
        cues = [(str(i + 1), "", t) for i, t in enumerate(CAPS_WITH_ITALICS)]
        removable = g._delivery_removable_source_ids(cues)
        # Bunlarin hepsi gercek replik; hicbiri silinmemeli.
        self.assertEqual(removable, set())


if __name__ == "__main__":
    unittest.main()
