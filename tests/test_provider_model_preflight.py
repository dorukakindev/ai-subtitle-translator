import unittest
from types import SimpleNamespace
from unittest import mock

import subtitle_translator_gui as gui


class ProviderModelPreflightTest(unittest.TestCase):
    def test_collects_only_enabled_routes_and_deduplicates(self):
        snapshot = {
            "main_api_key": "key-main",
            "main_api_base_url": "https://api.shuaiapi.com/v1",
            "main_model_name": "gpt-5.4",
            "hybrid_mode": True,
            "critic": True,
            "native": True,
            "semantic_reconcile": True,
            "polish": True,
            "backtrans": True,
            "helper_keys": {
                role: "key-main" for role in ("analysis", "critic", "polish", "qc")
            },
            "helper_urls": {
                role: "https://api.shuaiapi.com/v1"
                for role in ("analysis", "critic", "polish", "qc")
            },
            "helper_models": {
                role: "gpt-5.4" for role in ("analysis", "critic", "polish", "qc")
            },
        }

        targets = gui._provider_preflight_targets(snapshot)

        self.assertEqual(targets, [(
            "Ana ceviri", "key-main", "https://api.shuaiapi.com/v1", "gpt-5.4")
        ])

    def test_repair_only_does_not_require_unused_helper_routes(self):
        snapshot = {
            "main_api_key": "key-main",
            "main_api_base_url": "https://api.shuaiapi.com/v1",
            "main_model_name": "gpt-5.4",
            "auto_retry_repair_only": True,
            "hybrid_mode": True,
            "critic": True,
            "helper_keys": {"analysis": "key-helper", "critic": "key-helper"},
            "helper_urls": {
                "analysis": "https://api.shuaiapi.com/v1",
                "critic": "https://api.shuaiapi.com/v1",
            },
            "helper_models": {"analysis": "gpt-5.4", "critic": "gpt-5.4"},
        }

        self.assertEqual(gui._provider_preflight_targets(snapshot), [(
            "Ana ceviri", "key-main", "https://api.shuaiapi.com/v1", "gpt-5.4")
        ])

    def test_case_sensitive_endpoint_paths_are_not_deduplicated(self):
        snapshot = {
            "main_api_key": "same-key",
            "main_api_base_url": "https://PROVIDER.example/Official/V1",
            "main_model_name": "gpt-5.4",
            "hybrid_mode": True,
            "helper_keys": {"analysis": "same-key"},
            "helper_urls": {
                "analysis": "https://provider.example/official/V1"},
            "helper_models": {"analysis": "gpt-5.4"},
        }

        targets = gui._provider_preflight_targets(snapshot)

        self.assertEqual(len(targets), 2)

    def test_reads_sdk_and_dictionary_model_lists(self):
        sdk_response = SimpleNamespace(data=[
            SimpleNamespace(id="gpt-5.4"), SimpleNamespace(id="gpt-5.4-mini")
        ])
        dict_response = {"data": [{"id": "gpt-5.4"}]}

        self.assertEqual(
            gui._visible_model_ids(sdk_response), {"gpt-5.4", "gpt-5.4-mini"})
        self.assertEqual(gui._visible_model_ids(dict_response), {"gpt-5.4"})

    @staticmethod
    def _app_stub():
        app = SimpleNamespace()
        app.logs = []
        app._set_phase = lambda *_args: None
        app._set_status = lambda *_args: None
        app._log = lambda message, tag=None: app.logs.append((message, tag))
        return app

    def test_preflight_disables_sdk_retries_and_accepts_visible_model(self):
        app = self._app_stub()
        listed = SimpleNamespace(data=[SimpleNamespace(id="gpt-5.4")])
        request_client = mock.MagicMock()
        request_client.models.list.return_value = listed
        client = mock.MagicMock()
        client.with_options.return_value = request_client

        with mock.patch.object(gui, "OpenAI", return_value=client):
            ok = gui.App._provider_model_preflight(app, [(
                "Ana ceviri", "key", "https://api.shuaiapi.com/v1", "gpt-5.4")
            ])

        self.assertTrue(ok)
        client.with_options.assert_called_once_with(max_retries=0, timeout=30.0)
        request_client.models.list.assert_called_once_with()

    def test_preflight_blocks_model_missing_from_group(self):
        app = self._app_stub()
        request_client = mock.MagicMock()
        request_client.models.list.return_value = SimpleNamespace(
            data=[SimpleNamespace(id="gpt-5.4-mini")])
        client = mock.MagicMock()
        client.with_options.return_value = request_client

        with mock.patch.object(gui, "OpenAI", return_value=client):
            ok = gui.App._provider_model_preflight(app, [(
                "Ana ceviri", "key", "https://api.shuaiapi.com/v1", "gpt-5.4")
            ])

        self.assertFalse(ok)
        self.assertTrue(any(tag == "err" for _message, tag in app.logs))

    def test_transient_model_list_failure_defers_to_visible_chat_retry(self):
        app = self._app_stub()

        class TemporaryError(RuntimeError):
            status_code = 503

        request_client = mock.MagicMock()
        request_client.models.list.side_effect = TemporaryError(
            "No available channel temporarily")
        client = mock.MagicMock()
        client.with_options.return_value = request_client

        with mock.patch.object(gui, "OpenAI", return_value=client):
            ok = gui.App._provider_model_preflight(app, [(
                "Ana ceviri", "key", "https://api.shuaiapi.com/v1", "gpt-5.4")
            ])

        self.assertTrue(ok)
        self.assertTrue(any(tag == "warn" for _message, tag in app.logs))


if __name__ == "__main__":
    unittest.main()
