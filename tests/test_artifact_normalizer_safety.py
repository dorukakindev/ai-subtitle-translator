import unittest

import sdh_cleaner


class ArtifactNormalizerSafetyTests(unittest.TestCase):
    def test_context_sensitive_words_are_not_blindly_rewritten(self):
        cases = (
            ("Mortuary'de çalışıyor.", "Mortuary'de çalışıyor."),
            ("Mummy, wait!", "Mummy, wait!"),
            ("Bu gerçek boy ölüm maskesi.", "Bu gerçek boy ölüm maskesi."),
            ("Yada bunu bilmiyordu.", "Yada bunu bilmiyordu."),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    sdh_cleaner.normalize_turkish_artifacts(source), expected)

    def test_specific_mummy_and_mortuary_residue_repairs_remain(self):
        self.assertEqual(
            sdh_cleaner.normalize_turkish_artifacts("mortuary school'a gitti"),
            "cenaze hizmetleri okuluna gitti",
        )
        self.assertEqual(
            sdh_cleaner.normalize_turkish_artifacts("mummy parts"),
            "Mumya parçaları",
        )


if __name__ == "__main__":
    unittest.main()
