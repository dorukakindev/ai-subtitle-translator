import io
import unittest
from types import SimpleNamespace
from unittest import mock
from urllib.error import HTTPError

import helper_models
import hybrid_translate
import provider_retry
import subtitle_translator_gui


class DirectProviderRetryRegressionTest(unittest.TestCase):
    def _assert_direct_retry(self, wrapper):
        client = SimpleNamespace(
            base_url="https://proxy.example/v1/messages",
            api_key="test-key",
        )
        error = helper_models.ProviderAdapterError(
            "temporary", status_code=429, headers={"Retry-After": "17"})
        with mock.patch(
                "helper_models.call_anthropic_messages",
                side_effect=[error, "ok"]) as call, mock.patch(
                "provider_retry._wait_for_transient_retry",
                return_value=30.0) as wait, mock.patch(
                "provider_retry.record_provider_failure",
                return_value=None):
            result = wrapper(
                client, model="custom-claude", messages=[], timeout=9)
        self.assertEqual(result, "ok")
        self.assertEqual(call.call_count, 2)
        wait.assert_called_once_with(error, 1, 3)

    def test_hybrid_direct_anthropic_retries_transient_failure(self):
        self._assert_direct_retry(hybrid_translate._safe_chat_create)

    def test_gui_direct_anthropic_retries_transient_failure(self):
        self._assert_direct_retry(subtitle_translator_gui._safe_chat_create)


class ProviderAdapterErrorRegressionTest(unittest.TestCase):
    def test_anthropic_http_error_preserves_retry_after_and_redacts_key(self):
        key = "test-secret-provider-key"
        error = HTTPError(
            "https://api.anthropic.com/v1/messages",
            429,
            "rate limited",
            {"Retry-After": "17"},
            io.BytesIO(f'{{"error":"echo {key}"}}'.encode()),
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(helper_models.ProviderAdapterError) as caught:
                helper_models.call_anthropic_messages(
                    "claude", [{"role": "user", "content": "x"}],
                    api_key_str=key,
                    base_url="https://api.anthropic.com/v1",
                )
        error.close()
        exc = caught.exception
        self.assertEqual(exc.status_code, 429)
        self.assertEqual(exc.headers.get("Retry-After"), "17")
        self.assertNotIn(key, str(exc))
        self.assertNotIn(key, str(exc.body))
        self.assertEqual(provider_retry.retry_after_seconds(exc), 17.0)

    def test_bedrock_error_preserves_response_metadata_and_redacts_credentials(self):
        access = "TESTACCESS123"
        secret = "testSecret456"
        original = RuntimeError(f"failed for {access} and {secret}")
        original.response = {
            "ResponseMetadata": {
                "HTTPStatusCode": 503,
                "HTTPHeaders": {"retry-after": "22"},
            },
            "Error": {"Code": "ServiceUnavailableException"},
        }
        exc = helper_models._provider_adapter_error(
            "AWS Bedrock", original,
            api_key_str=f"{access}:{secret}:eu-west-1")
        self.assertEqual(exc.status_code, 503)
        self.assertEqual(exc.headers.get("retry-after"), "22")
        self.assertNotIn(access, str(exc))
        self.assertNotIn(secret, str(exc))
        self.assertTrue(provider_retry._is_transient_provider_error(exc))


class MissingUsageRegressionTest(unittest.TestCase):
    def test_gui_usage_reporter_does_not_count_adapter_placeholder_as_real_usage(self):
        callback = mock.MagicMock()
        callback.report_missing_usage = mock.MagicMock()
        response = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=0),
            usage_available=False,
        )
        self.assertFalse(subtitle_translator_gui._report_response_usage(
            callback, response))
        callback.assert_not_called()
        callback.report_missing_usage.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
