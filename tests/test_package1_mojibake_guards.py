import unittest
import hybrid_translate as ht

class DummyContextMemory:
    def __getattr__(self, name):
        return None

class TestPackage1MojibakeGuards(unittest.TestCase):
    def test_script_guard_and_native_reader_prompt_runtime_text(self):
        """Prompt outputs contain clean Unicode script characters and natural Turkish."""
        context = DummyContextMemory()
        prompt = ht.build_system_prompt(context=context, src_lang="English", tgt_lang="Turkish")
        self.assertIn("NEVER output Arabic (ع،ح)", prompt)
        self.assertIn("Tamil (கோயில்)", prompt)
        self.assertIn("Devanagari (देव)", prompt)
        self.assertIn("Cyrillic (текст)", prompt)
        self.assertNotIn("Ø¹ØŒØ­", prompt)

    def test_mekisi_caught_as_model_corruption(self):
        """mekişi and MEKİŞİ are caught by _POLISH_MODEL_CORRUPTION_RE."""
        self.assertTrue(bool(ht._POLISH_MODEL_CORRUPTION_RE.search("Bu mekişi tamamen bozuk.")))
        self.assertTrue(bool(ht._POLISH_MODEL_CORRUPTION_RE.search("MEKİŞİ son kelime")))
        self.assertTrue(bool(ht._POLISH_MODEL_CORRUPTION_RE.search("İyeleri listesi")))
        self.assertFalse(bool(ht._POLISH_MODEL_CORRUPTION_RE.search("normal Türkçe kelime")))

    def test_local_fixes_graal_and_bible(self):
        """Graal şatosu and Bible possessive suffixes produce correct local fixes."""
        fixed_graal, _ = ht._apply_local_fixes("De Heilige Graal şatosu çok eski.")
        self.assertIn("Kutsal Kâse Şatosu", fixed_graal)

        fixed_bible, _ = ht._apply_local_fixes("Bible'ın içinde geçiyor.")
        self.assertIn("Kutsal Kitap'ın", fixed_bible)

    def test_quote_punctuation_stripping(self):
        """curly quotes and angle quotes are stripped correctly at text ends."""
        # _ellipsis_continues
        self.assertTrue(ht._ellipsis_continues("Düşünüyordum...”", "...sonra geldiler"))

        # _looks_like_early_turkish_verb_closure
        self.assertTrue(ht._looks_like_early_turkish_verb_closure("Evlerine geldiler»"))

        # has_non_turkish_target_leak
        leak = ht.has_non_turkish_target_leak("“Buñuel”", glossary_target=True)
        self.assertFalse(leak)

    def test_causative_want_backslide_preserved(self):
        """_has_causative_want_backslide preserves existing correct behavior."""
        self.assertNotIn("Ã", ht._POLISH_CAUSATIVE_WANT_RE.pattern)
        self.assertTrue(ht._has_causative_want_backslide("gitmek istetmek", "gitmek istiyor"))
        self.assertTrue(ht._has_causative_want_backslide("görmek istetmek", "görmek istiyor"))
        self.assertTrue(ht._has_causative_want_backslide("düşünmek istetmek", "düşünmek istiyor"))
        self.assertFalse(ht._has_causative_want_backslide("gitmek istiyor", "gitmek istiyor"))


if __name__ == "__main__":
    unittest.main()
