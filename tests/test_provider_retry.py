import unittest
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import provider_retry
import subtitle_translator_gui as gui


def _client(url="https://api.shuaiapi.com/v1", key="sk-reseller"):
    return SimpleNamespace(base_url=url, api_key=key)


class RetryAfterParsingTest(unittest.TestCase):
    def test_retry_after_header_seconds(self):
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after": "17"}),
        )
        self.assertEqual(provider_retry.retry_after_seconds(exc), 17.0)

    def test_retry_after_milliseconds_header(self):
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after-ms": "1250"}),
        )
        self.assertEqual(provider_retry.retry_after_seconds(exc), 1.25)

    def test_google_retry_info_delay_from_body(self):
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={}),
            body={
                "error": {
                    "details": [{
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "3.5s",
                    }]
                }
            },
        )
        self.assertEqual(provider_retry.retry_after_seconds(exc), 3.5)

    def test_reseller_try_again_message(self):
        exc = RuntimeError("HTTP 429: quota exceeded; try again in 12.5 seconds")
        self.assertEqual(provider_retry.retry_after_seconds(exc), 12.5)


class ProviderCooldownRegistryTest(unittest.TestCase):
    def test_same_reseller_key_shares_cooldown_and_staggers_waiters(self):
        now = [100.0]
        sleeps = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=sleeps.append,
            retry_spacing=0.25,
        )
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after": "10"}),
        )
        client = _client()

        self.assertEqual(registry.record_rate_limit(client, exc), 10.0)
        self.assertEqual(registry.before_request(client), 10.0)
        self.assertEqual(registry.before_request(client), 10.25)
        self.assertEqual(sleeps, [10.0, 10.25])

    def test_different_api_keys_do_not_share_cooldown(self):
        now = [100.0]
        sleeps = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=sleeps.append,
        )
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after": "8"}),
        )
        registry.record_rate_limit(_client(key="key-a"), exc)

        self.assertEqual(registry.before_request(_client(key="key-b")), 0.0)
        self.assertEqual(sleeps, [])

    def test_non_rate_limit_error_does_not_start_cooldown(self):
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: 100.0,
            sleeper=lambda _delay: None,
        )
        exc = SimpleNamespace(
            status_code=500,
            response=SimpleNamespace(headers={"retry-after": "30"}),
        )
        self.assertIsNone(registry.record_rate_limit(_client(), exc))
        self.assertEqual(registry.before_request(_client()), 0.0)


class SafeChatCooldownIntegrationTest(unittest.TestCase):
    def _assert_wrapper_records_429(self, fn):
        client = mock.MagicMock()
        client.base_url = "https://api.shuaiapi.com/v1"
        client.api_key = "sk-reseller"
        error = RuntimeError("HTTP 429 rate limit")
        client.chat.completions.create.side_effect = error
        with (
            mock.patch("provider_retry.before_provider_request") as before,
            mock.patch("provider_retry.record_provider_failure") as record,
        ):
            with self.assertRaises(RuntimeError):
                fn(client, model="gpt-5.4", messages=[])
        before.assert_called_once_with(client)
        record.assert_called_once_with(client, error)

    def test_hybrid_wrapper_records_reseller_429(self):
        self._assert_wrapper_records_429(ht._safe_chat_create)

    def test_gui_wrapper_records_reseller_429(self):
        self._assert_wrapper_records_429(gui._safe_chat_create)


if __name__ == "__main__":
    unittest.main()
