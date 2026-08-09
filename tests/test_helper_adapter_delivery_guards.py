"""Direct provider adapter regressions: URL, cancellation and usage telemetry."""
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import helper_models as helpers


class _Cancelled:
    def raise_if_cancelled(self):
        raise RuntimeError("cancelled")


class AnthropicAdapterDeliveryGuardTest(unittest.TestCase):
    def _response(self, payload):
        class Response:
            def read(self):
                return json.dumps(payload).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False
        return Response()

    def test_root_urls_normalize_to_exact_messages_endpoint(self):
        self.assertEqual(helpers._anthropic_messages_url("https://api.anthropic.com"),
                         "https://api.anthropic.com/v1/messages")
        self.assertEqual(helpers._anthropic_messages_url("https://api.anthropic.com/v1"),
                         "https://api.anthropic.com/v1/messages")
        self.assertEqual(helpers._anthropic_messages_url("https://proxy.test/v1/messages/"),
                         "https://proxy.test/v1/messages")

    def test_anthropic_missing_usage_is_explicit_not_fake_zero_usage(self):
        with patch("urllib.request.urlopen", return_value=self._response({
                "content": [{"type": "text", "text": "ok"}]})):
            response = helpers.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}],
                base_url="https://api.anthropic.com/v1")
        self.assertFalse(response.usage_available)
        self.assertTrue(response.usage.missing)
        self.assertEqual(response.usage.total_tokens, 0)

    def test_cancelled_anthropic_request_never_opens_network(self):
        with patch("urllib.request.urlopen") as urlopen:
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                helpers.call_anthropic_messages(
                    "claude", [{"role": "user", "content": "x"}],
                    cancel_context=_Cancelled())
        urlopen.assert_not_called()

    def test_timeout_is_forwarded_to_anthropic_transport(self):
        captured = {}

        def urlopen(_request, timeout=None):
            captured["timeout"] = timeout
            return self._response({
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            })

        with patch("urllib.request.urlopen", side_effect=urlopen):
            helpers.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}], timeout_seconds=17)
        self.assertEqual(captured["timeout"], 17.0)

    def test_malformed_usage_is_reported_missing_without_breaking_response(self):
        with patch("urllib.request.urlopen", return_value=self._response({
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": "not-a-number", "output_tokens": "2"},
        })):
            response = helpers.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}],
                base_url="https://api.anthropic.com/v1")
        self.assertFalse(response.usage_available)
        self.assertTrue(response.usage.missing)
        self.assertEqual(response.usage.total_tokens, 0)

    def test_numeric_string_usage_is_normalized_to_integers(self):
        with patch("urllib.request.urlopen", return_value=self._response({
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": "3", "output_tokens": "2"},
        })):
            response = helpers.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}],
                base_url="https://api.anthropic.com/v1")
        self.assertTrue(response.usage_available)
        self.assertEqual(response.usage.total_tokens, 5)
        self.assertIsInstance(response.usage.prompt_tokens, int)


class BedrockAdapterUsageGuardTest(unittest.TestCase):
    def test_bedrock_missing_usage_is_explicit(self):
        boto3 = MagicMock()
        client = MagicMock()
        boto3.Session.return_value.client.return_value = client
        client.converse.return_value = {
            "output": {"message": {"content": [{"text": "ok"}]}},
        }
        with patch.dict("sys.modules", {"boto3": boto3}):
            response = helpers.call_bedrock_converse(
                "model", [{"role": "user", "content": "x"}])
        self.assertFalse(response.usage_available)
        self.assertTrue(response.usage.missing)

    def test_bedrock_checks_cancellation_before_client_creation(self):
        boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": boto3}):
            with self.assertRaisesRegex(RuntimeError, "cancelled"):
                helpers.call_bedrock_converse(
                    "model", [{"role": "user", "content": "x"}],
                    cancel_context=_Cancelled())
        boto3.Session.assert_not_called()

    def test_bedrock_registers_live_client_for_transport_cancellation(self):
        from request_cancellation import RunRequestCanceller, RequestCancelled

        boto3 = MagicMock()
        client = MagicMock()
        boto3.Session.return_value.client.return_value = client
        started = threading.Event()
        release = threading.Event()
        canceller = RunRequestCanceller()
        errors = []

        def converse(**_kwargs):
            started.set()
            release.wait(1)
            raise RuntimeError("closed")

        client.converse.side_effect = converse
        client.close.side_effect = release.set

        def worker():
            try:
                helpers.call_bedrock_converse(
                    "model", [{"role": "user", "content": "x"}],
                    cancel_context=canceller)
            except Exception as exc:
                errors.append(exc)

        with patch.dict("sys.modules", {"boto3": boto3}):
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(started.wait(1))
            self.assertEqual(canceller.cancel(), 1)
            thread.join(1)

        self.assertFalse(thread.is_alive())
        client.close.assert_called_once_with()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertIn("closed", str(errors[0]))


if __name__ == "__main__":
    unittest.main()
