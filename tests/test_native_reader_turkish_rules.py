import unittest
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class NativeReaderTurkishRulesTest(unittest.TestCase):
    def test_rules_are_turkish_only_and_include_subtitle_guards(self):
        rules = ht.native_reader_style_rules("Türkçe")
        self.assertIn("Kaynak cümlenin kelime sırasını yamama", rules)
        self.assertIn("açık kazanım yoksa aynen bırak", rules)
        self.assertIn("konuşmacı veya sahne sınırını asla geçme", rules)
        self.assertEqual(ht.native_reader_style_rules("German"), "")

    def test_native_prompt_injects_rules_for_turkish_but_not_german(self):
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))])
        blocks = [("1", "00:00:00,000 --> 00:00:01,000", "Bu doğal bir cümle.")]
        for language, expected in (("Turkish", True), ("German", False)):
            with self.subTest(language=language), \
                    patch("openai.OpenAI", return_value=object()), \
                    patch("hybrid_translate._safe_chat_create", return_value=response) as safe:
                ht.native_reader_pass(blocks, "key", tgt_lang=language)
                prompt = safe.call_args.kwargs["messages"][0]["content"]
                self.assertEqual("DOĞAL TÜRKÇE KONTROLÜ" in prompt, expected)

    def test_verifier_requires_fidelity_in_addition_to_source_free_test(self):
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"id":"1","accept":false}]'))])
        candidate = {
            "id": "1", "source": "I saw him.", "before": "Onu gördüm.",
            "after": "Gördüm onu.", "context_before": [], "context_after": []}
        with patch("hybrid_translate._safe_chat_create", return_value=response) as safe:
            accepted = ht._verify_native_candidates(object(), "model", [candidate])
        self.assertEqual(accepted, set())
        prompt = safe.call_args.kwargs["messages"][0]["content"]
        self.assertIn("bu test tek başına değişiklik gerekçesi değildir", prompt)
        self.assertIn("anlam ve açık doğallık kazanımı", prompt)


if __name__ == "__main__":
    unittest.main()
