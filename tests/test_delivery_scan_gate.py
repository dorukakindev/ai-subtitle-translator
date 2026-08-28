# -*- coding: utf-8 -*-
"""Teslim taramasının 'kesin' bulguları da teslimi durdurur.

Kapı yalnız DENETİM sözlüğüne bakıyordu. Taramanın tek kapı sinyali
`delivery_scan_failed`'di ve o "tarama ÇÖKTÜ" demek, "tarama bir şey BULDU"
değil — yani tarama ne bulursa bulsun dosya teslim edilebiliyordu.

Arşivde ölçüldü (616 teslim): metne cue numarası sızmış 7 cue, biri
(`Dont.Die.Without.Telling.Me.Where` #90) satırın TAMAMINI kaybetmiş,
yerinde yalnız `91` yazıyor. Kapı bunların hiçbirini görmüyordu.
"""
import unittest

import subtitle_translator_gui as gui


class ScanHardErrorTest(unittest.TestCase):
    def test_certain_classes_stop_delivery(self):
        for key in ("cue_id_leak_ids", "broken_italic_ids",
                    "repetition_collapse_ids"):
            with self.subTest(key=key):
                self.assertEqual(gui._FINDING_CLASSES[key][0], "kesin")
                self.assertTrue(
                    gui._delivery_scan_has_hard_error({key: ["7"]}))

    def test_probable_classes_do_not_stop_delivery(self):
        """'muhtemel' sınıflar rapor eder, teslimi durdurmaz."""
        for key in ("source_residue_ids", "missing_predicate_ids",
                    "english_filler_ids"):
            with self.subTest(key=key):
                self.assertEqual(gui._FINDING_CLASSES[key][0], "muhtemel")
                self.assertFalse(
                    gui._delivery_scan_has_hard_error({key: ["7"]}))

    def test_empty_and_malformed_scans_are_safe(self):
        for scan in ({}, None, [], {"cue_id_leak_ids": []},
                     {"cue_id_leak_ids": 3}, {"bilinmeyen_ids": ["1"]}):
            with self.subTest(scan=scan):
                self.assertFalse(gui._delivery_scan_has_hard_error(scan))

    def test_class_list_is_derived_not_duplicated(self):
        """Sınıf listesi ayrı tutulmaz; güven etiketinden türetilir."""
        import inspect
        source = inspect.getsource(gui._delivery_scan_has_hard_error)
        self.assertIn("_FINDING_CLASSES.get(key)", source)
        self.assertIn('meta[0] != "kesin"', source)

    def test_gate_call_site_consults_the_scan(self):
        import inspect
        source = inspect.getsource(gui.App._save_quality_report)
        self.assertIn("_delivery_scan_has_hard_error(row.get(\"delivery_scan\"))",
                      source)


class RepetitionNeedsASourceTest(unittest.TestCase):
    """Kuralın bütün isabeti kaynak elemesinden geliyor.

    Kaynağı bulunamayan dosyalarda ölçüldü: 13 bulgunun 11'i yanlıştı
    (`Bükül! Bükül!`, `Oo, oo, oo`, `Bill, Bill, Bill` — retorik tekrar ve
    şarkı sözü). Eleme çalışamıyorsa bulgu da verilmez.
    """

    LOOP = "Yani, işte işte işte işte işte işte işte işte"
    SOURCE = "I mean, I know it's gonna be uncomfortable at work,"

    def test_flagged_when_the_source_is_available(self):
        self.assertEqual(
            gui._repetition_collapse_ids([("1", "x", self.LOOP)],
                                         {"1": self.SOURCE}),
            ["1"])

    def test_silent_without_a_source(self):
        self.assertEqual(
            gui._repetition_collapse_ids([("1", "x", self.LOOP)], {}), [])
        self.assertEqual(
            gui._repetition_collapse_ids([("1", "x", self.LOOP)], None), [])
        self.assertEqual(
            gui._repetition_collapse_ids([("1", "x", self.LOOP)], {"1": ""}),
            [])

    def test_rhetorical_repetition_stays_silent_either_way(self):
        for text in ("Bükül! Bükül! Bükül! Bükül! Bükül!",
                     "Bill. Bill, Bill, Bill, Bill.",
                     "<i>Oo, oo, oo, oo</i> <i>Oo, oo, oo, oo</i>"):
            with self.subTest(text=text[:24]):
                self.assertEqual(
                    gui._repetition_collapse_ids([("1", "x", text)], {}), [])


if __name__ == "__main__":
    unittest.main()
