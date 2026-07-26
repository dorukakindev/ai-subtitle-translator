import json
import unittest

from response_integrity import parse_translation_payload, translation_items_from_raw


class TranslationItemsTest(unittest.TestCase):
    def test_balanced_extraction_ignores_brackets_inside_string(self):
        raw = 'preamble [{"i":1,"t":"[kapı] açıldı"},{"i":2,"t":"tamam"}] suffix'
        items, mode = translation_items_from_raw(raw)
        self.assertEqual(mode, "array")
        self.assertEqual(items[0]["t"], "[kapı] açıldı")

    def test_accepts_tr_envelope_but_returns_only_items(self):
        items, mode = translation_items_from_raw(
            '{"tr":[{"i":"1","t":"Merhaba"}],"meta":{"x":1}}')
        self.assertEqual(mode, "envelope")
        self.assertEqual(items, [{"i": "1", "t": "Merhaba"}])

    def test_salvages_complete_prefix_objects(self):
        items, mode = translation_items_from_raw(
            '[{"i":1,"t":"A"},{"i":2,"t":"B"},{"i":3,"t":')
        self.assertEqual(mode, "salvaged")
        self.assertEqual([item["i"] for item in items], [1, 2])


class ParseTranslationPayloadTest(unittest.TestCase):
    def test_duplicate_id_is_fatal_and_not_last_write_wins(self):
        parsed = parse_translation_payload(
            '[{"i":1,"t":"ilk"},{"i":1,"t":"ikinci"}]', {"1"})
        self.assertEqual(parsed.duplicate_ids, {"1"})
        self.assertNotIn("1", parsed.translations)
        self.assertEqual(parsed.fatal_reason, "duplicate_id")

    def test_unexpected_id_is_rejected(self):
        parsed = parse_translation_payload(
            '[{"i":1,"t":"A"},{"i":99,"t":"B"}]', {"1", "2"})
        self.assertEqual(parsed.translations, {"1": "A"})
        self.assertEqual(parsed.unexpected_ids, {"99"})
        self.assertEqual(parsed.missing_ids, {"2"})

    def test_non_string_translation_is_rejected(self):
        parsed = parse_translation_payload(
            json.dumps([{"i": 1, "t": {"text": "A"}}]), {"1"})
        self.assertEqual(parsed.translations, {})
        self.assertEqual(parsed.invalid_text_ids, {"1"})
        self.assertEqual(parsed.missing_ids, {"1"})

    def test_missing_ids_are_explicit(self):
        parsed = parse_translation_payload('[{"i":1,"t":"A"}]', {"1", "2"})
        self.assertEqual(parsed.translations, {"1": "A"})
        self.assertEqual(parsed.missing_ids, {"2"})


if __name__ == "__main__":
    unittest.main()
