"""
hybrid_translate.condense okuma hızı (CPS) yardımcıları için testler.
condense_fast_lines API çağrısı yaptığı için sadece saf yardımcıları test ediyoruz:
_block_duration ve find_fast_lines.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# hybrid_translate dış subtitle_localizer projesini import edebilir;
# bu testler sadece saf fonksiyonları kullandığı için modülü doğrudan içe alıyoruz.
import hybrid_translate as ht


class BlockDurationTest(unittest.TestCase):
    def test_basic_duration(self):
        ts = "00:00:01,000 --> 00:00:04,000"
        self.assertAlmostEqual(ht._block_duration(ts), 3.0, places=2)

    def test_subsecond_duration(self):
        ts = "00:00:10,500 --> 00:00:12,000"
        self.assertAlmostEqual(ht._block_duration(ts), 1.5, places=2)

    def test_malformed_returns_zero(self):
        self.assertEqual(ht._block_duration("not a timestamp"), 0.0)

    def test_minutes_hours(self):
        ts = "01:02:03,000 --> 01:02:05,000"
        self.assertAlmostEqual(ht._block_duration(ts), 2.0, places=2)


class FindFastLinesTest(unittest.TestCase):
    def test_detects_too_fast_line(self):
        # 60 karakter / 1 saniye = 60 CPS — sınır 21'in çok üstünde
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "A" * 60)]
        fast = ht.find_fast_lines(blocks, cps_limit=21.0)
        self.assertEqual(len(fast), 1)
        self.assertEqual(fast[0][0], "1")

    def test_ignores_comfortable_line(self):
        # 10 karakter / 5 saniye = 2 CPS — rahat okunur
        blocks = [("1", "00:00:01,000 --> 00:00:06,000", "Merhaba")]
        fast = ht.find_fast_lines(blocks, cps_limit=21.0)
        self.assertEqual(fast, [])

    def test_char_budget_is_limit_times_duration(self):
        # 2 saniye, limit 20 → bütçe 40 karakter
        blocks = [("5", "00:00:00,000 --> 00:00:02,000", "X" * 100)]
        fast = ht.find_fast_lines(blocks, cps_limit=20.0)
        self.assertEqual(len(fast), 1)
        self.assertEqual(fast[0][2], 40)

    def test_skips_hata_blocks(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        self.assertEqual(ht.find_fast_lines(blocks), [])

    def test_skips_zero_duration(self):
        blocks = [("1", "00:00:02,000 --> 00:00:02,000", "A" * 50)]
        self.assertEqual(ht.find_fast_lines(blocks), [])

    def test_newlines_not_counted_as_extra(self):
        # İki satır toplam 60 görünür karakter (newline sayılmaz) / 1 sn → hızlı
        text = ("A" * 30) + "\n" + ("B" * 30)
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", text)]
        fast = ht.find_fast_lines(blocks, cps_limit=21.0)
        self.assertEqual(len(fast), 1)

    def test_mixed_blocks(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "A" * 50),   # hızlı
            ("2", "00:00:02,000 --> 00:00:08,000", "kısa"),      # rahat
            ("3", "00:00:08,000 --> 00:00:09,000", "B" * 40),    # hızlı
        ]
        fast = ht.find_fast_lines(blocks, cps_limit=21.0)
        ids = [f[0] for f in fast]
        self.assertEqual(ids, ["1", "3"])


class CondensePassStatusTest(unittest.TestCase):
    def test_total_api_failure_is_not_reported_as_completed(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "A" * 60)]
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create",
                side_effect=RuntimeError("provider unavailable")):
            result, changed = ht.condense_fast_lines(
                blocks, "key", helper_model="model", status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(changed, 0)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["successful_chunks"], 0)
        self.assertEqual(status["failed_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
