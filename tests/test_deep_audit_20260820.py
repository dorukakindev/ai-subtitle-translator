# -*- coding: utf-8 -*-
"""DERIN_BUG_DENETIMI_2026-08-20.md bulgularının regresyon testleri.

Her sınıf denetim maddesinin KARŞI ÖRNEĞİNİ kilitler; madde numarası
docstring'de verilir.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import sdh_cleaner
import subtitle_translator_gui as g


class _Cue:
    def __init__(self, index, timestamp, text):
        self.index, self.timestamp, self.text = index, timestamp, text
        self.start, self.end = [part.strip() for part in timestamp.split("-->")]


def _delivered(blocks, cues, target="Turkish"):
    rows = g._prepare_upload_ready_blocks(blocks, target, None, source_cues=cues)
    return [(idx, text) for idx, _ts, text in rows
            if "discord" not in str(text)]


class CueFillNeedsSourceContinuationTest(unittest.TestCase):
    """Madde 1: taşıma yalnız aynı kaynak cümlesinin devamında yapılmalı."""

    def test_independent_source_sentences_are_not_merged(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Eve gittim"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "Yangın çıktı hemen kaçmalıyız buradan derhal şimdi")]
        moved, count = g.rebalance_cue_fill_pairs(
            pair, {"1": "I left.", "2": "Fire!"})
        self.assertEqual(count, 0)
        self.assertEqual(moved, pair)

    def test_source_continuation_still_moves(self):
        pair = [("368", "00:30:00,000 --> 00:30:07,000", "Cümlenin ilk yarısı"),
                ("369", "00:30:07,000 --> 00:30:07,400",
                 "yani bu ikinci parça çok kısa bir cue içine "
                 "sıkıştırılmış durumda ve okunamaz.")]
        source = {"368": "A fairly long English narration sentence with room",
                  "369": "elements."}
        _moved, count = g.rebalance_cue_fill_pairs(pair, source)
        self.assertEqual(count, 1)

    def test_capitalised_continuation_is_a_new_sentence(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Bir şeyler anlatıyor"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "sonra bambaşka bir konuya geçti ve uzun uzun konuştu.")]
        _moved, count = g.rebalance_cue_fill_pairs(
            pair, {"1": "He was talking", "2": "Then everything changed"})
        self.assertEqual(count, 0)

    def test_missing_source_blocks_the_move(self):
        pair = [("1", "00:00:01,000 --> 00:00:08,000", "Bir şeyler anlatıyor"),
                ("2", "00:00:08,000 --> 00:00:08,400",
                 "sonra bambaşka bir konuya geçti ve uzun uzun konuştu.")]
        _moved, count = g.rebalance_cue_fill_pairs(pair, {})
        self.assertEqual(count, 0)


class CondenseSpeakerAndContentTest(unittest.TestCase):
    """Madde 2 ve 30: condense konuşmacı ve içerik kaybetmemeli."""

    def test_two_speakers_are_never_merged(self):
        ok, reason = ht.validate_condense_candidate(
            "- Merhaba\n- Nasılsın?", "- Merhaba, nasılsın?",
            "- Hello\n- How are you?", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "speaker_merge")

    def test_two_speakers_kept_is_accepted(self):
        ok, _reason = ht.validate_condense_candidate(
            "- Merhaba dostum nasılsın\n- İyiyim teşekkür ederim",
            "- Merhaba nasılsın\n- İyiyim sağ ol",
            "- Hello friend how are you\n- I am fine thanks",
            tgt_lang="Turkish")
        self.assertTrue(ok)

    def test_dropping_the_object_is_content_loss(self):
        ok, reason = ht.validate_condense_candidate(
            "Maria kırmızı tren biletini kaçırdı.", "Maria kaçırdı.",
            "Maria missed the red train ticket.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertEqual(reason, "content_loss")

    def test_sourceless_shortening_keeps_its_freedom(self):
        ok, _reason = ht.validate_condense_candidate(
            "Bu çok uzun bir cümle, birçok gereksiz kelimeyle dolu.",
            "Uzun bir cümle burada.")
        self.assertTrue(ok)


class SharedTimestampDeletionTest(unittest.TestCase):
    """Madde 5: aynı zamanı paylaşan kredi gerçek diyaloğu silmemeli."""

    TS = "00:00:01,000 --> 00:00:02,000"

    def test_dialogue_survives_a_credit_at_the_same_timestamp(self):
        cues = [_Cue(1, self.TS, "Subtitles by Example"),
                _Cue(2, self.TS, "Hello.")]
        blocks = [("1", self.TS, "Altyazı: Example"), ("2", self.TS, "Merhaba.")]
        self.assertEqual(_delivered(blocks, cues), [("2", "Merhaba.")])

    def test_a_lone_credit_is_still_removed(self):
        cues = [_Cue(1, self.TS, "Subtitles by Example")]
        blocks = [("1", self.TS, "Altyazı: Example")]
        self.assertEqual(_delivered(blocks, cues), [])


class NarrativeScreenCardTest(unittest.TestCase):
    """Madde 6: büyük harfli ekran kartları SDH değildir."""

    def test_place_date_and_film_cards_are_kept(self):
        for card in ("BERLIN 1961", "PARIS, 1943", "THE END", "ACT I",
                     "ACT III", "PART TWO", "CHAPTER ONE", "1975",
                     "TO BE CONTINUED"):
            with self.subTest(card=card):
                self.assertFalse(sdh_cleaner.is_structural_sdh_label(card))

    def test_sound_labels_are_still_structural_sdh(self):
        for label in ("APPLAUSE", "LAUGHTER", "MUSIC PLAYING", "GUNSHOT",
                      "DOOR SLAMS", "АПЛОДИСМЕНТЫ", "ВОЙ СИРЕНЫ"):
            with self.subTest(label=label):
                self.assertTrue(sdh_cleaner.is_structural_sdh_label(label))


class OwnerMismatchIsHardErrorTest(unittest.TestCase):
    """Madde 8: cue sahiplik kayması teslimi durdurmalı."""

    def test_owner_mismatch_blocks_the_ready_marker(self):
        self.assertTrue(g._delivery_audit_has_hard_error(
            {"status": "review", "delivery_owner_mismatch_ids": ["1"]}))

    def test_clean_audit_is_still_accepted(self):
        self.assertFalse(g._delivery_audit_has_hard_error(
            {"status": "ok", "delivery_owner_mismatch_ids": []}))


class SdhLookingTargetOverRealDialogueTest(unittest.TestCase):
    """Madde 14: kaynak diyalogsa SDH-benzeri hedef silinmemeli."""

    TS = "00:00:01,000 --> 00:00:03,000"

    def test_broken_translation_is_marked_not_deleted(self):
        delivered = _delivered([("1", self.TS, "[MÜZİK]")],
                               [_Cue(1, self.TS, "Hello.")])
        self.assertEqual(delivered, [("1", "[ÇEVİRİ EKSİK]")])

    def test_real_sdh_source_is_still_dropped(self):
        delivered = _delivered([("1", self.TS, "[MÜZİK]")],
                               [_Cue(1, self.TS, "[MUSIC PLAYING]")])
        self.assertEqual(delivered, [])


class DeliverySignatureBoundsTest(unittest.TestCase):
    """Madde 44 ve 45: imza aralıkları geçerli ve çakışmasız olmalı."""

    def _signatures(self, rows):
        cues = [_Cue(idx, ts, "Line %s." % idx) for idx, ts, _t in rows]
        out = g._prepare_upload_ready_blocks(rows, "Turkish", None,
                                             source_cues=cues)
        return [g._srt_timestamp_bounds(ts) for _idx, ts, text in out
                if "discord" in str(text)]

    def test_no_signature_has_zero_or_reversed_duration(self):
        for start in ("00:00:00,000", "00:00:00,001", "00:00:00,002",
                      "00:00:05,000"):
            rows = [("1", f"{start} --> 00:00:08,000", "Merhaba dünya.")]
            with self.subTest(start=start):
                for begin, end in self._signatures(rows):
                    self.assertLess(begin, end)

    def test_signatures_do_not_overlap_each_other(self):
        rows = [("1", "00:00:10,000 --> 00:00:12,000", "Üçüncü cümle."),
                ("2", "00:00:01,000 --> 00:00:03,000", "Birinci cümle."),
                ("3", "00:00:05,000 --> 00:00:07,000", "İkinci cümle.")]
        spans = self._signatures(rows)
        self.assertEqual(len(spans), 3)
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                with self.subTest(pair=(i, j)):
                    self.assertFalse(
                        spans[i][1] > spans[j][0] and spans[j][1] > spans[i][0])


if __name__ == "__main__":
    unittest.main()
