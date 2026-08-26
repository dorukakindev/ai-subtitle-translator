# -*- coding: utf-8 -*-
"""Caps kararı TEK yerde verilsin; ikizler ters karar veremesin.

"Bu dosyada caps sinyaline güvenilir mi?" sorusunun iki kopyası vardı ve
eşikleri farklıydı (GUI 0.60, hibrit 0.80) — üstelik birbirinin tümleyeni
değillerdi. Arada kalan bir kaynakta (%78,3 caps) cümle etiketleyicisinin
iki ikizi 66 cue'da ayrı sonuç üretiyordu.

Bu test kopyanın geri gelmesini engeller.
"""
import unittest

import hybrid_translate as ht
import sdh_cleaner as s
import subtitle_translator_gui as g


def _texts(caps_count, plain_count):
    rows = ["BIR SES ETIKETI GIBI" for _ in range(caps_count)]
    rows += ["Bu sıradan bir replik." for _ in range(plain_count)]
    return rows


class Cue:
    __slots__ = ("index", "start", "end", "text")

    def __init__(self, index, start, end, text):
        self.index = index
        self.start = start
        self.end = end
        self.text = text


class CapsGateSingleSourceTest(unittest.TestCase):
    def test_gui_wrapper_delegates(self):
        for caps, plain in ((0, 20), (5, 15), (16, 4), (20, 0)):
            rows = _texts(caps, plain)
            with self.subTest(caps=caps):
                self.assertEqual(g._source_caps_heuristic_allowed(rows),
                                 s.caps_heuristic_allowed(rows))

    def test_threshold_band_is_decided_once(self):
        # %78,3 caps: eski iki eşik (0.60 / 0.80) arasında kalan bant.
        rows = _texts(78, 22)
        self.assertFalse(s.caps_heuristic_allowed(rows))
        self.assertFalse(g._source_caps_heuristic_allowed(rows))

    def test_twin_taggers_agree_in_the_band(self):
        rows = _texts(78, 22)
        blocks = []
        cues = []
        for i, text in enumerate(rows, start=1):
            ts_a = "00:00:%02d,000" % (i * 2 % 60)
            ts_b = "00:00:%02d,500" % (i * 2 % 60)
            blocks.append((i, "%s --> %s" % (ts_a, ts_b), text))
            cues.append(Cue(i, ts_a, ts_b, text))
        self.assertEqual(ht._tag_fragments(cues), g._tag_fragments_gui(blocks))

    def test_markup_does_not_reopen_the_gate(self):
        rows = ["<i>BIR</i> SES ETIKETI GIBI" for _ in range(20)]
        self.assertFalse(s.caps_heuristic_allowed(rows))

    def test_too_few_rows_is_not_trusted(self):
        self.assertFalse(s.caps_heuristic_allowed(["Kısa.", "İki satır."]))


if __name__ == "__main__":
    unittest.main()
