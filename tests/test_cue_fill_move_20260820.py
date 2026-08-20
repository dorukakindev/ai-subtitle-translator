# -*- coding: utf-8 -*-
"""P2-E: cue-fill metnini komşu cue'ya taşıma (zaman damgası değişmez)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


def _flat(blocks):
    return " ".join(
        " ".join(str(text or "").replace("\n", " ").split())
        for _idx, _ts, text in blocks).strip()


class CueFillMoveTest(unittest.TestCase):
    PAIR = [
        ("368", "00:30:00,000 --> 00:30:07,000",
         "Cümlenin ilk yarısı"),
        ("369", "00:30:07,000 --> 00:30:07,400",
         "yani bu ikinci parça çok kısa bir cue içine sıkıştırılmış "
         "durumda ve okunamaz."),
    ]
    SRC = {"368": "A fairly long English narration sentence with room here",
           "369": "elements."}

    def test_text_is_moved_to_the_previous_cue(self):
        moved, count = g.rebalance_cue_fill_pairs(self.PAIR, self.SRC)
        self.assertEqual(count, 1)
        self.assertNotEqual(moved[0][2], self.PAIR[0][2])

    def test_joined_text_is_unchanged(self):
        moved, _ = g.rebalance_cue_fill_pairs(self.PAIR, self.SRC)
        self.assertEqual(_flat(moved), _flat(self.PAIR))

    def test_timestamps_are_untouched(self):
        moved, _ = g.rebalance_cue_fill_pairs(self.PAIR, self.SRC)
        self.assertEqual([row[1] for row in moved],
                         [row[1] for row in self.PAIR])

    def test_receiving_cue_stays_within_limits(self):
        moved, _ = g.rebalance_cue_fill_pairs(self.PAIR, self.SRC)
        first = moved[0][2]
        self.assertLessEqual(
            g._cue_reading_speed(first.replace("\n", " "), moved[0][1]),
            g.CPS_WARN_LIMIT)
        for line in first.split("\n"):
            self.assertLessEqual(g._visible_len(line), g._LINE_THRESHOLD)

    def test_reading_speed_actually_improves(self):
        moved, _ = g.rebalance_cue_fill_pairs(self.PAIR, self.SRC)
        before = g._cue_reading_speed(self.PAIR[1][2], self.PAIR[1][1])
        after = g._cue_reading_speed(
            moved[1][2].replace("\n", " "), moved[1][1])
        self.assertLess(after, before)

    def test_dialogue_pairs_are_never_touched(self):
        pair = [
            ("1", "00:30:00,000 --> 00:30:07,000", "- Ne yaptın orada"),
            ("2", "00:30:07,000 --> 00:30:07,400",
             "- Hiçbir şey yapmadım ben orada bugün hiç kimseyle konuşmadım."),
        ]
        moved, count = g.rebalance_cue_fill_pairs(pair, {"1": "a", "2": "b"})
        self.assertEqual(count, 0)
        self.assertEqual(moved, pair)

    def test_tagged_cues_are_never_touched(self):
        pair = [
            ("1", "00:30:00,000 --> 00:30:07,000", "<i>Bir şeyler anlatıyor</i>"),
            ("2", "00:30:07,000 --> 00:30:07,400",
             "ve bu cue bir hayli uzun bir metin taşıyor gerçekten de böyle."),
        ]
        _moved, count = g.rebalance_cue_fill_pairs(pair, {"1": "a", "2": "b"})
        self.assertEqual(count, 0)

    def test_previous_cue_that_ends_a_sentence_is_not_a_continuation(self):
        pair = [
            ("1", "00:30:00,000 --> 00:30:07,000", "Cümle burada bitti."),
            ("2", "00:30:07,000 --> 00:30:07,400",
             "bu ayrı bir cümle ve oldukça uzun bir metin taşıyor işte böyle."),
        ]
        _moved, count = g.rebalance_cue_fill_pairs(pair, {"1": "a", "2": "b"})
        self.assertEqual(count, 0)

    def test_balanced_pairs_are_left_alone(self):
        pair = [
            ("1", "00:30:00,000 --> 00:30:03,000", "Kısa bir cümle"),
            ("2", "00:30:03,000 --> 00:30:06,000", "ve devamı burada."),
        ]
        moved, count = g.rebalance_cue_fill_pairs(pair, {"1": "a", "2": "b"})
        self.assertEqual(count, 0)
        self.assertEqual(moved, pair)


class CueFillMoveSettingTest(unittest.TestCase):
    def test_default_is_on(self):
        self.assertTrue(g.QUALITY_PROFILE_DEFAULTS["cue_fill_move"])

    def test_it_is_a_boundary_quality_var(self):
        self.assertIn("cue_fill_move", g._BOUNDARY_QUALITY_VARS)

    def test_migration_enables_it(self):
        settings = {"quality_profile_version": 10}
        g._apply_quality_profile_defaults(settings)
        self.assertTrue(settings["cue_fill_move"])


if __name__ == "__main__":
    unittest.main()
