import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import hybrid_translate as ht
import provider_retry
import subtitle_translator_gui as gui


def _client(url="https://api.shuaiapi.com/v1", key="sk-reseller"):
    return SimpleNamespace(base_url=url, api_key=key)


class RetryAfterParsingTest(unittest.TestCase):
    def test_status_code_with_underscore_is_parsed_as_transient(self):
        exc = RuntimeError("status_code=503, 服务暂时不可用，请稍后重试")
        self.assertEqual(provider_retry._status_code(exc), 503)
        self.assertTrue(provider_retry._is_transient_provider_error(exc))

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
    def test_clearing_hooks_prevents_late_ui_callback(self):
        events = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: 100.0,
            sleeper=lambda _delay: None,
            wait_callback=lambda *args: events.append(args),
        )

        registry.set_hooks()
        registry._notify("request_tick", 3, 1)

        self.assertEqual(events, [])

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

    def test_transient_retry_wait_uses_schedule_and_can_be_cancelled(self):
        now = [100.0]
        events = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
            wait_callback=lambda *args: events.append(args),
        )

        self.assertEqual(registry.wait_for_retry(30, 1, 3), 30.0)
        self.assertEqual(now[0], 130.0)
        self.assertEqual(events[0][0], "retry_start_1_3")
        self.assertEqual(events[-1], ("retry_end_1_3", 0, 0))

    def test_three_transient_failures_open_circuit_then_one_probe_recovers(self):
        now = [100.0]
        events = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
            wait_callback=lambda *args: events.append(args),
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        client = _client()
        error = TemporaryError("temporarily unavailable")
        self.assertIsNone(registry.record_transient_failure(client, error))
        self.assertIsNone(registry.record_transient_failure(client, error))
        self.assertEqual(
            registry.record_transient_failure(client, error),
            provider_retry.PROVIDER_CIRCUIT_COOLDOWN_SECONDS,
        )

        waited = registry.before_request(client)
        self.assertEqual(
            waited, provider_retry.PROVIDER_CIRCUIT_COOLDOWN_SECONDS)
        registry.request_started()
        registry.request_finished(client, True)
        self.assertEqual(registry.before_request(client), 0.0)
        self.assertIn("circuit_open", [event[0] for event in events])
        self.assertIn("circuit_probe", [event[0] for event in events])
        self.assertIn("circuit_recovered", [event[0] for event in events])

    def test_permanent_response_resets_old_transient_failure_count(self):
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: 100.0,
            sleeper=lambda _delay: None,
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        class PermanentError(RuntimeError):
            status_code = 503

        client = _client()
        temporary = TemporaryError("temporarily unavailable")
        permanent = PermanentError(
            "model_not_found: No available channel for model gpt-5.4")
        self.assertIsNone(registry.record_transient_failure(client, temporary))
        self.assertIsNone(registry.record_transient_failure(client, temporary))
        self.assertIsNone(registry.record_transient_failure(client, permanent))
        self.assertIsNone(registry.record_transient_failure(client, temporary))

    def test_rate_limit_probe_releases_transient_circuit_lock(self):
        now = [100.0]
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        class RateLimitError(RuntimeError):
            status_code = 429

        client = _client()
        for _ in range(3):
            registry.record_transient_failure(
                client, TemporaryError("temporarily unavailable"),
                model="gpt-5.4")
        registry.before_request(client, model="gpt-5.4")

        registry.record_transient_failure(
            client, RateLimitError("rate limit"), model="gpt-5.4")

        self.assertEqual(
            registry.before_request(client, model="gpt-5.4"), 0.0)

    def test_permanent_probe_releases_transient_circuit_lock(self):
        now = [100.0]
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        class PermanentError(RuntimeError):
            status_code = 503

        client = _client()
        for _ in range(3):
            registry.record_transient_failure(
                client, TemporaryError("temporarily unavailable"),
                model="gpt-5.4")
        registry.before_request(client, model="gpt-5.4")

        registry.record_transient_failure(
            client,
            PermanentError("model_not_found: No available channel for model gpt-5.4"),
            model="gpt-5.4",
        )

        self.assertEqual(
            registry.before_request(client, model="gpt-5.4"), 0.0)

    def test_failed_probe_reopens_circuit_with_visible_event(self):
        now = [100.0]
        events = []
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: now[0],
            sleeper=lambda delay: now.__setitem__(0, now[0] + delay),
            wait_callback=lambda *args: events.append(args),
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        client = _client()
        error = TemporaryError("temporarily unavailable")
        for _ in range(3):
            registry.record_transient_failure(client, error)
        registry.before_request(client)
        registry.request_started()
        registry.request_finished(client, False)
        self.assertEqual(
            registry.record_transient_failure(client, error),
            provider_retry.PROVIDER_CIRCUIT_COOLDOWN_SECONDS,
        )

        self.assertIn("circuit_reopen", [event[0] for event in events])

    def test_circuit_is_model_scoped_not_entire_reseller_key(self):
        registry = provider_retry.ProviderCooldownRegistry(
            clock=lambda: 100.0,
            sleeper=lambda _delay: None,
        )

        class TemporaryError(RuntimeError):
            status_code = 503

        client = _client()
        error = TemporaryError("temporarily unavailable")
        for _ in range(3):
            registry.record_transient_failure(
                client, error, model="gpt-5.4")

        self.assertEqual(
            registry.before_request(client, model="gpt-5.4-mini"), 0.0)


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
            mock.patch("provider_retry._wait_for_transient_retry") as wait,
        ):
            with self.assertRaises(RuntimeError):
                fn(client, model="gpt-5.4", messages=[])
        self.assertEqual(before.call_count, 6)
        self.assertEqual(record.call_count, 6)
        self.assertEqual(wait.call_args_list, [
            mock.call(error, 1, 5),
            mock.call(error, 2, 5),
            mock.call(error, 3, 5),
            mock.call(error, 4, 5),
            mock.call(error, 5, 5),
        ])

    def test_hybrid_wrapper_records_reseller_429(self):
        self._assert_wrapper_records_429(ht._safe_chat_create)

    def test_gui_wrapper_records_reseller_429(self):
        self._assert_wrapper_records_429(gui._safe_chat_create)

    def test_temporary_503_uses_short_first_retry_schedule(self):
        client = mock.MagicMock()
        client.base_url = "https://api.shuaiapi.com/v1"
        client.api_key = "sk-reseller"

        class TemporaryError(RuntimeError):
            status_code = 503

        error = TemporaryError("The service is temporarily unavailable")
        response = mock.MagicMock()
        client.chat.completions.create.side_effect = [
            error, error, error, error, error, response]
        waits = []
        with mock.patch.object(
            provider_retry, "PROVIDER_CIRCUIT_COOLDOWN_SECONDS", 0.0,
        ), mock.patch.object(
            provider_retry._REGISTRY,
            "wait_for_retry",
            side_effect=lambda delay, attempt, total: waits.append(
                (delay, attempt, total)) or delay,
        ), mock.patch.object(
            provider_retry._REGISTRY, "notify_retry_success"
        ) as retry_success:
            result = ht._safe_chat_create(
                client, model="gpt-5.4", messages=[])

        self.assertIs(result, response)
        self.assertEqual(waits, [
            (10.0, 1, 5),
            (20.0, 2, 5),
            (30.0, 3, 5),
            (40.0, 4, 5),
            (120.0, 5, 5),
        ])
        retry_success.assert_called_once_with(5, 5)

    def test_transient_error_hint_does_not_force_120_second_first_wait(self):
        class TemporaryError(RuntimeError):
            status_code = 503

        error = TemporaryError("temporarily unavailable; try again in 120 seconds")
        waits = []
        with mock.patch.object(
            provider_retry._REGISTRY,
            "wait_for_retry",
            side_effect=lambda delay, attempt, total: waits.append(
                (delay, attempt, total)) or delay,
        ):
            provider_retry._wait_for_transient_retry(error, 1, 5)

        self.assertEqual(waits, [(10.0, 1, 5)])

    def test_permanent_model_channel_503_is_not_retried(self):
        client = mock.MagicMock()
        client.base_url = "https://api.shuaiapi.com/v1"
        client.api_key = "sk-reseller"

        class ChannelError(RuntimeError):
            status_code = 503

        error = ChannelError(
            "model_not_found: No available channel for model gpt-5.4")
        client.chat.completions.create.side_effect = error
        with mock.patch("provider_retry._wait_for_transient_retry") as wait:
            with self.assertRaises(ChannelError):
                ht._safe_chat_create(client, model="gpt-5.4", messages=[])

        client.chat.completions.create.assert_called_once()
        wait.assert_not_called()


class ResponseCheckpointTest(unittest.TestCase):
    def tearDown(self):
        provider_retry.configure_response_checkpoint()

    @staticmethod
    def _response(content):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop")],
            usage=None,
        )

    @staticmethod
    def _mock_client(response):
        client = mock.MagicMock()
        client.base_url = "https://reseller.example/v1"
        client.api_key = "sk-hidden"
        client.chat.completions.create.return_value = response
        return client

    def test_completed_response_is_replayed_after_restart(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            kwargs = {"messages": [{"role": "user", "content": "critic packet 1"}]}
            first = self._mock_client(self._response('[{"id":"1","fixed":"İyi."}]'))
            provider_retry.configure_response_checkpoint(root, "run-origin")
            original = provider_retry.chat_create_with_compat(
                first, "gpt-4.1", kwargs)
            self.assertEqual(first.chat.completions.create.call_count, 1)

            hits = []
            resumed = self._mock_client(RuntimeError("API çağrılmamalı"))
            resumed.chat.completions.create.side_effect = AssertionError(
                "tamamlanan paket yeniden gönderilmemeli")
            provider_retry.configure_response_checkpoint(
                root, "run-origin", allow_reads=True,
                hit_callback=hits.append)
            restored = provider_retry.chat_create_with_compat(
                resumed, "gpt-4.1", kwargs)

            self.assertEqual(
                restored.choices[0].message.content,
                original.choices[0].message.content)
            resumed.chat.completions.create.assert_not_called()
            self.assertEqual(hits, [1])
            checkpoint_text = "".join(
                path.read_text(encoding="utf-8")
                for path in root.rglob("*.json"))
            self.assertNotIn("sk-hidden", checkpoint_text)
            self.assertNotIn("critic packet 1", checkpoint_text)

    def test_stage_label_does_not_change_existing_checkpoint_identity(self):
        client = self._mock_client(self._response("ok"))
        kwargs = {"messages": [{"role": "user", "content": "same request"}]}
        legacy = provider_retry._response_checkpoint_key(
            client, "gpt-5.4", kwargs)
        labelled = provider_retry._response_checkpoint_key(
            client, "gpt-5.4", kwargs,
            checkpoint_label="native_reader")
        self.assertEqual(legacy, labelled)

    def test_checkpoint_reports_named_analysis_stage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            kwargs = {"messages": [{"role": "user", "content": "scene page"}]}
            first = self._mock_client(self._response('{"scenes":[]}'))
            provider_retry.configure_response_checkpoint(root, "run-origin")
            provider_retry.chat_create_with_compat(
                first, "gpt-5.4", kwargs,
                checkpoint_label="analysis_scene_plan")

            hits = []
            resumed = self._mock_client(RuntimeError("must not call API"))
            resumed.chat.completions.create.side_effect = AssertionError(
                "completed analysis stage must be replayed")
            provider_retry.configure_response_checkpoint(
                root, "run-origin", allow_reads=True,
                hit_callback=lambda count, label: hits.append((count, label)))
            provider_retry.chat_create_with_compat(
                resumed, "gpt-5.4", kwargs,
                checkpoint_label="analysis_scene_plan")

            resumed.chat.completions.create.assert_not_called()
            self.assertEqual(hits, [(1, "analysis_scene_plan")])

    def test_cached_response_is_consumed_once_before_live_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            kwargs = {"messages": [{"role": "user", "content": "same request"}]}
            first = self._mock_client(self._response("malformed cached response"))
            provider_retry.configure_response_checkpoint(root, "run-origin")
            provider_retry.chat_create_with_compat(first, "gpt-4.1", kwargs)

            resumed = self._mock_client(self._response("fresh retry response"))
            provider_retry.configure_response_checkpoint(
                root, "run-origin", allow_reads=True)
            cached = provider_retry.chat_create_with_compat(
                resumed, "gpt-4.1", kwargs)
            fresh = provider_retry.chat_create_with_compat(
                resumed, "gpt-4.1", kwargs)

            self.assertEqual(
                cached.choices[0].message.content, "malformed cached response")
            self.assertEqual(
                fresh.choices[0].message.content, "fresh retry response")
            resumed.chat.completions.create.assert_called_once()

    def test_changed_request_does_not_reuse_stale_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            first = self._mock_client(self._response("old"))
            provider_retry.configure_response_checkpoint(root, "run-origin")
            provider_retry.chat_create_with_compat(
                first, "gpt-4.1",
                {"messages": [{"role": "user", "content": "old input"}]})

            resumed = self._mock_client(self._response("new"))
            provider_retry.configure_response_checkpoint(
                root, "run-origin", allow_reads=True)
            result = provider_retry.chat_create_with_compat(
                resumed, "gpt-4.1",
                {"messages": [{"role": "user", "content": "changed input"}]})

            self.assertEqual(result.choices[0].message.content, "new")
            resumed.chat.completions.create.assert_called_once()

    def test_late_response_cannot_write_into_reconfigured_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            response = self._response("late old-run response")
            client = self._mock_client(response)
            provider_retry.configure_response_checkpoint(root, "same-origin")

            def finish_after_new_run_started(*_args, **_kwargs):
                provider_retry.configure_response_checkpoint(
                    root, "same-origin", allow_reads=True)
                return response

            with mock.patch.object(
                provider_retry,
                "_chat_create_with_compat_uncached",
                side_effect=finish_after_new_run_started,
            ):
                result = provider_retry.chat_create_with_compat(
                    client,
                    "gpt-5.4",
                    {"messages": [{"role": "user", "content": "old run"}]},
                    checkpoint_label="main_translation",
                )

            self.assertIs(result, response)
            self.assertEqual(list(root.rglob("*.json")), [])

    def test_completed_run_clears_only_its_namespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".quality_response_checkpoint"
            client = self._mock_client(self._response("ok"))
            provider_retry.configure_response_checkpoint(root, "run-a")
            provider_retry.chat_create_with_compat(
                client, "gpt-4.1", {"messages": []})
            provider_retry.configure_response_checkpoint(root, "run-b")
            provider_retry.chat_create_with_compat(
                client, "gpt-4.1", {"messages": []})

            self.assertTrue(provider_retry.clear_response_checkpoint_namespace(
                root, "run-a"))
            run_a = provider_retry._response_checkpoint_namespace_dir(root, "run-a")
            run_b = provider_retry._response_checkpoint_namespace_dir(root, "run-b")
            self.assertFalse(run_a.exists())
            self.assertTrue(run_b.exists())


class ResponseCheckpointCoverageTest(unittest.TestCase):
    def test_all_safe_chat_call_sites_name_their_checkpoint_stage(self):
        missing = []
        for module in (ht, gui):
            path = Path(module.__file__)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = (
                    func.attr if isinstance(func, ast.Attribute)
                    else func.id if isinstance(func, ast.Name)
                    else ""
                )
                if name != "_safe_chat_create":
                    continue
                if not any(
                    keyword.arg == "_checkpoint_label"
                    for keyword in node.keywords
                ):
                    missing.append(f"{path.name}:{node.lineno}")
        self.assertEqual(missing, [])


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

    def test_transient_retry_callback_reports_attempt_and_delay(self):
        logs = []
        statuses = []
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *args: logs.append(args),
            _set_status=statuses.append,
        )
        gui.App._provider_wait_callback(app, "retry_start_2_5", 20, 1)
        gui.App._provider_wait_callback(app, "retry_tick_2_5", 19, 1)
        gui.App._provider_wait_callback(app, "retry_end_2_5", 0, 0)
        gui.App._provider_wait_callback(app, "retry_success_2_5", 0, 0)

        self.assertEqual(len(logs), 3)
        self.assertIn("20 sn", logs[0][0])
        self.assertIn("2/5", logs[0][0])
        self.assertIn("gönderiliyor", logs[1][0])
        self.assertIn("başarılı", logs[2][0])
        self.assertIn("19 sn", statuses[-3])
        self.assertIn("yanıt bekleniyor", statuses[-2])
        self.assertIn("işlem devam ediyor", statuses[-1])

    def test_circuit_callback_reports_pause_probe_and_recovery(self):
        logs = []
        statuses = []
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *args: logs.append(args),
            _set_status=statuses.append,
        )
        gui.App._provider_wait_callback(app, "circuit_open", 60, 0)
        gui.App._provider_wait_callback(app, "circuit_tick", 30, 1)
        gui.App._provider_wait_callback(app, "circuit_probe", 0, 1)
        gui.App._provider_wait_callback(app, "circuit_reopen", 60, 1)
        gui.App._provider_wait_callback(app, "circuit_recovered", 0, 0)

        self.assertEqual(len(logs), 4)
        self.assertIn("60 sn", logs[0][0])
        self.assertIn("tek kontrol", logs[0][0])
        self.assertIn("kontrol", logs[1][0])
        self.assertIn("başarısız", logs[2][0])
        self.assertIn("yeniden", logs[3][0])
        self.assertIn("devam", statuses[-1])

    def test_request_heartbeat_shows_elapsed_wait(self):
        statuses = []
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *_args: None,
            _set_status=statuses.append,
        )
        gui.App._provider_wait_callback(app, "request_start", 0, 2)
        gui.App._provider_wait_callback(app, "request_tick", 47, 2)

        self.assertIn("47 sn", statuses[-1])
        self.assertIn("2 aktif", statuses[-1])


if __name__ == "__main__":
    unittest.main()
