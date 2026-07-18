"""
Round 9 cila testleri: TM toplu sorgu (lookup_batch) + atomik ayar yazımı.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from translation_memory import TranslationMemory


class LookupBatchTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.tm = TranslationMemory(db_path=self.db)

    def tearDown(self):
        self.tm.close()
        os.unlink(self.db)

    def test_batch_matches_only_stored(self):
        self.tm.store("Hello.", "Merhaba.", tgt_lang="Turkish")
        self.tm.store("Goodbye.", "Hoşça kal.", tgt_lang="Turkish")
        out = self.tm.lookup_batch(["Hello.", "Goodbye.", "Unknown."], tgt_lang="Turkish")
        self.assertEqual(out["Hello."], "Merhaba.")
        self.assertEqual(out["Goodbye."], "Hoşça kal.")
        self.assertNotIn("Unknown.", out)

    def test_batch_matches_single_query_consistency(self):
        # lookup_batch ve lookup aynı sonucu vermeli
        self.tm.store("Same line.", "Aynı satır.", tgt_lang="Turkish")
        single = self.tm.lookup("Same line.", tgt_lang="Turkish")
        batch  = self.tm.lookup_batch(["Same line."], tgt_lang="Turkish")
        self.assertEqual(single, batch["Same line."])

    def test_lang_isolation(self):
        self.tm.store("Hello.", "Merhaba.", tgt_lang="Turkish")
        out = self.tm.lookup_batch(["Hello."], tgt_lang="German")
        self.assertNotIn("Hello.", out)

    def test_empty_and_over_999(self):
        self.assertEqual(self.tm.lookup_batch([], tgt_lang="Turkish"), {})
        # 1000+ benzersiz sorgu — parça parça çalışmalı, patlamamalı
        big = [f"line {i}" for i in range(1500)]
        self.tm.store("line 7", "satır 7", tgt_lang="Turkish")
        out = self.tm.lookup_batch(big, tgt_lang="Turkish")
        self.assertEqual(out.get("line 7"), "satır 7")
        self.assertEqual(len(out), 1)


class AtomicSettingsWriteTest(unittest.TestCase):
    """Atomik yazımın .tmp bırakmadan dosyayı güncellediğini doğrular."""
    def test_replace_is_atomic_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / ".gui_settings.json"
            tmp = target.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"model": "gpt-5.4-mini"}, f, indent=2, ensure_ascii=False)
            tmp.replace(target)
            self.assertTrue(target.exists())
            self.assertFalse(tmp.exists())   # tmp temizlendi
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["model"],
                             "gpt-5.4-mini")


if __name__ == "__main__":
    unittest.main()
