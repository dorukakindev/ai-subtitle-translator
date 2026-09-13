"""Tests for actual bugs found in audit, not false positives."""
import unittest
from pathlib import Path
import hybrid_translate as ht


class SortKeyMixedIntStrTest(unittest.TestCase):
    def test_mixed_keys_no_crash(self):
        """save_results sort does not crash on mixed int/str keys."""
        srt_blocks = {"1": ("1", "a", "x"), "abc": ("abc", "b", "y"), "2": ("2", "c", "z")}
        sorted_keys = sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))
        # Numeric keys first in numeric order, then string keys alphabetically
        self.assertEqual(sorted_keys, ["1", "2", "abc"])

    def test_all_numeric_keys(self):
        """All numeric keys still sort correctly."""
        srt_blocks = {"3": (), "1": (), "10": (), "2": ()}
        sorted_keys = sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))
        self.assertEqual(sorted_keys, ["1", "2", "3", "10"])

    def test_all_string_keys(self):
        """Non-numeric keys sort alphabetically after numeric."""
        srt_blocks = {"foo": (), "bar": (), "baz": ()}
        sorted_keys = sorted(srt_blocks, key=lambda k: (0, int(k)) if str(k).isdigit() else (1, str(k)))
        self.assertEqual(sorted_keys, ["bar", "baz", "foo"])

    def test_repair_batches_sort_fixed(self):
        """repair_batches.py sort key uses safe tuple pattern."""
        repair_src = (Path(__file__).resolve().parents[1] / 'repair_batches.py').read_text(
            encoding='utf-8')
        self.assertIn("(0, int(k))", repair_src)
        self.assertIn("(1, str(k))", repair_src)


class CeviriEksikSkipTest(unittest.TestCase):
    def test_ceviri_eksik_not_flagged(self):
        """[ÇEVİRİ EKSİK] lines are skipped entirely, produce no reasons."""
        class FakeCue:
            index = 1
            text = "This has some important meaning"
        fake_cues = [FakeCue()]
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "[ÇEVİRİ EKSİK]")]
        suspicious = ht.run_validators(tr_blocks, cues=fake_cues)
        # Should have zero suspicious items (the placeholder is skipped)
        self.assertEqual(len(suspicious), 0)

    def test_hata_still_skipped(self):
        """[HATA] lines continue to be skipped."""
        class FakeCue:
            index = 1
            text = "This has some important meaning"
        fake_cues = [FakeCue()]
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "[HATA]")]
        suspicious = ht.run_validators(tr_blocks, cues=fake_cues)
        self.assertEqual(len(suspicious), 0)

    def test_real_text_still_checked(self):
        """Real translation text continues to be validated."""
        class FakeCue:
            index = 1
            text = "I don't know"
        fake_cues = [FakeCue()]
        tr_blocks = [("1", "00:00:01 --> 00:00:04", "biliyorum")]
        suspicious = ht.run_validators(tr_blocks, cues=fake_cues)
        self.assertGreater(len(suspicious), 0)


if __name__ == "__main__":
    unittest.main()
