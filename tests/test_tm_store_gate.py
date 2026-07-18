"""TranslationMemory.store / store_batch — kayıt-anı güvenlik gate'i (Görev 2,
future-quality-guards-brief.md). Amaç: sızıntı/bozuk-token içeren bir çeviri TM'ye
GİRMESİN — aksi hâlde fuzzy/exact eşleşmeyle gelecekteki bölümlere geri taşınır,
ki bu tüm diğer guard'ları by-pass eden tek yoldur.
"""
import os
import tempfile
import unittest

from translation_memory import TranslationMemory


class TMStoreGateTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = path
        self.tm = TranslationMemory(db_path=path)

    def tearDown(self):
        self.tm.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_non_turkish_leak_target_not_stored(self):
        ok = self.tm.store("welcome party", "Bir bäýram/holidaý oturylyşyğı.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertIsNone(self.tm.lookup("welcome party", tgt_lang="Turkish"))

    def test_garble_token_target_not_stored(self):
        ok = self.tm.store("Luciferian symbolism", "esas olarak simwolika yaydı.", tgt_lang="Turkish")
        self.assertFalse(ok)
        self.assertIsNone(self.tm.lookup("Luciferian symbolism", tgt_lang="Turkish"))

    def test_hata_placeholder_not_stored(self):
        # Regresyon kilidi — bu kontrol Görev 2'den ÖNCE de vardı.
        ok = self.tm.store("hello there", "[HATA]", tgt_lang="Turkish")
        self.assertFalse(ok)

    def test_clean_pair_stored_and_retrievable(self):
        ok = self.tm.store("hello", "merhaba", tgt_lang="Turkish")
        self.assertTrue(ok)
        self.assertEqual(self.tm.lookup("hello", tgt_lang="Turkish"), "merhaba")


class TMStoreBatchGateTest(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.path = path
        self.tm = TranslationMemory(db_path=path)

    def tearDown(self):
        self.tm.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_mixed_batch_only_clean_pairs_saved(self):
        pairs = [
            ("good morning", "günaydın"),
            ("welcome party", "Bir bäýram/holidaý oturylyşyğı."),  # sızıntı
            ("Luciferian symbolism", "esas olarak simwolika yaydı."),  # garble
            ("good night", "iyi geceler"),
            ("skip me", "[HATA]"),  # zaten mevcut kural
        ]
        self.tm.store_batch(pairs, tgt_lang="Turkish")
        self.assertEqual(self.tm.lookup("good morning", tgt_lang="Turkish"), "günaydın")
        self.assertEqual(self.tm.lookup("good night", tgt_lang="Turkish"), "iyi geceler")
        self.assertIsNone(self.tm.lookup("welcome party", tgt_lang="Turkish"))
        self.assertIsNone(self.tm.lookup("Luciferian symbolism", tgt_lang="Turkish"))
        self.assertIsNone(self.tm.lookup("skip me", tgt_lang="Turkish"))


if __name__ == "__main__":
    unittest.main()
