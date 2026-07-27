import unittest
from types import SimpleNamespace

from subtitle_translator_gui import _validated_chat_content


def _response(content="ok", finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ]
    )


class ValidatedChatContentTests(unittest.TestCase):
    def test_accepts_clean_openai_response(self):
        self.assertEqual(_validated_chat_content(_response("  tamam  ")), "tamam")

    def test_accepts_missing_reason_for_compatible_resellers(self):
        self.assertEqual(_validated_chat_content(_response(finish_reason=None)), "ok")

    def test_accepts_anthropic_and_completed_reason_aliases(self):
        self.assertEqual(_validated_chat_content(_response(finish_reason="end_turn")), "ok")
        self.assertEqual(_validated_chat_content(_response(finish_reason="completed")), "ok")

    def test_rejects_truncated_or_filtered_response(self):
        for reason in ("length", "max_tokens", "content_filter", "refusal"):
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(RuntimeError, reason):
                    _validated_chat_content(_response(finish_reason=reason))

    def test_rejects_empty_choices_and_content(self):
        with self.assertRaisesRegex(RuntimeError, "empty choices"):
            _validated_chat_content(SimpleNamespace(choices=[]))
        with self.assertRaisesRegex(RuntimeError, "empty content"):
            _validated_chat_content(_response(content="  "))

    def test_accepts_dictionary_shaped_compatible_response(self):
        response = {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": " sözlük "},
            }]
        }
        self.assertEqual(_validated_chat_content(response), "sözlük")


if __name__ == "__main__":
    unittest.main()
