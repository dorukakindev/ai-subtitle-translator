import unittest
from subtitle_formats import restore_format_tags

class TestFormatTagRestore(unittest.TestCase):
    def test_restore(self):
        self.assertEqual(restore_format_tags("<i>Hello</i>", "Merhaba"), "<i>Merhaba</i>")
        self.assertEqual(restore_format_tags("<i>Hello</i>", "[HATA] Error"), "[HATA] Error")
        self.assertEqual(restore_format_tags("<i>Hello</i>", "[ÇEVİRİ EKSİK]"), "[ÇEVİRİ EKSİK]")
        self.assertEqual(restore_format_tags("<i>Hello</i>", " [ÇEVİRİ EKSİK] "), " [ÇEVİRİ EKSİK] ")

if __name__ == "__main__":
    unittest.main()
