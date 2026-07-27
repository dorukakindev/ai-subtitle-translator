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
        def sleep(delay):
            sleeps.append(delay)
            now[0] += delay
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=sleep,
            retry_spacing=0.25,
        )
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after": "10"}),
        )
        client = _client()

        self.assertEqual(registry.record_rate_limit(client, exc), 10.0)
        self.assertEqual(registry.before_request(client), 10.0)
        self.assertAlmostEqual(registry.before_request(client), 0.25)
        self.assertAlmostEqual(sum(sleeps), 10.25)

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

    def test_wait_can_be_cancelled(self):
        now = [100.0]
        events = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
            cancel_check=lambda: True,
            wait_callback=lambda *args: events.append(args),
        )
        exc = SimpleNamespace(
            status_code=429,
            response=SimpleNamespace(headers={"retry-after": "30"}),
        )
        registry.record_rate_limit(_client(), exc)
        with self.assertRaises(provider_retry.ProviderWaitCancelled):
            registry.before_request(_client())
        self.assertEqual(events[0][0], "start")
        self.assertEqual(events[-1], ("end", 0, 0))


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


class ResellerStructuredOutputTest(unittest.TestCase):
    def _client(self, suffix):
        client = mock.MagicMock()
        client.base_url = f"https://reseller-{suffix}.example/v1"
        client.api_key = "sk-test"
        return client

    def test_translation_payload_uses_strict_tr_envelope(self):
        client = self._client("supported")
        response = mock.MagicMock()
        client.chat.completions.create.return_value = response
        result = ht._safe_chat_create(
            client,
            model="gpt-5.4",
            messages=[
                {"role": "developer", "content": "Translate."},
                {"role": "user", "content": '{"tr":[{"i":"1","t":"Hello"}]}'},
            ],
        )
        self.assertIs(result, response)
        sent = client.chat.completions.create.call_args.kwargs
        self.assertEqual(sent["response_format"]["type"], "json_schema")
        self.assertEqual(
            sent["response_format"]["json_schema"]["schema"]["properties"]["tr"]
            ["items"]["properties"]["i"]["enum"],
            ["1"],
        )
        self.assertEqual(sent["messages"][-1]["role"], "user")

    def test_unsupported_schema_retries_plain_and_caches_result(self):
        client = self._client("unsupported")

        class UnsupportedError(RuntimeError):
            status_code = 400

        response = mock.MagicMock()
        client.chat.completions.create.side_effect = [
            UnsupportedError("response_format json_schema is not supported"),
            response,
        ]
        kwargs = {
            "model": "gpt-5.4",
            "messages": [
                {"role": "developer", "content": "Translate."},
                {"role": "user", "content": '{"tr":[{"i":"1","t":"Hello"}]}'},
            ],
        }
        self.assertIs(ht._safe_chat_create(client, **kwargs), response)
        first, second = client.chat.completions.create.call_args_list
        self.assertIn("response_format", first.kwargs)
        self.assertNotIn("response_format", second.kwargs)

        client.chat.completions.create.reset_mock()
        client.chat.completions.create.side_effect = None
        client.chat.completions.create.return_value = response
        ht._safe_chat_create(client, **kwargs)
        self.assertNotIn(
            "response_format",
            client.chat.completions.create.call_args.kwargs,
        )

    def test_non_gpt_custom_model_keeps_existing_behavior(self):
        client = self._client("regular")
        response = mock.MagicMock()
        client.chat.completions.create.return_value = response
        ht._safe_chat_create(
            client,
            model="gpt-4o",
            messages=[
                {"role": "user", "content": '{"tr":[{"i":"1","t":"Hello"}]}'},
            ],
        )
        self.assertNotIn(
            "response_format",
            client.chat.completions.create.call_args.kwargs,
        )

    def test_hybrid_array_extractor_accepts_structured_envelope(self):
        raw = '{"tr":[{"i":"1","t":"Merhaba"}]}'
        self.assertEqual(
            ht._extract_json_array(raw),
            '[{"i": "1", "t": "Merhaba"}]',
        )


class ProviderWaitUiCallbackTest(unittest.TestCase):
    def test_callback_logs_once_and_updates_status(self):
        logs = []
        statuses = []
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *args: logs.append(args),
            _set_status=statuses.append,
        )
        gui.App._provider_wait_callback(app, "start", 12, 1)
        gui.App._provider_wait_callback(app, "tick", 11, 1)
        gui.App._provider_wait_callback(app, "end", 0, 0)
        self.assertEqual(len(logs), 1)
        self.assertIn("12 sn", logs[0][0])
        self.assertIn("11 sn", statuses[-2])
        self.assertIn("devam ediliyor", statuses[-1])


if __name__ == "__main__":
    unittest.main()
