# -*- coding: utf-8 -*-
"""SDH etiketi gerçek konuşmayla aynı cümle grubuna girmesin.

`[Prayer]` nokta ile kapanmadığı için cümle AÇIYOR ve peşindeki gerçek
konuşmayı aynı `frag_group`'a çekiyordu. Model o grubu tek cümle sanıp
anlamı ID'ler arasında dağıtabiliyor; sonra SDH temizliği etiketi silince
oraya taşınmış içerik de gidiyor.

Gerçek arşivde ölçüldü: karma grup 2032 -> 76, etkilenen dosya 160 -> 31.
"""
import unittest

import hybrid_translate as ht
import sdh_cleaner as s
import subtitle_translator_gui as g


class Cue:
    __slots__ = ("index", "start", "end", "text")

    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


def _ts(sec):
    return "00:00:%02d,000" % sec


ROWS = [
    ("[Prayer]", 10, 12),
    ("For centuries, the supplies of food", 12, 14),
    ("and the people who grew them", 14, 16),
    ("...in the event of war.", 16, 18),
]


def _cues():
    return [Cue(i + 1, _ts(a), _ts(b), t)
            for i, (t, a, b) in enumerate(ROWS)]


def _blocks():
    return [(i + 1, "%s --> %s" % (_ts(a), _ts(b)), t)
            for i, (t, a, b) in enumerate(ROWS)]


class StructuralSdhPredicateTest(unittest.TestCase):
    def test_labels_are_structural(self):
        for text in ("[Prayer]", "[Baby crying]", "(door slams)", "♪♪",
                     "[Announcement]"):
            with self.subTest(text=text):
                self.assertTrue(s.is_structural_sdh_cue(text))

    def test_real_speech_is_not_structural(self):
        for text in ("For centuries, the supplies of food",
                     "No delays expected.",
                     "...in the event of war."):
            with self.subTest(text=text):
                self.assertFalse(s.is_structural_sdh_cue(text))

    def test_caps_file_does_not_turn_speech_into_a_label(self):
        # Baştan sona büyük harfli kaynakta caps sinyali ayırt etmez.
        self.assertFalse(s.is_structural_sdh_cue(
            "AND THAT'S HOW IT GOES WITH THE ADULT BRAIN",
            allow_caps_heuristic=False))


class StructuralSdhBreaksSentenceGroupTest(unittest.TestCase):
    def test_label_does_not_open_a_sentence_group(self):
        tags = ht._tag_fragments(_cues())
        self.assertEqual(tags[1], "none")          # [Prayer]
        self.assertEqual(tags[2], "start")         # gerçek cümle burada başlar
        self.assertEqual(tags[4], "end")

    def test_label_is_not_a_group_member(self):
        cues = _cues()
        gid_by_idx, groups = ht._fragment_groups(cues)
        self.assertIsNone(gid_by_idx.get(1))
        for group in groups:
            self.assertNotIn(1, group.get("items", []))

    def test_gui_twin_produces_the_same_tags(self):
        ht_tags = ht._tag_fragments(_cues())
        gui_tags = g._tag_fragments_gui(_blocks())
        self.assertEqual(ht_tags, gui_tags)


if __name__ == "__main__":
    unittest.main()
