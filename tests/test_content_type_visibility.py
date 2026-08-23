# -*- coding: utf-8 -*-
"""İçerik türü hangi aşamada olursa olsun görünür olmalı.

Kullanıcı kenar çubuğunda 'Otomatik' görüyor, ama 2026-08-23 02:21 koşusunda
ne ön analiz çalıştı ne de logda türden söz edildi; dosya jenerik şemayla
çevrildi ve bu ancak teslimden sonra fark edilebilirdi. Atlama artık
nedeniyle loglanıyor, kullanılan tür hem loga hem kalite raporuna yazılıyor.
"""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class SkipIsLoggedTest(unittest.TestCase):

    def test_start_explains_why_the_preflight_was_skipped(self):
        source = inspect.getsource(g.App._start)
        self.assertIn("_auto_type_files = self._auto_content_type_files(", source)
        self.assertIn("İçerik türü ön analizi atlandı:", source)

    def test_both_skip_reasons_are_distinguished(self):
        source = inspect.getsource(g.App._start)
        self.assertIn("hiçbirinde tür 'Otomatik'", source)
        self.assertIn("kurtarma/yeniden deneme akışı", source)

    def test_the_preflight_still_runs_when_files_are_automatic(self):
        source = inspect.getsource(g.App._start)
        marker = source.index("_auto_type_files = ")
        window = source[marker:marker + 400]
        self.assertIn("self._start_content_type_preflight(key, srt_files)", window)


class ResolvedTypeIsLoggedTest(unittest.TestCase):

    def test_both_hybrid_flows_log_the_content_type(self):
        for method in (g.App._run_sync_hybrid, g.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertIn('İçerik türü: ', source)

    def test_it_is_logged_next_to_the_analysis_depth(self):
        source = inspect.getsource(g.App._run_sync_hybrid)
        self.assertLess(source.index("İçerik türü: "),
                        source.index("Analiz derinligi"))


class ReportShowsTheTypeTest(unittest.TestCase):

    ROWS = [
        {"name": "X.srt", "total": 100, "schema_name": "Belgesel",
         "pass_coverage": "Critic"},
        {"name": "Y.srt", "total": 50, "pass_coverage": "-"},
    ]

    def _report(self, rows=None):
        return g.build_quality_report_text(
            rows if rows is not None else self.ROWS,
            "gpt-5.4", "Turkish", "sync", 0)

    def test_the_type_is_printed_for_the_file(self):
        self.assertIn("İçerik türü", self._report())
        self.assertIn("Belgesel", self._report())

    def test_a_row_without_a_type_prints_no_empty_line(self):
        text = self._report([self.ROWS[1]])
        self.assertNotIn("İçerik türü", text)

    def test_every_flow_fills_the_field(self):
        # Dört ana akış + iki yan yol (yalnız-onarım, hybrid kısmi/başarısız):
        # bu satırlar da içerik türü yazmalı, yoksa rapor eksik kalıyor.
        source = inspect.getsource(g)
        self.assertGreaterEqual(source.count('"schema_name": ('), 6)

    def test_the_side_paths_also_fill_it(self):
        for method in (g.App._run_sync_hybrid, g.App._run_hybrid):
            with self.subTest(method=method.__name__):
                self.assertIn('"schema_name": (schema_dict or {}).get',
                              inspect.getsource(method))


if __name__ == "__main__":
    unittest.main()
