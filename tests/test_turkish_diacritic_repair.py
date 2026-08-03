import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


_TS = "00:00:01,000 --> 00:00:02,000"


class TurkishDiacriticRepairValidationTests(unittest.TestCase):
    def test_accepts_only_ascii_equivalent_diacritic_gain(self):
        self.assertEqual(
            ht.validate_turkish_diacritic_repair(
                "Bugun hava cok guzel.", "Bugün hava çok güzel."),
            (True, ""),
        )

    def test_rejects_punctuation_or_content_change(self):
        ok, reason = ht.validate_turkish_diacritic_repair(
            "Bugun hava cok guzel.", "Bugün hava çok güzel!")
        self.assertFalse(ok)
        self.assertEqual(reason, "content_changed")

    def test_rejects_linebreak_or_tag_change(self):
        self.assertEqual(
            ht.validate_turkish_diacritic_repair(
                "<i>Bugun\ncok guzel.</i>", "<i>Bugün çok güzel.</i>"),
            (False, "linebreak_count"),
        )
        self.assertEqual(
            ht.validate_turkish_diacritic_repair(
                "<i>Bugun cok guzel.</i>", "Bugün çok güzel."),
            (False, "format_tags"),
        )


class TurkishDiacriticRepairPassTests(unittest.TestCase):
    def test_applies_safe_repairs_and_rejects_semantic_edits(self):
        blocks = [
            ("1", _TS, "Bugun hava cok guzel."),
            ("2", _TS, "Bu satir aynen kalacak."),
        ]
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=(
                '[{"id":"99","text":"Bugün hava çok güzel."},'
                '{"id":"98","text":"Bu satır kesinlikle değişecek."}]'
            )))],
        )
        status = {}
        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", return_value=response):
            result, changed = ht.repair_turkish_ascii_diacritics(
                {"1": "The weather is very nice today.",
                 "2": "This line will remain unchanged."},
                blocks, api_key="x", status_out=status)

        self.assertEqual(changed, 1)
        self.assertEqual(result[0][2], "Bugün hava çok güzel.")
        self.assertEqual(result[1][2], "Bu satir aynen kalacak.")
        self.assertEqual(status["status"], "completed")

    def test_removes_circumflex_from_candidate(self):
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"id":"1","text":"Hâlâ çok güzel."}]'))],
        )
        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", return_value=response):
            result, changed = ht.repair_turkish_ascii_diacritics(
                {"1": "It is still very nice."},
                [("1", _TS, "Hala cok guzel.")], api_key="x")

        self.assertEqual(changed, 1)
        self.assertEqual(result[0][2], "Hala çok güzel.")


if __name__ == "__main__":
    unittest.main()
