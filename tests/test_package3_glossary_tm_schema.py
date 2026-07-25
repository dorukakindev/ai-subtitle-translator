import unittest
import tempfile
from pathlib import Path

import hybrid_translate as ht
from translation_memory import TranslationMemory


class TestPackage3GlossaryAndTmSchema(unittest.TestCase):
    def test_sanitize_glossary_preserves_proper_noun_wqx_terms(self):
        """sanitize_glossary_for_turkish does not drop valid proper nouns with w, q, x."""
        glossary = {
            "Hollywood": "Hollywoodlu sanatçı",
            "Squid Game": "Squid Game oyunu",
            "X-Men": "X-Men takımı",
            "Washington": "Washington'ın"
        }
        cleaned = ht.sanitize_glossary_for_turkish(glossary)
        self.assertIn("Hollywood", cleaned)
        self.assertIn("Squid Game", cleaned)
        self.assertIn("X-Men", cleaned)
        self.assertIn("Washington", cleaned)

    def test_sanitize_glossary_drops_true_foreign_drift(self):
        """sanitize_glossary_for_turkish drops terms with true non-Turkish drift."""
        dirty_glossary = {
            "President": "madaxweynaha",
            "World Bank": "bangiga_wqx"
        }
        cleaned = ht.sanitize_glossary_for_turkish(dirty_glossary)
        self.assertEqual(cleaned, {})

    def test_tm_schema_isolation_fingerprint(self):
        """_settings_fingerprint includes schema_name correctly."""
        fp1 = TranslationMemory._settings_fingerprint("gpt-4o", "saygılı", "anime")
        fp2 = TranslationMemory._settings_fingerprint("gpt-4o", "saygılı", "frp")
        self.assertNotEqual(fp1, fp2)
        self.assertIn("s:anime", fp1)
        self.assertIn("s:frp", fp2)

    def test_tm_schema_isolation_store_and_lookup(self):
        """Entries stored under one schema_name are isolated from lookups of another schema_name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_tm.db"
            tm = TranslationMemory(db_path=db_path)
            try:
                tm.store("Spellbook of light", "Işık büyü kitabı", model="gpt-4o", tgt_lang="tr", schema_name="frp")
                tm.store("Spellbook of light", "Işık kitabı", model="gpt-4o", tgt_lang="tr", schema_name="anime")

                hit_frp = tm.lookup("Spellbook of light", tgt_lang="tr", model="gpt-4o", schema_name="frp")
                hit_anime = tm.lookup("Spellbook of light", tgt_lang="tr", model="gpt-4o", schema_name="anime")
                hit_belgesel = tm.lookup("Spellbook of light", tgt_lang="tr", model="gpt-4o", schema_name="belgesel")

                self.assertEqual(hit_frp, "Işık büyü kitabı")
                self.assertEqual(hit_anime, "Işık kitabı")
                self.assertIsNone(hit_belgesel)
            finally:
                tm.close()

    def test_tm_schema_isolation_fuzzy_lookup(self):
        """fuzzy_lookup respects schema_name isolation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_tm.db"
            tm = TranslationMemory(db_path=db_path)
            try:
                tm.store("Spellbook of divine light", "Kutsal ışık büyü kitabı", model="gpt-4o", tgt_lang="tr", schema_name="frp")

                fuzzy_frp = tm.fuzzy_lookup("Spellbook of divine light!", threshold=0.85, tgt_lang="tr", model="gpt-4o", schema_name="frp")
                fuzzy_anime = tm.fuzzy_lookup("Spellbook of divine light!", threshold=0.85, tgt_lang="tr", model="gpt-4o", schema_name="anime")

                self.assertIsNotNone(fuzzy_frp)
                self.assertEqual(fuzzy_frp[0], "Kutsal ışık büyü kitabı")
                self.assertIsNone(fuzzy_anime)
            finally:
                tm.close()


if __name__ == "__main__":
    unittest.main()
