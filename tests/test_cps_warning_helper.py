"""_log_cps_warning (subtitle_translator_gui.py) — CPS_WARN_LIMIT'i aşan satırları
sayıp tek uyarı loglayan paylaşılan helper. Batch-parite işi (2026-07-10): inline CPS
bloğu (_run_sync_hybrid) bu helper'a çıkarıldı, hybrid-batch/düz-batch akışlarına da
eklendi — böylece sync'in CPS görünürlüğü tüm akışlarda var. Bu test extraction'ın
davranışını kilitler (sessizce bozulmasın)."""
import unittest

import subtitle_translator_gui as gui


class LogCpsWarningTest(unittest.TestCase):
    def _run(self, blocks):
        logs = []
        n = gui._log_cps_warning(blocks, lambda m, lvl=None: logs.append(m))
        return n, logs

    def test_fast_line_counted_and_logged(self):
        # 0.5 sn'de ~60 karakter → ~120 kar/sn, sınırın (24) çok üstünde.
        blocks = [("1", "00:00:01,000 --> 00:00:01,500",
                   "Bu satır yarım saniyede okunamayacak kadar uzun ve hızlıdır kesinlikle.")]
        n, logs = self._run(blocks)
        self.assertEqual(n, 1)
        self.assertTrue(logs and "CPS uyarısı" in logs[0])
        self.assertIn("#1", logs[0])

    def test_slow_line_not_counted(self):
        blocks = [("1", "00:00:01,000 --> 00:00:11,000", "Kısa.")]
        n, logs = self._run(blocks)
        self.assertEqual(n, 0)
        self.assertEqual(logs, [])

    def test_counts_only_fast_lines_in_mixed_set(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:11,000", "Rahat okunur."),          # yavaş
            ("2", "00:00:11,000 --> 00:00:11,400",
             "Çok uzun bir cümle bu kadar kısa sürede asla okunamaz maalesef."),  # hızlı
            ("3", "00:00:12,000 --> 00:00:20,000", "Bu da rahat."),           # yavaş
        ]
        n, logs = self._run(blocks)
        self.assertEqual(n, 1)

    def test_newlines_excluded_from_length(self):
        # \n karakterleri uzunluğa sayılmaz (görünür metin bazlı).
        blocks = [("1", "00:00:01,000 --> 00:00:05,000", "İki\nsatır kısa.")]
        n, _ = self._run(blocks)
        self.assertEqual(n, 0)

    def test_malformed_timestamp_ignored(self):
        blocks = [("1", "bozuk-zaman-damgası", "herhangi bir metin")]
        n, logs = self._run(blocks)
        self.assertEqual(n, 0)
        self.assertEqual(logs, [])

    def test_no_log_fn_does_not_crash(self):
        # log_fn None ise sayım yine döner, log atılmaz.
        n = gui._log_cps_warning([("1", "00:00:01,000 --> 00:00:01,200",
                                   "Aşırı hızlı bir satır burada uzun uzun yazılmış hâlde.")], None)
        self.assertEqual(n, 1)

    def test_empty_blocks(self):
        n, logs = self._run([])
        self.assertEqual(n, 0)
        self.assertEqual(logs, [])


if __name__ == "__main__":
    unittest.main()
