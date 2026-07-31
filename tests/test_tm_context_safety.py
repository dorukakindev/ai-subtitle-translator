import tempfile
import unittest
from pathlib import Path

from translation_memory import TranslationMemory


class TranslationMemoryContextSafetyTest(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.tm = TranslationMemory(Path(self._tempdir.name) / "tm.db")
        self.settings = {
            "model": "test-model",
            "tgt_lang": "tr",
            "profanity": "orta",
            "schema_name": "drama",
            "source_language": "English",
        }

    def tearDown(self):
        self.tm.close()
        self._tempdir.cleanup()

    def test_contextless_records_are_not_final_substitutions(self):
        self.tm.store("Come in.", "İçeri gel.", **self.settings)

        self.assertEqual(self.tm.lookup("Come in.", **self.settings), "İçeri gel.")
        self.assertEqual(self.tm.lookup_batch(
            ["Come in."], allow_contextless_final=False, **self.settings), {})
        self.assertIsNone(self.tm.fuzzy_lookup(
            "Come in!", threshold=0.95,
            allow_contextless_final=False, **self.settings))

    def test_final_substitution_requires_matching_context_fingerprint(self):
        context = "register=siz|glossary=doctor-doktor|series=show-s01e02"
        self.tm.store(
            "Come in.", "İçeri gelin.",
            context_fingerprint=context, **self.settings)

        self.assertEqual(
            self.tm.lookup_batch(
                ["Come in."], context_fingerprint=context, **self.settings),
            {"Come in.": "İçeri gelin."},
        )
        self.assertEqual(
            self.tm.lookup_batch(
                ["Come in."], context_fingerprint="register=sen", **self.settings),
            {},
        )

    def test_fuzzy_rejects_content_tense_and_person_drift(self):
        context = "stable-scene"
        self.tm.store(
            "We filmed the gear at the river throughout the long summer afternoon.",
            "Nehirde bütün uzun yaz öğleden sonrası dişliyi filme aldık.",
            context_fingerprint=context, **self.settings)
        self.tm.store(
            "I carry the blue case through the empty hall.",
            "Mavi çantayı boş koridordan taşıyorum.",
            context_fingerprint=context, **self.settings)
        self.tm.store(
            "We carry the blue case through the empty hall.",
            "Mavi çantayı boş koridordan taşıyoruz.",
            context_fingerprint=context, **self.settings)

        self.assertIsNone(self.tm.fuzzy_lookup(
            "We filmed the bear at the river throughout the long summer afternoon.",
            threshold=0.95, context_fingerprint=context, **self.settings))
        self.assertIsNone(self.tm.fuzzy_lookup(
            "I carried the blue case through the empty hall.",
            threshold=0.95, context_fingerprint=context, **self.settings))
        self.assertIsNone(self.tm.fuzzy_lookup(
            "They carry the blue case through the empty hall.",
            threshold=0.95, context_fingerprint=context, **self.settings))
        self.assertIsNotNone(self.tm.fuzzy_lookup(
            "I carry the blue case through the empty hall!",
            threshold=0.95, context_fingerprint=context, **self.settings))


if __name__ == "__main__":
    unittest.main()
