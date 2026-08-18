import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import provider_retry
import subtitle_translator_gui as gui
from helper_models import resolve_helper_model


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _HttpError(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status_code = status


class HelperShuaiRouteTest(unittest.TestCase):
    def tearDown(self):
        provider_retry.configure_shuai_route_failover(
            False, provider_retry.SHUAI_API_ROUTE_OPTIONS[0][1])

    def test_route_normalization_accepts_only_known_hosts(self):
        self.assertEqual(
            provider_retry.normalize_shuai_api_route(
                "https://cdn.shuaiapi.com/"),
            "https://cdn.shuaiapi.com/v1")
        self.assertEqual(
            provider_retry.normalize_shuai_api_route(
                "https://api.shuaiapi.com.evil.example/v1"), "")

    def test_builtin_reseller_uses_selected_route(self):
        display = gui.SHUAI_ROUTE_DISPLAY["Global"]
        stub = SimpleNamespace(
            helper_shuai_route_var=_Var(display),
            helper_model_vars={"critic": _Var("GPT-5.4 (Reseller)")},
            _api_key_assignments={},
            _api_key_profiles={},
            _helper_model_config=lambda _role: resolve_helper_model(
                "GPT-5.4 (Reseller)"),
            _is_custom_helper_label=lambda _label: False,
        )
        self.assertEqual(
            gui.App._helper_api_base_url(stub, "critic"),
            "https://oai.sb/v1")

    def test_same_shuai_key_is_reused_across_route_hosts(self):
        stub = SimpleNamespace(
            _active_snapshot=None,
            _api_key_assignments={},
            _api_key_profiles={},
            helper_model_vars={"critic": _Var("GPT-5.4 (Reseller)")},
            helper_role_key_vars={"critic": _Var("")},
            helper_custom_key_vars={},
            _helper_keys_cache={},
            helper_key_entry=_Var(""),
            api_key_entry=_Var("shared-shuai-key"),
            _is_custom_helper_label=lambda _label: False,
            _get_current_helper_provider=lambda _role: "openai",
            _helper_api_base_url=lambda _role: "https://oai.sb/v1",
            _main_custom_active=lambda: False,
            _main_api_base_url=lambda: "https://api.shuaiapi.com/v1",
            _main_api_key=lambda: "shared-shuai-key",
        )
        self.assertEqual(
            gui.App._helper_api_key(stub, "critic"), "shared-shuai-key")

    def test_transient_route_failure_moves_to_next_route(self):
        provider_retry.configure_shuai_route_failover(
            True, "https://api.shuaiapi.com/v1")
        client = SimpleNamespace(
            base_url="https://api.shuaiapi.com/v1", api_key="secret")
        calls = []
        response = SimpleNamespace()

        def create(route_client, _model, _kwargs, **kwargs):
            calls.append((str(route_client.base_url), kwargs.get("retry_delays")))
            if str(route_client.base_url).startswith(
                    "https://api.shuaiapi.com"):
                raise _HttpError(503, "server error")
            return response

        with patch.object(
                provider_retry, "_openai_client_for_route",
                side_effect=lambda _client, route: SimpleNamespace(
                    base_url=route, api_key="secret")), patch.object(
                provider_retry, "chat_create_with_compat",
                side_effect=create):
            result = provider_retry.chat_create_with_shuai_failover(
                client, "gpt-5.4", {"messages": []})

        self.assertIs(result, response)
        self.assertEqual(calls[0][0], "https://api.shuaiapi.com/v1")
        self.assertEqual(calls[1][0], "https://oai.sb/v1")
        self.assertEqual(calls[0][1], ())
        self.assertEqual(response.shuai_route_used, "https://oai.sb/v1")

    def test_auth_error_does_not_walk_other_routes(self):
        provider_retry.configure_shuai_route_failover(
            True, "https://api.shuaiapi.com/v1")
        client = SimpleNamespace(
            base_url="https://api.shuaiapi.com/v1", api_key="secret")
        with patch.object(
                provider_retry, "chat_create_with_compat",
                side_effect=_HttpError(401, "invalid api key")) as create:
            with self.assertRaises(_HttpError):
                provider_retry.chat_create_with_shuai_failover(
                    client, "gpt-5.4", {"messages": []})
        self.assertEqual(create.call_count, 1)

    def test_all_routes_failed_preserves_normal_retry_policy(self):
        provider_retry.configure_shuai_route_failover(
            True, "https://api.shuaiapi.com/v1")
        client = SimpleNamespace(
            base_url="https://api.shuaiapi.com/v1", api_key="secret")
        calls = []

        def create(route_client, _model, _kwargs, **kwargs):
            calls.append((str(route_client.base_url), kwargs.get("retry_delays")))
            raise _HttpError(503, "server error")

        with patch.object(
                provider_retry, "_openai_client_for_route",
                side_effect=lambda _client, route: SimpleNamespace(
                    base_url=route, api_key="secret")), patch.object(
                provider_retry, "chat_create_with_compat",
                side_effect=create):
            with self.assertRaises(_HttpError):
                provider_retry.chat_create_with_shuai_failover(
                    client, "gpt-5.4", {"messages": []})

        self.assertEqual(len(calls), 5)
        self.assertTrue(all(retry == () for _url, retry in calls[:4]))
        self.assertIsNone(calls[-1][1])

    def test_helper_test_role_dispatches_to_live_dialog(self):
        called = []
        stub = SimpleNamespace(
            helper_roles={"analysis": "Yardımcı Analiz Modeli",
                          "critic": "Critic Pass Modeli"},
            helper_api_test_role_var=_Var("Yardımcı Analiz Modeli"),
            _show_api_translation_test_dialog=lambda helper_role=None: called.append(
                helper_role),
        )
        gui.App._show_helper_api_translation_test(stub)
        self.assertEqual(called, ["analysis"])

    def test_live_dialog_uses_selected_helper_credentials(self):
        source = inspect.getsource(gui.App._show_api_translation_test_dialog)
        self.assertIn("self._helper_api_key(helper_role)", source)
        self.assertIn("self._helper_api_model(helper_role)", source)
        self.assertIn("self._helper_api_base_url(helper_role)", source)
        self.assertIn("helper_api_test_", source)


if __name__ == "__main__":
    unittest.main()
