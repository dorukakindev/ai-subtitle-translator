# -*- coding: utf-8 -*-
"""Teslim taraması AKIŞA GÖRE DEĞİL, her satır için çalışsın.

Ölçüm (2026-08-28, gerçek raporlar): 493 teslim satırının 261'inde (%53)
`delivery_scan` yoktu. Denetim (`delivery_audit`) merkezî olarak
`_save_quality_report` içinde her satır için hesaplanıyordu; tarama ise üç
akışın İÇİNE ayrı ayrı yazılmıştı ve yapmayan akışta hiç çalışmıyordu.
O dosyalar `cue_id_leak`, `source_residue`, `broken_italic`,
`repetition_collapse` gibi hiçbir tarama bulgusu almadı.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import subtitle_translator_gui as gui
from tests._gui_app import make_app


SRC = ("1\n00:00:01,000 --> 00:00:02,000\nOne line here.\n\n"
       "2\n00:00:03,000 --> 00:00:04,000\nAnother line here.\n")
OUT = ("1\n00:00:01,000 --> 00:00:02,000\n<i><i>Bir satır burada.</i></i>\n\n"
       "2\n00:00:03,000 --> 00:00:04,000\nBaşka bir satır burada.\n")


class DeliveryScanParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_scan_is_produced_from_the_files_on_disk(self):
        with TemporaryDirectory() as root:
            source = Path(root, "s.srt")
            output = Path(root, "o.srt")
            source.write_text(SRC, encoding="utf-8")
            output.write_text(OUT, encoding="utf-8")
            scan = self.app._delivery_scan_for_row(str(source), str(output))
        self.assertIsInstance(scan, dict)
        self.assertTrue(scan)
        # Bozuk italik bu satırda gerçekten var
        self.assertIn("1", scan.get("broken_italic_ids") or [])

    def test_missing_output_does_not_break_the_report(self):
        self.assertEqual(self.app._delivery_scan_for_row("", ""), {})
        self.assertEqual(
            self.app._delivery_scan_for_row("yok.srt", "yok-da.srt"), {})

    def test_scan_runs_where_the_audit_runs(self):
        """İkisi aynı yerde: bir akış birini alıp diğerini alamaz."""
        import inspect
        source = inspect.getsource(gui.App._save_quality_report)
        self.assertIn('row["delivery_audit"] = _subtitle_delivery_audit', source)
        self.assertIn('row["delivery_scan"] = self._delivery_scan_for_row',
                      source)

    def test_flow_supplied_scan_is_not_overwritten(self):
        """Akış kendi taramasını yaptıysa merkezî yol ona dokunmaz."""
        import inspect
        source = inspect.getsource(gui.App._save_quality_report)
        self.assertIn('if not isinstance(row.get("delivery_scan"), dict):',
                      source)


if __name__ == "__main__":
    unittest.main()
