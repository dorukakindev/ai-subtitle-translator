import ast
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui
from request_cancellation import RequestCancelled


class _CancelContext:
    def __init__(self, cancelled=False):
        self.cancelled = cancelled

    def is_cancelled(self):
        return self.cancelled


class HelperRequestCancellationTest(unittest.TestCase):
    def test_term_normalization_reports_usage(self):
        callback = MagicMock()
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps([
                {"id": "1", "tr": "Truva geldi."},
            ])))],
            usage=SimpleNamespace(
                total_tokens=31,
                prompt_tokens_details=SimpleNamespace(cached_tokens=8),
            ),
        )
        with patch.object(gui, "_mixed_term_autofix_plan", return_value={
                "1": [("Troy", "Truva")]}), patch(
                "openai.OpenAI", return_value=SimpleNamespace()), patch.object(
                gui, "_safe_chat_create", return_value=response):
            result, changed = gui._normalize_mixed_terms(
                [("1", "ts", "Troy geldi.")], {"1": "Troy came."},
                "key", "url", "model", token_callback=callback)

        self.assertEqual(changed, 1)
        self.assertEqual(result[0][2], "Truva geldi.")
        callback.assert_called_once_with(31, cached=8)

    def test_term_normalization_stops_on_request_cancellation(self):
        status = {}
        context = _CancelContext()
        with patch.object(gui, "_mixed_term_autofix_plan", return_value={
                "1": [("Troy", "Truva")]}), patch(
                "openai.OpenAI", return_value=SimpleNamespace()), patch.object(
                gui, "_safe_chat_create", side_effect=RequestCancelled("stop")) as call:
            result, changed = gui._normalize_mixed_terms(
                [("1", "ts", "Troy geldi.")], {"1": "Troy came."},
                "key", "url", "model", cancel_context=context,
                status_out=status)

        self.assertEqual(result[0][2], "Troy geldi.")
        self.assertEqual(changed, 0)
        self.assertEqual(status["status"], "cancelled")
        self.assertEqual(call.call_count, 1)
        self.assertIs(call.call_args.kwargs["cancel_context"], context)

    def test_repair_forwards_request_canceller(self):
        context = _CancelContext()
        with patch.object(
                gui, "_safe_chat_create",
                side_effect=RequestCancelled("stop")) as call:
            result, changed = gui._repair_untranslated_sync(
                [("1", "ts", "[HATA]")], {"1": "Hello."},
                SimpleNamespace(), "English", "Turkish",
                cancel_context=context)

        self.assertEqual(result[0][2], "[HATA]")
        self.assertEqual(changed, 0)
        self.assertIs(call.call_args.kwargs["cancel_context"], context)

    def test_precontext_propagates_request_cancellation(self):
        context = _CancelContext()
        with patch.object(
                ht, "_safe_chat_create",
                side_effect=RequestCancelled("stop")) as call:
            with self.assertRaises(RequestCancelled):
                gui.analyze_file_precontext(
                    SimpleNamespace(), [("1", "ts", "Hello")],
                    "model", "English", "Turkish",
                    cancel_context=context)
        self.assertIs(call.call_args.kwargs["cancel_context"], context)

    def test_detection_propagates_request_cancellation(self):
        context = _CancelContext()
        with patch.object(
                ht, "_safe_chat_create",
                side_effect=RequestCancelled("stop")):
            with self.assertRaises(RequestCancelled):
                gui.detect_content_type_with_ai(
                    SimpleNamespace(), [("1", "ts", "Hello")], "model",
                    cancel_context=context)
        with patch.object(
                gui, "_safe_chat_create",
                side_effect=RequestCancelled("stop")):
            with self.assertRaises(RequestCancelled):
                gui.detect_source_language_with_ai(
                    SimpleNamespace(), [("1", "ts", "Hello")], "model",
                    cancel_context=context)

    def test_all_app_helper_calls_forward_cancellation(self):
        tree = ast.parse(inspect.getsource(gui.App))
        names = {
            "_repair_untranslated_sync",
            "_normalize_mixed_terms",
            "detect_content_type_with_ai",
            "detect_source_language_with_ai",
            "analyze_file_precontext",
        }
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
        ]
        self.assertGreater(len(calls), 0)
        for call in calls:
            keywords = {keyword.arg for keyword in call.keywords}
            self.assertIn("cancel_context", keywords, call.func.id)
            if call.func.id == "_normalize_mixed_terms":
                self.assertIn("token_callback", keywords)


if __name__ == "__main__":
    unittest.main()
