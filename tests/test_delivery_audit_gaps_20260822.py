# -*- coding: utf-8 -*-
"""Teslim denetimindeki iki boşluk — GERÇEK teslim dosyalarında ölçüldü.

1. Cue SIRASI hiç denetlenmiyordu: 255 teslimin 34'ünde kendinden öncekinden
   erken başlayan cue vardı ve kullanıcı bunu hiç öğrenmiyordu.
2. 'МУЗЫКА: "Theme 21"' biçimindeki SDH künyesi (TAMAMI BÜYÜK etiket + karışık
   harfli eser adı) kaldırılabilir kaynak sayılmıyordu; SDH temizliğinin doğru
   düşürdüğü cue 'kayıp diyalog' = SERT HATA oluyor ve iyi teslimi karantinaya
   alıyordu. Ölçüm: 11 dosya → 8, iki bölümde 24 sahte kayıp → 2.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sdh_cleaner as sc
import subtitle_translator_gui as g

NL = chr(10)


def _srt(rows) -> str:
    out = []
    for idx, start, end, text in rows:
        out.append("%s%s%s --> %s%s%s%s" % (idx, NL, start, end, NL, text, NL))
    return NL.join(out)


class TitledSdhLabelTest(unittest.TestCase):
    """ALL-CAPS etiket + eser adı biçimi tanınmalı."""

    LABELS = (
        '<font color="#ffffff">МУЗЫКА: "Theme 21"</font>'
        + NL + '<font color="#ffffff">Tangerine Dream</font>',
        'МУЗЫКА: "Rite of Spring"' + NL + 'Игорь Стравинский (часть 1)',
        'MUSIC: "Oxygene" (Side 2 Part 4)',
        'MUSIC: "Syrinx" For Solo Flute',
        'MÜZİK: "Kara Sevda"',
        'MUSIC: Tangerine Dream',
    )
    DIALOGUE = (
        "JOHN: Get out",
        "JOHN: I am here.",
        "MÜZİK: Ne yapıyorsun",
        "JOHN: Get out (angrily)",
        "Bugün: harika bir gün",
        "RYAN:",
    )

    def test_music_credits_are_labels(self):
        for text in self.LABELS:
            with self.subTest(text=text[:40]):
                self.assertTrue(sc.is_titled_sdh_label(text))

    def test_real_dialogue_after_a_speaker_label_is_kept(self):
        for text in self.DIALOGUE:
            with self.subTest(text=text[:40]):
                self.assertFalse(sc.is_titled_sdh_label(text))

    def test_the_audit_treats_them_as_expected_removals(self):
        self.assertTrue(g._source_cue_is_delivery_removable(
            'МУЗЫКА: "Theme 21"' + NL + 'Tangerine Dream'))
        self.assertFalse(g._source_cue_is_delivery_removable("JOHN: Get out"))


class DeliveryCueOrderTest(unittest.TestCase):
    """Cue sırası: kaynaktan MİRAS olan bilgi, teslimde ORTAYA ÇIKAN sert hata."""

    SOURCE_ORDERED = [
        ("1", "00:00:01,000", "00:00:02,000", "First line."),
        ("2", "00:00:03,000", "00:00:04,000", "Second line."),
        ("3", "00:00:05,000", "00:00:06,000", "Third line."),
    ]
    SOURCE_DISORDERED = [
        ("1", "00:00:05,000", "00:00:06,000", "First line."),
        ("2", "00:00:01,000", "00:00:02,000", "Second line."),
        ("3", "00:00:07,000", "00:00:08,000", "Third line."),
    ]

    def _audit(self, source_rows, output_rows):
        folder = Path(tempfile.mkdtemp())
        source = folder / "src.srt"
        output = folder / "out.srt"
        source.write_text(_srt(source_rows), encoding="utf-8")
        output.write_text(_srt(output_rows), encoding="utf-8")
        return g._subtitle_delivery_audit(
            str(source), str(output), "Turkish", "English")

    def test_ordered_delivery_has_no_finding(self):
        audit = self._audit(self.SOURCE_ORDERED, [
            ("1", "00:00:01,000", "00:00:02,000", "Birinci."),
            ("2", "00:00:03,000", "00:00:04,000", "İkinci."),
            ("3", "00:00:05,000", "00:00:06,000", "Üçüncü."),
        ])
        self.assertEqual(audit.get("introduced_out_of_order_ids"), [])
        self.assertEqual(audit.get("inherited_out_of_order_ids"), [])

    def test_disorder_inherited_from_the_source_is_information_only(self):
        audit = self._audit(self.SOURCE_DISORDERED, [
            ("1", "00:00:05,000", "00:00:06,000", "Birinci."),
            ("2", "00:00:01,000", "00:00:02,000", "İkinci."),
            ("3", "00:00:07,000", "00:00:08,000", "Üçüncü."),
        ])
        self.assertTrue(audit.get("inherited_out_of_order_ids"))
        self.assertEqual(audit.get("introduced_out_of_order_ids"), [])

    def test_disorder_we_created_is_a_hard_error(self):
        audit = self._audit(self.SOURCE_ORDERED, [
            ("1", "00:00:05,000", "00:00:06,000", "Birinci."),
            ("2", "00:00:03,000", "00:00:04,000", "İkinci."),
            ("3", "00:00:01,000", "00:00:02,000", "Üçüncü."),
        ])
        self.assertTrue(audit.get("introduced_out_of_order_ids"))
        self.assertTrue(g._delivery_audit_has_hard_error(audit))

    def test_inherited_disorder_is_reported_to_the_user(self):
        audit = self._audit(self.SOURCE_DISORDERED, [
            ("1", "00:00:05,000", "00:00:06,000", "Birinci."),
            ("2", "00:00:01,000", "00:00:02,000", "İkinci."),
            ("3", "00:00:07,000", "00:00:08,000", "Üçüncü."),
        ])
        lines = g._delivery_audit_log_details(audit)
        self.assertTrue(
            any("cue_sirasi_kaynaktan" in line for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
