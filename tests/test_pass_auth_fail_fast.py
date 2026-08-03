import unittest
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class AuthError(RuntimeError):
    status_code = 401


class PassAuthFailFastTest(unittest.TestCase):
    def test_backtranslation_stops_after_first_auth_error(self):
        blocks = [
            (idx, f"00:00:{idx:02d},000 --> 00:00:{idx:02d},900", "Yeterince uzun Türkçe satır.")
            for idx in range(1, 4)
        ]
        src_map = {str(idx): "A sufficiently long source line." for idx in range(1, 4)}
        status = {}

        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create",
                side_effect=AuthError("invalid_api_key")) as create:
            result = ht.back_translation_check(
                src_map, blocks, api_key="bad", chunk_size=1,
                status_out=status)

        self.assertEqual(result, [])
        self.assertEqual(create.call_count, 1)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 3)
        self.assertIn("invalid_api_key", status["error"])

    def test_polish_stops_after_first_auth_error_without_retry(self):
        app = gui.App.__new__(gui.App)
        app._log = MagicMock()
        app._log_exc = MagicMock()
        app._update_tokens = MagicMock()
        blocks = [
            (idx, f"00:00:{idx % 60:02d},000 --> 00:00:{idx % 60:02d},900", "Doğal bir Türkçe satır.")
            for idx in range(1, 152)
        ]
        status = {}

        with patch("openai.OpenAI"), patch(
                "subtitle_translator_gui._safe_chat_create",
                side_effect=AuthError("invalid_api_key")) as create:
            result = app._polish_pass(
                blocks, "Turkish", "bad", "https://api.openai.com/v1",
                "gpt-5.4-mini", status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(create.call_count, 1)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 2)
        self.assertIn("invalid_api_key", status["error"])


if __name__ == "__main__":
    unittest.main()
