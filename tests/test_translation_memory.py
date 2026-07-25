"""
translation_memory.py için birim testler.

Kapsar:
- Tam eşleşme lookup / store
- Dil anahtarı izolasyonu (aynı kaynak, farklı hedef dil → farklı kayıt)
- [HATA]/[ÇEVİRİ EKSİK] içeren çeviriler kaydedilmez
- store_batch toplu kayıt
- session hit sayacı
"""
import tempfile
import unittest

from translation_memory import TranslationMemory


def _tmp_tm() -> TranslationMemory:
    """Her test için geçici dosyada taze TM döner."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return TranslationMemory(db_path=tmp.name)


class TMLookupTest(unittest.TestCase):
    def test_exact_match_returns_translation(self):
        tm = _tmp_tm()
        tm.store("Hello world", "Merhaba dünya", tgt_lang="Turkish")

        result = tm.lookup("Hello world", tgt_lang="Turkish")

        self.assertEqual(result, "Merhaba dünya")

    def test_missing_key_returns_none(self):
        tm = _tmp_tm()

        result = tm.lookup("Never stored", tgt_lang="Turkish")

        self.assertIsNone(result)

    def test_whitespace_normalization(self):
        tm = _tmp_tm()
        tm.store("  Hello   world  ", "Merhaba dünya", tgt_lang="Turkish")

        result = tm.lookup("Hello world", tgt_lang="Turkish")

        self.assertEqual(result, "Merhaba dünya")

    def test_case_insensitive_lookup(self):
        tm = _tmp_tm()
        tm.store("HELLO WORLD", "Merhaba dünya", tgt_lang="Turkish")

        result = tm.lookup("hello world", tgt_lang="Turkish")

        self.assertEqual(result, "Merhaba dünya")


class TMLanguageIsolationTest(unittest.TestCase):
    """Aynı kaynak metin farklı hedef dillerde ayrı kayıtlanmalı."""

    def test_different_target_languages_stored_separately(self):
        tm = _tmp_tm()
        tm.store("Good morning", "Günaydın", tgt_lang="Turkish")
        tm.store("Good morning", "Guten Morgen", tgt_lang="German")

        tr = tm.lookup("Good morning", tgt_lang="Turkish")
        de = tm.lookup("Good morning", tgt_lang="German")

        self.assertEqual(tr, "Günaydın")
        self.assertEqual(de, "Guten Morgen")
        self.assertNotEqual(tr, de)

    def test_lookup_without_lang_does_not_match_lang_keyed_entry(self):
        tm = _tmp_tm()
        tm.store("Good morning", "Günaydın", tgt_lang="Turkish")

        # Dil belirtilmeden lookup → farklı hash → miss
        result = tm.lookup("Good morning", tgt_lang="")

        self.assertIsNone(result)

    def test_fuzzy_lookup_isolated_by_target_language(self):
        tm = _tmp_tm()
        tm.store("This is a great day", "Bu harika bir gün", tgt_lang="Turkish")
        tm.store("This is a good day", "Das ist ein guter Tag", tgt_lang="German")

        # Querying fuzzy match for German should NOT return the Turkish one
        res = tm.fuzzy_lookup("This is a great day", tgt_lang="German")
        self.assertIsNone(res)

    def test_fuzzy_lookup_matches_correct_language(self):
        tm = _tmp_tm()
        tm.store("This is a great day", "Bu harika bir gün", tgt_lang="Turkish")
        tm.store("This is a good day", "Das ist ein guter Tag", tgt_lang="German")

        tr_res = tm.fuzzy_lookup("This is a great day!", tgt_lang="Turkish")
        de_res = tm.fuzzy_lookup("This is a good day!", tgt_lang="German")

        self.assertIsNotNone(tr_res)
        self.assertEqual(tr_res[0], "Bu harika bir gün")
        self.assertIsNotNone(de_res)
        self.assertEqual(de_res[0], "Das ist ein guter Tag")


class TMStoreTest(unittest.TestCase):
    def test_hata_entry_not_stored(self):
        tm = _tmp_tm()
        tm.store("Source line", "[HATA]", tgt_lang="Turkish")

        result = tm.lookup("Source line", tgt_lang="Turkish")

        self.assertIsNone(result)

    def test_missing_translation_marker_not_stored(self):
        tm = _tmp_tm()
        tm.store("Source line", "[ÇEVİRİ EKSİK]", tgt_lang="Turkish")

        result = tm.lookup("Source line", tgt_lang="Turkish")

        self.assertIsNone(result)

    def test_store_batch_inserts_all_pairs(self):
        tm = _tmp_tm()
        pairs = [("Line one", "Satır bir"), ("Line two", "Satır iki")]

        tm.store_batch(pairs, model="test-model", tgt_lang="Turkish")

        self.assertEqual(tm.lookup("Line one", tgt_lang="Turkish", model="test-model"), "Satır bir")
        self.assertEqual(tm.lookup("Line two", tgt_lang="Turkish", model="test-model"), "Satır iki")

    def test_store_batch_skips_hata(self):
        tm = _tmp_tm()
        pairs = [
            ("Good line", "İyi satır"),
            ("Bad line", "[HATA]"),
            ("Missing line", "[ÇEVİRİ EKSİK]"),
        ]

        tm.store_batch(pairs, tgt_lang="Turkish")

        self.assertEqual(tm.lookup("Good line", tgt_lang="Turkish"), "İyi satır")
        self.assertIsNone(tm.lookup("Bad line", tgt_lang="Turkish"))
        self.assertIsNone(tm.lookup("Missing line", tgt_lang="Turkish"))

    def test_stats_total_count(self):
        tm = _tmp_tm()
        tm.store_batch([("A", "x"), ("B", "y"), ("C", "z")], tgt_lang="Turkish")

        self.assertEqual(tm.stats()["total"], 3)


class TMSessionHitsTest(unittest.TestCase):
    def test_record_hit_increments_counter(self):
        tm = _tmp_tm()

        tm.record_hit()
        tm.record_hit()

        self.assertEqual(tm.hit_count_session(), 2)

    def test_reset_session_hits(self):
        tm = _tmp_tm()
        tm.record_hit()
        tm.record_hit()

        tm.reset_session_hits()

        self.assertEqual(tm.hit_count_session(), 0)


class TMSchemaLegacyFallbackIsolationTest(unittest.TestCase):
    def test_legacy_unschematized_record_does_not_leak_to_schematized_queries(self):
        """Un-schematized legacy TM record must NOT bleed into queries with non-empty schema_name."""
        tm = _tmp_tm()
        # Create un-schematized legacy record (schema_name="")
        tm.store("Same source text", "LEGACY", tgt_lang="Turkish", model="gpt-4o", schema_name="")

        # Query with schema_name="anime" and "frp" (Exact, Batch, Fuzzy)
        self.assertIsNone(tm.lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name="anime"))
        self.assertIsNone(tm.lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name="frp"))

        batch_anime = tm.lookup_batch(["Same source text"], tgt_lang="Turkish", model="gpt-4o", schema_name="anime")
        batch_frp = tm.lookup_batch(["Same source text"], tgt_lang="Turkish", model="gpt-4o", schema_name="frp")
        self.assertEqual(batch_anime, {})
        self.assertEqual(batch_frp, {})

        fuzzy_anime = tm.fuzzy_lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name="anime")
        fuzzy_frp = tm.fuzzy_lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name="frp")
        self.assertIsNone(fuzzy_anime)
        self.assertIsNone(fuzzy_frp)

        # Un-schematized query (schema_name="") MUST find the legacy record
        self.assertEqual(tm.lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name=""), "LEGACY")
        batch_legacy = tm.lookup_batch(["Same source text"], tgt_lang="Turkish", model="gpt-4o", schema_name="")
        self.assertEqual(batch_legacy.get("Same source text"), "LEGACY")
        fuzzy_legacy = tm.fuzzy_lookup("Same source text", tgt_lang="Turkish", model="gpt-4o", schema_name="")
        self.assertIsNotNone(fuzzy_legacy)
        self.assertEqual(fuzzy_legacy[0], "LEGACY")


if __name__ == "__main__":
    unittest.main()
