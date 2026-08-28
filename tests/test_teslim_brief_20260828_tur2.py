# -*- coding: utf-8 -*-
"""11 filmlik ikinci teslimin kod bulguları.

Kaynak: `plans/teslim-20260828-kod-bulgulari-brief.md` (commit `6c60bb2`).
Ölçümler programın ürettiği hal (`*.pre-opus-20260828.srt`) üzerinden.
"""
import unittest

import subtitle_translator_gui as gui
from subtitle_formats import (restore_format_tags, _match_prefixed_wrap,
                              _match_full_wrap)


class PrefixedItalicRestoreTest(unittest.TestCase):
    """Madde 1: satır İÇİNDE açılan `<i>` geri konamıyordu — 1.251 cue.

    The Tales of Hoffmann bir opera filmi; kaynak iki kalıp kullanıyor.
    `<i>♪ metin ♪</i>` korunuyordu (etiket satır başında), `♪ <i>metin</i> ♪`
    tamamen düşüyordu. `_match_full_wrap` etiketin BÜTÜN satırı sarmasını
    istiyor; önünde nota/tire/konuşmacı etiketi olunca eşleşmiyor.

    Arşiv ölçümü: düzeltme 1.270 cue kurtarıyor (Hoffmann 1.251,
    The Contestant 13, Night of the Eagle 6).
    """

    def test_note_outside_the_tag_is_restored(self):
        self.assertEqual(
            restore_format_tags("♪ <i>Some drink, drink</i> ♪",
                                "♪ İçin, için ♪"),
            "♪ <i>İçin, için</i> ♪")

    def test_dialogue_dash_before_the_tag(self):
        self.assertEqual(
            restore_format_tags("- <i>Number, please.</i>",
                                "- Numara, lütfen."),
            "- <i>Numara, lütfen.</i>")

    def test_sdh_speaker_label_before_the_tag(self):
        """Madde 2: SDH etiketi silinirken ardındaki italik de yutuluyordu."""
        self.assertEqual(
            restore_format_tags("- [Margaret] <i>Are you there?</i>",
                                "- Orada mısın?"),
            "- <i>Orada mısın?</i>")

    def test_multi_line_note_pattern(self):
        self.assertEqual(
            restore_format_tags("♪ <i>First line</i> ♪\n♪ <i>Second</i> ♪",
                                "♪ Birinci ♪\n♪ İkinci ♪"),
            "♪ <i>Birinci</i> ♪\n♪ <i>İkinci</i> ♪")

    def test_the_already_working_pattern_still_works(self):
        self.assertEqual(
            restore_format_tags("<i>♪ We want some beer ♪</i>",
                                "♪ Biraz bira istiyoruz ♪"),
            "<i>♪ Biraz bira istiyoruz ♪</i>")

    def test_nothing_is_invented(self):
        """Kaynak italik değilse çeviri de italik olmaz."""
        for source, translated in (
                ("♪ Plain lyric ♪", "♪ Düz söz ♪"),
                ("Normal line.", "Normal satır."),
                ("He said <i>no</i> loudly.", "Yüksek sesle <i>hayır</i> dedi."),
                ("<i>All italic</i>", "<i>Hepsi italik</i>")):
            with self.subTest(source=source):
                self.assertEqual(
                    restore_format_tags(source, translated), translated)

    def test_prefixed_wrap_matcher_rejects_a_plain_full_wrap(self):
        """Öneksiz tam sarmalama eski yolun işi, bu yolun değil."""
        self.assertIsNone(_match_prefixed_wrap("<i>tamamen sarılı</i>"))
        self.assertIsNotNone(_match_full_wrap("<i>tamamen sarılı</i>"))


class LostItalicIsReportedTest(unittest.TestCase):
    """Madde 1'in ikinci yarısı: kayıp italik rapora da düşsün."""

    def test_prefixed_wrap_loss_is_a_finding(self):
        self.assertEqual(
            gui._format_coverage_lost_ids(
                [("1", "x", "♪ İçin, için ♪")],
                {"1": "♪ <i>Some drink</i> ♪"}),
            ["1"])

    def test_font_and_position_stay_excluded(self):
        """Teslim bunları BİLEREK atıyor; kayıp sayılmaz."""
        self.assertEqual(
            gui._format_coverage_lost_ids(
                [("1", "x", "renksiz")],
                {"1": '<font color="#ffff00">coloured</font>'}),
            [])


class UnbalancedNoteTest(unittest.TestCase):
    """Madde 3: çok satırlı cue'da kapanış ♪ düşüyor (Hoffmann #78)."""

    def test_odd_note_count_against_an_even_source(self):
        self.assertEqual(
            gui._unbalanced_note_ids(
                [("1", "x", "♪ Kleinzach'lı şarkıyı söylemeliyiz")],
                {"1": "♪ We'll have to have the one about Kleinzach ♪"}),
            ["1"])

    def test_balanced_delivery_is_quiet(self):
        self.assertEqual(
            gui._unbalanced_note_ids(
                [("1", "x", "♪ Şarkı ♪")], {"1": "♪ Song ♪"}),
            [])

    def test_odd_source_is_not_the_delivery_fault(self):
        """Kaynağın kendisi tek işaretliyse çeviri de öyle olur."""
        self.assertEqual(
            gui._unbalanced_note_ids(
                [("1", "x", "♪ Şarkı")], {"1": "♪ Song"}),
            [])

    def test_no_source_no_finding(self):
        self.assertEqual(
            gui._unbalanced_note_ids([("1", "x", "♪ Şarkı")], {}), [])


class InconsistentRepeatTest(unittest.TestCase):
    """Madde 5: birebir aynı kaynak dize farklı Türkçelerle çevrilmiş.

    Eşik 30 karakter, ölçümle: 12'de 85 grup, 30'da 57 ve örneklenen hepsi
    gerçek. Kısa dizeler (`Evet.`) doğal olarak tekrar eder.
    """

    SRC = "when industrial fishing came along, everything changed"

    def test_two_different_translations_are_flagged(self):
        blocks = [("399", "x", "Endüstriyel balıkçılık çıkınca,"),
                  ("619", "x", "Endüstriyel balıkçılık ortaya çıkınca,")]
        self.assertEqual(
            gui._inconsistent_repeat_ids(
                blocks, {"399": self.SRC, "619": self.SRC}),
            ["399", "619"])

    def test_identical_translations_are_quiet(self):
        blocks = [("1", "x", "Aynı çeviri."), ("2", "x", "Aynı çeviri.")]
        self.assertEqual(
            gui._inconsistent_repeat_ids(
                blocks, {"1": self.SRC, "2": self.SRC}),
            [])

    def test_short_lines_are_exempt(self):
        blocks = [("1", "x", "Evet."), ("2", "x", "Tabii.")]
        self.assertEqual(
            gui._inconsistent_repeat_ids(
                blocks, {"1": "Yes.", "2": "Yes."}),
            [])

    def test_finding_classes_are_registered(self):
        for key in ("unbalanced_note_ids", "inconsistent_repeat_ids"):
            with self.subTest(key=key):
                self.assertIn(key, gui._FINDING_CLASSES)


if __name__ == "__main__":
    unittest.main()
