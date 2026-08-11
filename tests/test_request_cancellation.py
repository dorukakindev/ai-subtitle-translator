import ast
import inspect
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui
from request_cancellation import RequestCancelled, RunRequestCanceller


class _Client:
    def __init__(self):
        self.base_url = "https://api.example.test/v1"
        self.api_key = "key"
        self.close = MagicMock()


class RunRequestCancellerTest(unittest.TestCase):
    def test_cancel_closes_each_active_client_once(self):
        canceller = RunRequestCanceller()
        client = _Client()
        canceller.register(client)
        canceller.register(client)

        self.assertEqual(canceller.cancel(), 1)
        client.close.assert_called_once_with()
        canceller.unregister(client)
        canceller.unregister(client)

    def test_cancelled_context_blocks_request_before_network(self):
        canceller = RunRequestCanceller()
        canceller.cancel()
        client = _Client()

        with patch("provider_retry.chat_create_with_compat") as create, \
             self.assertRaises(RequestCancelled):
            ht._safe_chat_create(
                client,
                cancel_context=canceller,
                model="gpt-5.4",
                messages=[{"role": "user", "content": "x"}],
            )

        create.assert_not_called()

    def test_cancel_attempts_to_close_active_client_and_discards_result(self):
        canceller = RunRequestCanceller()
        client = _Client()
        started = threading.Event()
        released = threading.Event()
        errors = []

        def blocked_create(*_args, **_kwargs):
            started.set()
            released.wait(timeout=2)
            raise RuntimeError("connection closed")

        client.close.side_effect = released.set

        def worker():
            try:
                ht._safe_chat_create(
                    client,
                    cancel_context=canceller,
                    model="gpt-5.4",
                    messages=[{"role": "user", "content": "x"}],
                )
            except Exception as exc:
                errors.append(exc)

        with patch("provider_retry.chat_create_with_compat",
                   side_effect=blocked_create):
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(canceller.cancel(), 1)
            thread.join(timeout=1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RequestCancelled)

    def test_completed_request_unregisters_before_later_cancel(self):
        canceller = RunRequestCanceller()
        client = _Client()
        response = SimpleNamespace(choices=[])

        with patch("provider_retry.chat_create_with_compat", return_value=response):
            self.assertIs(
                ht._safe_chat_create(
                    client,
                    cancel_context=canceller,
                    model="gpt-5.4",
                    messages=[{"role": "user", "content": "x"}],
                ),
                response,
            )

        self.assertEqual(canceller.cancel(), 0)
        client.close.assert_not_called()

    def test_late_success_after_cancel_is_discarded(self):
        canceller = RunRequestCanceller()
        client = _Client()

        def create(*_args, **_kwargs):
            canceller.cancel()
            return SimpleNamespace(choices=[])

        with patch("provider_retry.chat_create_with_compat",
                   side_effect=create), self.assertRaises(RequestCancelled):
            ht._safe_chat_create(
                client,
                cancel_context=canceller,
                model="gpt-5.4",
                messages=[{"role": "user", "content": "x"}],
            )

    def test_anthropic_adapter_returns_promptly_when_cancelled(self):
        canceller = RunRequestCanceller()
        client = _Client()
        client.base_url = "https://proxy.example/v1/messages"
        started = threading.Event()
        release = threading.Event()
        errors = []

        def blocked_adapter(**_kwargs):
            started.set()
            release.wait(timeout=2)
            return SimpleNamespace(choices=[])

        def worker():
            try:
                ht._safe_chat_create(
                    client,
                    cancel_context=canceller,
                    model="custom-claude",
                    messages=[{"role": "user", "content": "x"}],
                )
            except Exception as exc:
                errors.append(exc)

        with patch("helper_models.call_anthropic_messages",
                   side_effect=blocked_adapter):
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(canceller.cancel(), 1)
            thread.join(timeout=1)
            release.set()

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RequestCancelled)


def _late_success(canceller):
    """Return a response only after marking its owning run cancelled."""
    response = SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))],
    )

    def _create(*_args, **_kwargs):
        canceller.cancel()
        return response

    return _create


class DefaultHelperPassCancellationTest(unittest.TestCase):
    """Every default helper pass must pass the run context and discard late output."""

    def _run_hybrid_pass(self, fn, *args, **kwargs):
        canceller = RunRequestCanceller()
        client = _Client()
        with patch("openai.OpenAI", return_value=client), \
             patch("provider_retry.chat_create_with_compat",
                   side_effect=_late_success(canceller)) as create:
            result = fn(*args, cancel_context=canceller, **kwargs)
        self.assertEqual(create.call_count, 1)
        return result

    def test_native_pass_discards_late_result_and_stops_after_first_chunk(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Bu zaten doğru.")]

        result = self._run_hybrid_pass(
            ht.native_reader_pass,
            blocks,
            helper_api_key="key",
        )

        self.assertEqual(result, blocks)

    def test_native_pass_rolls_back_completed_chunk_when_next_chunk_is_cancelled(self):
        blocks = [
            (i, "00:00:00,000 --> 00:00:01,000", f"Eski çeviri {i}.")
            for i in range(1, 152)
        ]
        first = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"id":"1","fixed":"Daha doğal çeviri 1."}]'
            ))],
        )

        with patch("openai.OpenAI", return_value=_Client()), \
             patch("hybrid_translate._safe_chat_create",
                   side_effect=[first, RequestCancelled("cancelled")]):
            result = ht.native_reader_pass(
                blocks,
                helper_api_key="key",
                cancel_context=RunRequestCanceller(),
            )

        self.assertEqual(result, blocks)

    def test_critic_pass_rolls_back_completed_chunk_and_change_log_on_cancel(self):
        cues = [SimpleNamespace(index=i, text=f"Source {i}") for i in range(1, 102)]
        blocks = [
            (i, "00:00:00,000 --> 00:00:01,000", f"Eski çeviri {i}.")
            for i in range(1, 102)
        ]
        suspicious = [
            (i, "00:00:00,000 --> 00:00:01,000", f"Eski çeviri {i}.", "TEST")
            for i in range(1, 102)
        ]
        first = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"id":"1","fixed":"Daha doğal çeviri 1."}]'
            ))],
        )
        changes = [{"id": "existing"}]

        with patch("openai.OpenAI", return_value=_Client()), \
             patch("hybrid_translate._apply_local_fixes",
                   side_effect=lambda text, **_kwargs: (text + " yerel", 1)), \
             patch("hybrid_translate.run_validators", return_value=suspicious), \
             patch("hybrid_translate._safe_chat_create",
                   side_effect=[first, RequestCancelled("cancelled")]):
            result = ht.critic_pass_with_helper(
                cues,
                blocks,
                helper_api_key="key",
                change_log=changes,
            )

        self.assertEqual(result, blocks)
        self.assertEqual(changes, [{"id": "existing"}])

    def test_condense_pass_discards_late_result_and_stops_after_first_chunk(self):
        blocks = [(1, "00:00:00,000 --> 00:00:00,100", "x" * 100)]

        result, changed = self._run_hybrid_pass(
            ht.condense_fast_lines,
            blocks,
            helper_api_key="key",
        )

        self.assertEqual(result, blocks)
        self.assertEqual(changed, 0)

    def test_qc_autofix_never_applies_suggestion_after_request_cancel(self):
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Eski çeviri")]
        issues = [{
            "id": "1",
            "original": "Original line",
            "current": "Eski çeviri",
            "problem": "test",
            "suggestion": "İptalden sonra asla uygulanmamalı",
        }]

        result = self._run_hybrid_pass(
            ht.qc_auto_fix,
            issues,
            blocks,
            helper_api_key="key",
            model="gpt-5.4-mini",
        )

        self.assertEqual(result, blocks)

    def test_polish_pass_discards_late_result_without_retrying(self):
        canceller = RunRequestCanceller()
        client = _Client()
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda *_args, **_kwargs: None,
            _log_exc=lambda *_args, **_kwargs: None,
            _update_tokens=lambda *_args, **_kwargs: None,
        )
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Bu zaten doğru.")]

        with patch("openai.OpenAI", return_value=client), \
             patch("provider_retry.chat_create_with_compat",
                   side_effect=_late_success(canceller)) as create:
            result = gui.App._polish_pass(
                app,
                blocks,
                "Turkish",
                "key",
                "https://api.example.test/v1",
                "gpt-5.4-mini",
                cancel_context=canceller,
            )

        self.assertEqual(result, blocks)
        self.assertEqual(create.call_count, 1)


class GuiCancellationWiringTest(unittest.TestCase):
    def test_stop_cancels_active_helper_requests(self):
        canceller = MagicMock()
        app = SimpleNamespace(
            _stop_flag=False,
            _helper_request_canceller=canceller,
            _pause_btw_files=MagicMock(),
            _log=MagicMock(),
            _set_status=MagicMock(),
            _batch_lock=threading.RLock(),
            _active_batches={},
        )

        gui.App._stop(app)

        self.assertTrue(app._stop_flag)
        canceller.cancel.assert_called_once_with()

    def test_close_sets_stop_before_cancelling_requests(self):
        events = []

        class Canceller:
            def cancel(self):
                events.append(("cancel", app._stop_flag))

        app = SimpleNamespace(
            _is_shutting_down=False,
            _is_running=False,
            _pending_batches_after_id=None,
            _drain_ui_queue_id=None,
            _ui_queue=SimpleNamespace(get_nowait=MagicMock(
                side_effect=gui.queue.Empty)),
            _stop_flag=False,
            _helper_request_canceller=Canceller(),
            _stop_elapsed_timer=MagicMock(),
            _save_settings=MagicMock(),
            withdraw=MagicMock(),
            _drain_workers_for_close=MagicMock(),
        )

        gui.App._on_close(app)

        self.assertEqual(events, [("cancel", True)])
        app._drain_workers_for_close.assert_called_once_with()


class SyncRetryCancellationTest(unittest.TestCase):
    def test_every_direct_gui_chat_call_receives_cancel_context(self):
        tree = ast.parse(inspect.getsource(gui))
        missing = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else "")
            if name != "_safe_chat_create":
                continue
            if "cancel_context" not in {kw.arg for kw in node.keywords}:
                missing.append(node.lineno)

        self.assertEqual(missing, [])

    def test_stop_during_retry_backoff_never_starts_a_second_request(self):
        class TransientError(RuntimeError):
            status_code = 429

        canceller = RunRequestCanceller()
        app = SimpleNamespace(
            _stop_flag=False,
            _helper_request_canceller=canceller,
            _json_repair_pass=lambda *_args: None,
            _log=lambda *_args, **_kwargs: None,
            _update_tokens=lambda *_args, **_kwargs: None,
            _block_automatic_recovery_for_permanent_provider=lambda: None,
        )
        req = {
            "custom_id": "chunk-1",
            "body": {
                "model": "gpt-5.4-mini",
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": json.dumps({
                        "tr": [{"i": 1, "t": "Source line"}],
                    })},
                ],
            },
        }
        calls = []

        def send(_client, **kwargs):
            calls.append(kwargs)
            raise TransientError("HTTP 429")

        def stop_during_wait(_seconds):
            app._stop_flag = True
            canceller.cancel()

        with patch.object(gui, "_safe_chat_create", side_effect=send), \
             patch.object(gui.time, "sleep", side_effect=stop_during_wait):
            unresolved = gui.App._retry_hata(
                app, object(), {"chunk-1": "[HATA]"}, [req], max_rounds=1)

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0]["cancel_context"], canceller)
        self.assertEqual(unresolved, {"chunk-1"})


if __name__ == "__main__":
    unittest.main()
