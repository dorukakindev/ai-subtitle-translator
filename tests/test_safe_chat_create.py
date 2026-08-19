import unittest
from unittest import mock

import hybrid_translate as ht
import subtitle_translator_gui as gui
from request_cancellation import RunRequestCanceller


class SafeChatCreateModelCompatTest(unittest.TestCase):
    """_safe_chat_create model-specific kwarg stripping (no network call)."""

    def _make_client(self):
        c = mock.MagicMock()
        c.base_url = "https://api.openai.com/v1"
        c.api_key = "sk-fake"
        return c

    def _call(self, fn, client, **kwargs):
        try:
            fn(client, **kwargs)
        except Exception:
            pass
        return client.chat.completions.create

    def test_o1_strips_temperature(self):
        client = self._make_client()
        create = self._call(ht._safe_chat_create, client, model="o1-preview", temperature=0.7, messages=[])
        _called_kwargs = create.call_args[1]
        self.assertNotIn("temperature", _called_kwargs)

    def test_o1_converts_system_to_developer(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create, client, model="o1-mini",
            messages=[{"role": "system", "content": "you are x"}],
        )
        _called_kwargs = create.call_args[1]
        msgs = _called_kwargs["messages"]
        self.assertEqual(msgs[0]["role"], "developer")

    def test_o1_strips_response_format(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create, client, model="o1-preview",
            messages=[], response_format={"type": "json_object"},
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("response_format", _called_kwargs)

    def test_o3_strips_response_format_and_converts_system(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create,
            client,
            model="o3-mini",
            messages=[{"role": "system", "content": "x"}],
            response_format={"type": "json_object"},
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("response_format", _called_kwargs)
        self.assertEqual(_called_kwargs["messages"][0]["role"], "developer")

    def test_o4_strips_response_format_and_converts_system(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create,
            client,
            model="o4-mini",
            messages=[{"role": "system", "content": "x"}],
            response_format={"type": "json_object"},
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("response_format", _called_kwargs)
        self.assertEqual(_called_kwargs["messages"][0]["role"], "developer")

    def test_gpt5_strips_temperature(self):
        client = self._make_client()
        create = self._call(ht._safe_chat_create, client, model="gpt-5.4-mini", temperature=0.7, messages=[])
        _called_kwargs = create.call_args[1]
        self.assertNotIn("temperature", _called_kwargs)

    def test_gpt5_strips_response_format_and_converts_system(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create,
            client,
            model="gpt-5.4-mini",
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "you are x"}],
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("temperature", _called_kwargs)
        self.assertNotIn("response_format", _called_kwargs)
        self.assertEqual(_called_kwargs["messages"][0]["role"], "developer")

    def test_regular_model_keeps_temperature(self):
        client = self._make_client()
        create = self._call(ht._safe_chat_create, client, model="gpt-4o", temperature=0.7, messages=[])
        _called_kwargs = create.call_args[1]
        self.assertEqual(_called_kwargs["temperature"], 0.7)

    def test_regular_model_keeps_response_format_and_system(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create,
            client,
            model="gpt-4o",
            temperature=0.7,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "you are x"}],
        )
        _called_kwargs = create.call_args[1]
        self.assertEqual(_called_kwargs["temperature"], 0.7)
        self.assertEqual(_called_kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(_called_kwargs["messages"][0]["role"], "system")

    def test_reasoning_model_maps_max_tokens(self):
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create, client, model="o3-mini",
            messages=[], max_tokens=4000,
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("max_tokens", _called_kwargs)
        self.assertEqual(_called_kwargs.get("max_completion_tokens"), 4000)

    def test_reasoning_model_raises_tiny_budget_to_floor(self):
        """Düşünme jetonları da bu bütçeden düşer; 40-80 jetonluk kısa görevler
        (tür/kaynak dil tespiti) hiç görünür çıktı üretemiyordu."""
        client = self._make_client()
        create = self._call(
            ht._safe_chat_create, client, model="o3-mini",
            messages=[], max_tokens=80,
        )
        self.assertEqual(
            create.call_args[1]["max_completion_tokens"],
            ht.REASONING_MIN_COMPLETION_TOKENS)

    def test_bedrock_provider_routes_away(self):
        client = mock.MagicMock()
        client.base_url = "https://bedrock.us-east-1.amazonaws.com"
        client.api_key = "fake"
        with mock.patch("helper_models.call_bedrock_converse", return_value="bedrock_ok") as mock_bedrock:
            result = ht._safe_chat_create(
                client, model="claude-3", messages=[], timeout=17)
            self.assertEqual(result, "bedrock_ok")
            mock_bedrock.assert_called_once()
            self.assertEqual(mock_bedrock.call_args.kwargs["timeout_seconds"], 17)
            self.assertIsNone(mock_bedrock.call_args.kwargs["cancel_context"])

    def test_custom_messages_url_routes_to_anthropic(self):
        client = mock.MagicMock()
        client.base_url = "https://proxy.example/v1/messages"
        client.api_key = "fake"
        with mock.patch("helper_models.call_anthropic_messages", return_value="ok") as call:
            self.assertEqual(
                ht._safe_chat_create(
                    client, model="custom-claude", messages=[], timeout=23), "ok")
            call.assert_called_once()
            self.assertEqual(call.call_args.kwargs["timeout_seconds"], 23)
            self.assertIsNone(call.call_args.kwargs["cancel_context"])

    def test_gui_helper_routes_forward_timeout_and_cancel_context(self):
        client = mock.MagicMock()
        client.base_url = "https://proxy.example/v1/messages"
        client.api_key = "fake"
        cancel_context = RunRequestCanceller()
        with mock.patch(
                "helper_models.call_anthropic_messages", return_value="ok") as call:
            self.assertEqual(gui._safe_chat_create(
                client, cancel_context=cancel_context,
                model="claude-haiku-4-5-20251001",
                messages=[], timeout=29), "ok")
        self.assertIs(call.call_args.kwargs["cancel_context"], cancel_context)
        self.assertEqual(call.call_args.kwargs["timeout_seconds"], 29)

    def test_gui_version_identical_behavior(self):
        client = self._make_client()
        create = self._call(
            gui._safe_chat_create,
            client,
            model="gpt-5.4-mini",
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "you are x"}],
            max_tokens=123,
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("temperature", _called_kwargs)
        self.assertNotIn("response_format", _called_kwargs)
        self.assertEqual(_called_kwargs["messages"][0]["role"], "developer")
        self.assertNotIn("max_tokens", _called_kwargs)
        self.assertEqual(
            _called_kwargs["max_completion_tokens"],
            ht.REASONING_MIN_COMPLETION_TOKENS)

    def test_gui_o4_matches_hybrid_behavior(self):
        client = self._make_client()
        create = self._call(
            gui._safe_chat_create,
            client,
            model="o4-mini",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "x"}],
            max_tokens=77,
        )
        _called_kwargs = create.call_args[1]
        self.assertNotIn("response_format", _called_kwargs)
        self.assertEqual(_called_kwargs["messages"][0]["role"], "developer")
        self.assertEqual(
            _called_kwargs["max_completion_tokens"],
            ht.REASONING_MIN_COMPLETION_TOKENS)
