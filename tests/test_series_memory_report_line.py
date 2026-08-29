# -*- coding: utf-8 -*-
"""Dizi Hafızası kaydı yoksa rapor NEDENİ yazmalı, "bilinmiyor" değil.

Zincir (2026-08-28, her halkası ölçüldü):
Dosya teslim kapısını geçemezse dört akış da `continue` ediyor ve
`_pass_status["Series-Memory"]` hiç oluşmuyor → rapor `else` dalına düşüp
"açık, çalışma kaydı yok" yazıyordu. Davranış DOĞRU (eksik/bozuk bölümden
dizi kanonu yazılmamalı); yanlış olan raporun bunu bilinmiyor gibi
göstermesiydi — oysa satırın kendisi nedeni taşıyor.

Arşiv ölçümü: 494 rapor bloğunun 156'sı "çalışma kaydı yok" diyordu;
149'u (%95,5) eksik çeviri / kısmi çıktı / tarama uyarısı taşıyor.
Kalan 7'de satır `done` olduğu için eski metin korunur — yardımcı
neden UYDURMAZ.
"""
import unittest

import subtitle_translator_gui as gui


class MissingLineTest(unittest.TestCase):
    def test_missing_translation_is_named(self):
        line = gui.series_memory_missing_line(
            {"run_status": "error", "hata": 4})
        self.assertIn("atlandı", line)
        self.assertIn("eksik çeviri", line)

    def test_failed_delivery_scan_is_named(self):
        line = gui.series_memory_missing_line(
            {"run_status": "error", "hata": 0, "delivery_scan_failed": True})
        self.assertIn("teslim taraması", line)

    def test_other_error_still_says_skipped(self):
        line = gui.series_memory_missing_line(
            {"run_status": "error", "hata": 0})
        self.assertIn("atlandı", line)
        self.assertIn("tamamlanmış sayılmadı", line)

    def test_review_status_is_named(self):
        line = gui.series_memory_missing_line({"run_status": "review"})
        self.assertIn("incelemeye ayrıldı", line)

    def test_clean_file_keeps_the_old_wording(self):
        """Hatasız dosyada kayıt yoksa neden GERÇEKTEN bilinmiyor."""
        for row in ({"run_status": "done"}, {}, None, "bozuk"):
            with self.subTest(row=row):
                self.assertEqual(gui.series_memory_missing_line(row),
                                 "Dizi Hafızası: açık, çalışma kaydı yok")

    def test_every_branch_keeps_the_feature_name(self):
        for row in ({"run_status": "error", "hata": 1},
                    {"run_status": "error", "delivery_scan_failed": True},
                    {"run_status": "error"},
                    {"run_status": "review"},
                    {"run_status": "done"}):
            with self.subTest(row=row):
                self.assertTrue(
                    gui.series_memory_missing_line(row).startswith(
                        "Dizi Hafızası: "))


class ReportUsesTheHelperTest(unittest.TestCase):
    """İki `else` dalı da yardımcıdan geçmeli; biri kalırsa açık geri döner."""

    def test_no_bare_fallback_text_is_left(self):
        import inspect
        source = inspect.getsource(gui.build_file_quality_lines) if hasattr(
            gui, "build_file_quality_lines") else inspect.getsource(gui)
        marker = source.index('series_enabled = bool(snapshot.get("series_memory"))')
        window = source[marker:marker + 1400]
        self.assertEqual(window.count("series_memory_missing_line(row)"), 2)
        self.assertNotIn('lines.append("Dizi Hafızası: açık, çalışma kaydı yok")',
                         window)



class FlowRecordsTheReasonTest(unittest.TestCase):
    """Kök neden AKIŞTA kapatıldı: artık satır nedeni kendi taşıyor.

    Rapor tarafındaki çıkarım (`series_memory_missing_line`) eski
    dosyalar için geri düşüş olarak kalır; yeni koşularda akış zaten
    `{"status": "skipped", "reason": ...}` yazar.
    """

    def test_write_results_has_the_missing_else(self):
        import inspect
        source = inspect.getsource(gui.App._write_results)
        marker = source.index("if _hata_n == 0 and _n_filled == 0:")
        window = source[marker:marker + 900]
        self.assertIn('"reason": ("unresolved_markers" if _hata_n', window)
        self.assertIn('else "cue_fill_applied"', window)

    def test_both_gate_paths_record_before_continue(self):
        import inspect
        source = inspect.getsource(gui)
        self.assertEqual(
            source.count('_pass_status.setdefault("Series-Memory", {'), 3)

    def test_sync_hybrid_separates_its_three_causes(self):
        import inspect
        source = inspect.getsource(gui.App._run_sync_hybrid)
        self.assertIn('"analysis_incomplete" if not _analysis_ok', source)
        self.assertIn('else "unresolved_markers" if _hata_n', source)

    def test_new_reasons_are_readable(self):
        for reason, beklenen in (
                ("unresolved_markers", "eksik çeviri"),
                ("cue_fill_applied", "cue-fill"),
                ("delivery_failed", "teslim kapısı"),
                ("quality_failed", "kalite")):
            with self.subTest(reason=reason):
                metin = gui.pass_skip_explanation(
                    {"status": "skipped", "reason": reason})
                self.assertIn(beklenen, metin)

    def test_report_line_uses_the_shared_table(self):
        for reason, beklenen in (
                ("unresolved_markers", "eksik çeviri işareti"),
                ("cue_fill_applied", "cue-fill taşıması"),
                ("delivery_failed", "teslim kapısını geçemedi"),
                ("quality_failed", "kalite/teslim denetimi"),
                ("not_series", "dizi bölümü algılanmadı")):
            with self.subTest(reason=reason):
                lines = gui._quality_feature_audit(
                    {"run_status": "error",
                     "pass_status": {"Series-Memory": {
                         "status": "skipped", "reason": reason}}},
                    {"series_memory": True, "mode": "sync"})
                satir = next(l for l in lines if "Dizi Hafızası" in l)
                self.assertIn(beklenen, satir)
                self.assertNotIn("uygulanmadı", satir)
                self.assertNotIn("çalışma kaydı yok", satir)

if __name__ == "__main__":
    unittest.main()
