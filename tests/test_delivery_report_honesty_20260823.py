# -*- coding: utf-8 -*-
"""Teslim ve rapor katmanının dürüstlüğü.

Hepsi 'çıktı vaat edilenden farklı' sınıfı: işaret hiç yazılmıyor, rapor
istenen geçişi uygulanmış gösteriyor, iki sayı aynı içeriği ölçmüyor.
"""
import inspect
import os
import sys
import unittest
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)
TS = "00:00:01,000 --> 00:00:03,000"


class UploadReadyMarkerOnSuccessTest(unittest.TestCase):
    """Başarılı koşuda 'YÜKLEMEYE HAZIR.txt' hiç yazılmıyordu.

    `_finalize_run_record` durumu Türkçe yazıyor ('tamamlandı'), plan ise
    yalnız 'done'/'completed' kabul ediyordu. Sonuç: işaret yazılmadığı
    gibi varsa bayat sayılıp siliniyordu.
    """

    def setUp(self):
        self._original = g._output_matches_source_fingerprint
        g._output_matches_source_fingerprint = lambda *a, **k: True
        self.addCleanup(setattr, g, "_output_matches_source_fingerprint",
                        self._original)

    def _record(self, status, folder):
        source = os.path.join(folder, "a.srt")
        output = os.path.join(folder, "a.tr.srt")
        for path, text in ((source, "Hi"), (output, "Selam")):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("1" + NL + TS + NL + text + NL)
        return {
            "status": status,
            "settings": {"input_dir": folder, "output_dir": folder},
            "files": {source: {"status": "done", "output_path": output}},
        }

    def _plan(self, status):
        with TemporaryDirectory() as folder:
            return g.upload_ready_marker_plan(self._record(status, folder))

    def test_the_turkish_success_status_is_accepted(self):
        ready, stale = self._plan(g.RUN_STATUS_DONE)
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(stale), 0)

    def test_the_english_spellings_still_work(self):
        for status in ("done", "completed"):
            with self.subTest(status=status):
                ready, _stale = self._plan(status)
                self.assertEqual(len(ready), 1)

    def test_a_partial_or_stopped_run_is_still_blocked(self):
        for status in ("kısmen tamamlandı", "durduruldu", "başarısız",
                       "eksik"):
            with self.subTest(status=status):
                ready, stale = self._plan(status)
                self.assertEqual(len(ready), 0)
                self.assertEqual(len(stale), 1)

    def test_the_finalizer_and_the_plan_share_one_constant(self):
        self.assertIn(g.RUN_STATUS_DONE, g.RUN_STATUS_SUCCESS)
        self.assertIn('record["status"] = RUN_STATUS_DONE',
                      inspect.getsource(g.App._finalize_run_record))
        self.assertIn("run_status not in RUN_STATUS_SUCCESS",
                      inspect.getsource(g.upload_ready_marker_plan))


class SignaturesAreNotTranslationTest(unittest.TestCase):
    """208 gerçek teslimin hepsinde üç imza var.

    Satır sayısı onları paydadan çıkarırken CPS ölçüyordu: 57 dosyada
    ortalama/maksimum CPS, 25 dosyada CPS aşım sayısı değişiyordu.
    """

    BLOCKS = [
        ("0", TS, "discord: ceviri2"),
        ("1", TS, "Kısa satır."),
        ("2", TS, "discord: ceviri2"),
    ]

    def test_the_line_count_and_cps_measure_the_same_cues(self):
        self.assertEqual(g.delivery_line_count(self.BLOCKS), 1)
        avg, top = g._cps_stats(self.BLOCKS)
        alone = g._cps_stats([self.BLOCKS[1]])
        self.assertEqual((avg, top), alone)

    def test_a_signature_never_counts_as_a_cps_breach(self):
        fast_signature = [("0", "00:00:01,000 --> 00:00:01,200",
                           "discord: ceviri2")]
        _hata, cps = g._count_hata_cps(fast_signature)
        self.assertEqual(cps, 0)

    def test_a_real_breach_is_still_counted(self):
        fast = [("1", "00:00:01,000 --> 00:00:01,500",
                 "Bu cümle gerçekten çok uzun ve okunamayacak kadar hızlı.")]
        _hata, cps = g._count_hata_cps(fast)
        self.assertEqual(cps, 1)


class RealisedPassesAreReportedSeparatelyTest(unittest.TestCase):
    """`pass_coverage` açık UI kutularından kuruluyor — İSTENEN geçişler.

    Rapor onu 'Uygulanan geçişler' diye gösteriyordu; 100 koşu raporunda
    20 dosyada 21 çelişki ölçüldü.
    """

    ROW = {
        "name": "X.srt", "total": 100,
        "pass_coverage": "Critic, Polish, Native",
        "pass_status": {
            "Critic": {"status": "partial"},
            "Native": {"status": "skipped", "reason": "not_series"},
            "Polish": {"report_only": True},
        },
        "pass_trace": {"Polish": 12, "Critic": 0},
    }

    def _report(self):
        return g.build_quality_report_text(
            [self.ROW], "gpt-5.4", "Turkish", "sync", 0)

    def test_the_requested_row_is_named_honestly(self):
        text = self._report()
        self.assertIn("İstenen geçişler", text)
        self.assertNotIn("Uygulanan geçişler", text)

    def test_the_realised_row_reflects_what_happened(self):
        line = g.realised_pass_line(self.ROW)
        self.assertIn("Critic: kısmi", line)
        self.assertIn("Native: atlandı", line)
        self.assertIn("Polish: yalnız rapor", line)

    def test_the_skip_reason_is_spelled_out(self):
        self.assertIn("dizi bölümü olarak tanınmadı",
                      g.realised_pass_line(self.ROW))

    def test_a_pass_with_no_status_still_shows_its_change_count(self):
        line = g.realised_pass_line({"pass_trace": {"Condense": 0}})
        self.assertEqual(line, "Condense: değişiklik yok")

    def test_an_empty_row_produces_no_line(self):
        self.assertEqual(g.realised_pass_line({}), "")


if __name__ == "__main__":
    unittest.main()
