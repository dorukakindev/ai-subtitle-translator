import json
import unittest
from types import SimpleNamespace
from unittest import mock

import subtitle_translator_gui as gui
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

    def test_missing_block_recovery_rejects_truncated_response(self):
        req = {
            "custom_id": "chunk-1",
            "body": {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": json.dumps({
                        "tr": [{"i": "1", "t": "One"}, {"i": "2", "t": "Two"}]
                    })},
                ],
            },
        }
        partial = json.dumps([
            {"i": "1", "t": "Bir"},
            {"i": "2", "t": "İki"},
        ])
        stub = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *_args: None,
            _update_tokens=lambda *_args, **_kwargs: None,
        )
        with mock.patch.object(
                gui, "_safe_chat_create",
                return_value=_response(partial, finish_reason="length")):
            merged = gui.App._resend_missing_blocks(
                stub, object(), req, "", max_sub=20)
        self.assertEqual(
            [item["t"] for item in json.loads(merged)],
            ["[HATA]", "[HATA]"],
        )

    def test_retry_reports_real_final_unresolved_set(self):
        req = {
            "custom_id": "chunk-1",
            "body": {
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": json.dumps({
                        "tr": [{"i": "1", "t": "Hello"}]
                    })},
                ],
            },
        }
        stub = SimpleNamespace(
            _stop_flag=False,
            _json_repair_pass=lambda *_args: None,
            _resend_missing_blocks=lambda *_args, **_kwargs: None,
            _log=lambda *_args: None,
        )
        valid = {"chunk-1": json.dumps([{"i": "1", "t": "Merhaba"}])}
        self.assertEqual(
            gui.App._retry_hata(stub, object(), valid, [req], max_rounds=0),
            set(),
        )
        unresolved = {
            "chunk-1": json.dumps([
                {"i": "1", "t": "[HATA_NON_TURKISH_TARGET]"}
            ])
        }
        self.assertEqual(
            gui.App._retry_hata(
                stub, object(), unresolved, [req], max_rounds=0),
            {"chunk-1"},
        )


if __name__ == "__main__":
    unittest.main()
