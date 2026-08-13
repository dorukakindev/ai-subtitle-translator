import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import provider_retry
import subtitle_translator_gui as gui


class _StatusError(RuntimeError):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class ProviderRecoveryPromptTest(unittest.TestCase):
    def test_only_recoverable_provider_failures_offer_dialog(self):
        self.assertTrue(gui._should_offer_provider_recovery(
            TimeoutError("connection timed out")))
        self.assertTrue(gui._should_offer_provider_recovery(RuntimeError(
            "503 model_not_found: failed to get available channel")))
        self.assertFalse(gui._should_offer_provider_recovery(
            _StatusError("invalid_api_key", 401)))

    def test_main_request_retries_after_user_confirmed_recovery(self):
        app = gui.App.__new__(gui.App)
        app._provider_recovery_generation = 0
        app._stop_flag = False
        app._helper_request_canceller = None
        app._coordinate_provider_recovery = Mock(return_value=True)
        response = object()
        with patch.object(
                gui, "_safe_chat_create",
                side_effect=[TimeoutError("connection timed out"), response]) as create:
            result = gui.App._main_translation_chat_create(
                app, object(), {"model": "gpt-test", "messages": []})
        self.assertIs(result, response)
        self.assertEqual(create.call_count, 2)
        app._coordinate_provider_recovery.assert_called_once()

    def test_permanent_failure_never_opens_recovery_dialog(self):
        app = gui.App.__new__(gui.App)
        app._provider_recovery_generation = 0
        app._stop_flag = False
        app._helper_request_canceller = None
        app._coordinate_provider_recovery = Mock(return_value=True)
        error = _StatusError("invalid_api_key", 401)
        with patch.object(gui, "_safe_chat_create", side_effect=error):
            with self.assertRaises(_StatusError):
                gui.App._main_translation_chat_create(
                    app, object(), {"model": "gpt-test", "messages": []})
        app._coordinate_provider_recovery.assert_not_called()

    def test_coordinator_advances_generation_only_after_continue(self):
        app = gui.App.__new__(gui.App)
        app._provider_recovery_condition = threading.Condition()
        app._provider_recovery_active = False
        app._provider_recovery_generation = 0
        app._stop_flag = False
        app._is_shutting_down = False
        app._ui_queue = None
        app._log = Mock()
        app._set_status = Mock()

        def show(_client, _model, _error, _path, result, event):
            result["decision"] = "continue"
            event.set()

        app._show_provider_recovery_dialog = show
        self.assertTrue(gui.App._coordinate_provider_recovery(
            app, object(), "gpt-test", TimeoutError("timeout"), 0))
        self.assertEqual(app._provider_recovery_generation, 1)
        self.assertFalse(app._provider_recovery_active)

    def test_parallel_failures_share_one_recovery_dialog(self):
        app = gui.App.__new__(gui.App)
        app._provider_recovery_condition = threading.Condition()
        app._provider_recovery_active = False
        app._provider_recovery_generation = 0
        app._stop_flag = False
        app._is_shutting_down = False
        app._ui_queue = None
        app._log = Mock()
        app._set_status = Mock()
        shown = []
        dialog_entered = threading.Event()
        release_dialog = threading.Event()

        def show(_client, _model, _error, _path, result, event):
            shown.append(1)
            dialog_entered.set()
            release_dialog.wait(timeout=2)
            result["decision"] = "continue"
            event.set()

        app._show_provider_recovery_dialog = show
        results = []

        def coordinate():
            results.append(gui.App._coordinate_provider_recovery(
                app, object(), "gpt-test", TimeoutError("timeout"), 0))

        with patch.object(gui, "_post_ui",
                          side_effect=lambda _app, fn, *args, **kwargs: fn(*args, **kwargs)):
            leader = threading.Thread(target=coordinate)
            follower = threading.Thread(target=coordinate)
            leader.start()
            self.assertTrue(dialog_entered.wait(timeout=1))
            follower.start()
            time.sleep(0.05)
            release_dialog.set()
            leader.join(timeout=2)
            follower.join(timeout=2)

        self.assertEqual(shown, [1])
        self.assertEqual(results, [True, True])
        self.assertEqual(app._provider_recovery_generation, 1)

    def test_health_probe_provider_call_has_no_automatic_retry(self):
        calls = []

        def fail():
            calls.append(1)
            raise TimeoutError("connection timed out")

        client = SimpleNamespace(base_url="https://example.invalid/v1")
        with patch.object(provider_retry, "_wait_for_transient_retry") as wait:
            with self.assertRaises(TimeoutError):
                provider_retry.provider_call_with_retry(
                    fail, client, "gpt-test", retry_delays=())
        self.assertEqual(len(calls), 1)
        wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
