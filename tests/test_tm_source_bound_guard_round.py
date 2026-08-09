import os
import tempfile
import unittest

from translation_memory import TranslationMemory


class TranslationMemorySourceBoundGuardTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.tm = TranslationMemory(db_path=self.path)

    def tearDown(self):
        self.tm.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_source_preserved_scientific_and_foreign_terms_are_stored(self):
        pairs = [
            ("They call the custom coquiando.", "Bu gelenek coquiando diye anilir."),
            ("The meal includes bratwurst.", "Yemekte bratwurst var."),
            ("Penicillium camemberti grows here.", "Penicillium camemberti burada buyur."),
        ]

        self.tm.store_batch(pairs, tgt_lang="Turkish")

        for source, target in pairs:
            self.assertEqual(self.tm.lookup(source, tgt_lang="Turkish"), target)

    def test_real_source_english_residue_is_not_stored(self):
        source = "Christianity spread through the colony."
        target = "Christianity kolonide yayildi."

        self.assertFalse(self.tm.store(source, target, tgt_lang="Turkish"))
        self.assertIsNone(self.tm.lookup(source, tgt_lang="Turkish"))


if __name__ == "__main__":
    unittest.main()
