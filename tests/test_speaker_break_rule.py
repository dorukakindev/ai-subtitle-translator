# -*- coding: utf-8 -*-
"""Cümle grubunu kesen konuşmacı değişimi.

Eski desen (`[^\\W\\d_][^:\\n]{0,39}:\\s+`) cümle-İÇİ iki noktayı da
konuşmacı etiketi sanıyordu ve çok cue'lu cümleyi ortasından kesiyordu.
Kesilen grup hiç etiketlenmediği için model o cümleyi satır satır çeviriyor.

Ölçüm (84.590 gerçek kaynak cue): iki desen 2.791 gerçek kesmede aynı
kararı veriyor; yeni desen fazladan hiçbir yeri kesmiyor. Etiketleme
kazancı 120 dosyada +121 cue / +32 cümle grubu.
"""
import unittest

import hybrid_translate as ht
import subtitle_translator_gui as gui


class SpeakerBreakRuleTest(unittest.TestCase):
    RE = gui._SPEAKER_BREAK_RE

    def test_real_speaker_labels_still_break(self):
        for text in ("MAN: Hush.",
                     "HARRY CHRISTOPHERS: We know he loved it.",
                     "Stuart: Yes.",
                     "Mary-Ann: Tamam.",
                     "NARRATOR: Once upon a time."):
            with self.subTest(text=text):
                self.assertTrue(self.RE.match(text))

    def test_dialogue_dash_still_breaks(self):
        for text in ("- Nasılsın?", "– Fine.", "— Öyle mi?"):
            with self.subTest(text=text):
                self.assertTrue(self.RE.match(text))

    def test_mid_sentence_colon_does_not_break(self):
        """Ölçülen gerçek yanlış kesmeler."""
        for text in ("But he was wrong: it's not a tower,",
                     "And it had a name: Shambala.",
                     "four of the great rivers of Asia rise:",
                     "an Ancient Greek ''Mission: Impossible''.",
                     "I think that finally became one story: Jason.",
                     "The name of the land: we call it punt,",
                     "This is it: ''O Descobrimento Do Tibet''"):
            with self.subTest(text=text):
                self.assertIsNone(self.RE.match(text))

    def test_plain_sentences_do_not_break(self):
        for text in ("Bu normal bir cümle.", "Devam eden bir satır,",
                     "the central figure"):
            with self.subTest(text=text):
                self.assertIsNone(self.RE.match(text))

    def test_the_two_flows_share_one_pattern(self):
        """İkiz: GUI ve hybrid aynı deseni kullanmalı."""
        self.assertEqual(gui._SPEAKER_BREAK_RE.pattern,
                         ht._SPEAKER_BREAK_RE.pattern)


class SentenceGroupingTest(unittest.TestCase):
    """Yanlış kesme, çok cue'lu cümlenin gruplanmasını engelliyordu."""

    def test_sentence_continuing_past_a_colon_is_grouped(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:03,000",
             "In this tiny area of western Tibet"),
            ("2", "00:00:03,100 --> 00:00:05,000",
             "four of the great rivers of Asia rise:"),
            ("3", "00:00:05,100 --> 00:00:07,000",
             "the Indus and the Brahmaputra."),
        ]
        tags = gui._tag_fragments_gui(blocks)
        self.assertEqual(tags["1"], "start")
        self.assertEqual(tags["2"], "mid")
        self.assertEqual(tags["3"], "end")

    def test_a_real_speaker_change_still_ends_the_group(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:03,000", "He said something"),
            ("2", "00:00:03,100 --> 00:00:05,000", "MAN: Hush now."),
        ]
        tags = gui._tag_fragments_gui(blocks)
        self.assertEqual(tags["1"], "none")
        self.assertEqual(tags["2"], "none")


if __name__ == "__main__":
    unittest.main()
