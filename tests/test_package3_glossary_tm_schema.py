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

    def test_locked_terms_hint_sanitizes_glossary_and_preserves_names(self):
        """_locked_terms_hint sanitizes terms (dropping parens/notes/foreign script) while preserving character names."""
        import subtitle_translator_gui as gui
        from unittest.mock import MagicMock

        app = gui.App.__new__(gui.App)
        app._log = MagicMock()
        app._get_file_glossary = MagicMock(return_value="")

        pm = MagicMock()
        pm.get_glossary.return_value = {
            "sword": "kılıç",
            "shield": "kalkan",
            "Caesar": "Caesar (Sezar)",
            "maggot": "qurt/qurtçuk değil; askerî hakaret olarak mecazi 'pislik'/'larva' yerine doğrudan 'çürük kurt' anlamı vermeden...",
            "temple": "கோயிலும்"
        }
        pm.get_characters.return_value = {"Arthur": {}, "Merlin": {}}
        app._pm = pm

        hint = app._locked_terms_hint("file.srt", "Turkish")

        self.assertIn("sword -> kılıç", hint)
        self.assertIn("shield -> kalkan", hint)
        self.assertNotIn("Caesar (Sezar)", hint)
        self.assertNotIn("çürük kurt", hint)
        self.assertNotIn("கோயிலும்", hint)

        self.assertIn("LOCKED NAMES", hint)
        self.assertIn("Arthur", hint)
        self.assertIn("Merlin", hint)

    def test_glossary_token_matches_key_plural_s_handling(self):
        """_glossary_token_matches_key and _glossary_wqx_token require apostrophe + Turkish suffix for plural s matching."""
        # 1. Newsweeks -> Newsweek'ler (with apostrophe + Turkish suffix) is exempted
        self.assertTrue(ht._glossary_token_matches_key("Newsweek", {"newsweeks"}, raw_value="Newsweek'ler"))
        self.assertIsNone(ht._glossary_wqx_token("Newsweek'in sayısı", glossary_key="Newsweeks"))

        # 2. Without apostrophe + Turkish suffix, false s-stripping matches MUST BE FALSE
        self.assertFalse(ht._glossary_token_matches_key("Pari", {"paris"}, raw_value="Pari"))
        self.assertFalse(ht._glossary_token_matches_key("Jame", {"james"}, raw_value="Jame"))
        self.assertFalse(ht._glossary_token_matches_key("New", {"news"}, raw_value="New"))
        self.assertFalse(ht._glossary_token_matches_key("Xerxe", {"xerxes"}, raw_value="Xerxe"))
        self.assertFalse(ht._glossary_token_matches_key("What", {"whats"}, raw_value="What"))

        # Verify _glossary_wqx_token behavior directly
        self.assertEqual(ht._glossary_wqx_token("Xerxe kralı", glossary_key="Xerxes"), "Xerxe")

        # 3. Exact proper nouns match
        self.assertTrue(ht._glossary_token_matches_key("Princess", {"princess"}, raw_value="Princess"))
        self.assertTrue(ht._glossary_token_matches_key("Xerxes", {"xerxes"}, raw_value="Xerxes"))


if __name__ == "__main__":
    unittest.main()
