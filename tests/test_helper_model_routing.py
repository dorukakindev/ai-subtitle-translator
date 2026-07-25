import unittest


class HelperModelRoutingTest(unittest.TestCase):
    def test_anthropic_message_url_normalizes_native_and_proxy_bases(self):
        from helper_models import _anthropic_messages_url

        self.assertEqual(_anthropic_messages_url("https://api.anthropic.com"),
                         "https://api.anthropic.com/v1/messages")
        self.assertEqual(_anthropic_messages_url("https://api.anthropic.com/v1"),
                         "https://api.anthropic.com/v1/messages")
        self.assertEqual(_anthropic_messages_url("https://api.anthropic.com/v1/messages"),
                         "https://api.anthropic.com/v1/messages")
        self.assertEqual(_anthropic_messages_url("https://opencode.ai/zen/go/v1/messages"),
                         "https://opencode.ai/zen/go/v1/messages")

    def test_deepseek_v4_flash_routes_to_deepseek_api(self):
        from helper_models import resolve_helper_model

        cfg = resolve_helper_model("DeepSeek V4 Flash")

        self.assertEqual(cfg.provider, "deepseek")
        self.assertEqual(cfg.model, "deepseek-v4-flash")
        self.assertEqual(cfg.base_url, "https://api.deepseek.com")

    def test_minimax_is_removed_and_routes_to_openai_gpt54_mini(self):
        # MiniMax tamamen kaldırıldı — eski seçim gpt-5.4-mini'ye (OpenAI) göç eder
        from helper_models import resolve_helper_model

        cfg = resolve_helper_model("MiniMax M2.7")

        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-5.4-mini")
        self.assertEqual(cfg.base_url, "https://api.openai.com/v1")

    def test_legacy_minimax_not_in_helper_options_but_opencode_go_m3_is_available(self):
        from helper_models import HELPER_MODEL_OPTIONS

        joined = " ".join(HELPER_MODEL_OPTIONS).lower()
        self.assertIn("minimax m3 (opencode go)", joined)
        self.assertNotIn("minimax m2.7", joined)
        self.assertNotIn("minimax m1", joined)
        self.assertNotIn("abab", joined)
        self.assertIn("gpt-5.4-mini", HELPER_MODEL_OPTIONS)

    def test_legacy_minimax_setting_migrates_to_gpt54_mini(self):
        from helper_models import normalize_helper_model_label

        # Eski .gui_settings.json'da kayıtlı MiniMax değerleri gpt-5.4-mini olur
        self.assertEqual(normalize_helper_model_label("MiniMax-M2.7"), "gpt-5.4-mini")
        self.assertEqual(normalize_helper_model_label("MiniMax M1"), "gpt-5.4-mini")
        self.assertEqual(normalize_helper_model_label("abab6.5s-chat"), "gpt-5.4-mini")
        # DeepSeek ve OpenAI seçenekleri etkilenmez
        self.assertEqual(normalize_helper_model_label("deepseek-v4-flash"), "DeepSeek V4 Flash")
        self.assertEqual(normalize_helper_model_label("gpt-5.4-mini"), "gpt-5.4-mini")

    def test_opencode_go_minimax_m3_routes_to_anthropic_messages_endpoint(self):
        from helper_models import HELPER_MODEL_OPTIONS, normalize_helper_model_label, resolve_helper_model

        cfg = resolve_helper_model("MiniMax M3 (OpenCode Go)")

        self.assertIn("MiniMax M3 (OpenCode Go)", HELPER_MODEL_OPTIONS)
        self.assertEqual(normalize_helper_model_label("opencode-go/minimax-m3"), "MiniMax M3 (OpenCode Go)")
        self.assertEqual(normalize_helper_model_label("minimax-m3"), "MiniMax M3 (OpenCode Go)")
        self.assertEqual(cfg.provider, "anthropic")
        self.assertEqual(cfg.model, "minimax-m3")
        self.assertEqual(cfg.base_url, "https://opencode.ai/zen/go/v1/messages")

    def test_opencode_go_glm52_routes_to_openai_compatible_endpoint(self):
        from helper_models import HELPER_MODEL_OPTIONS, normalize_helper_model_label, resolve_helper_model

        cfg = resolve_helper_model("GLM-5.2 (OpenCode Go)")

        self.assertIn("GLM-5.2 (OpenCode Go)", HELPER_MODEL_OPTIONS)
        self.assertEqual(normalize_helper_model_label("opencode-go/glm-5.2"), "GLM-5.2 (OpenCode Go)")
        self.assertEqual(normalize_helper_model_label("glm-5.2"), "GLM-5.2 (OpenCode Go)")
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "glm-5.2")
        self.assertEqual(cfg.base_url, "https://opencode.ai/zen/go/v1")

    def test_opencode_go_qwen37_max_routes_to_anthropic_messages_endpoint(self):
        from helper_models import HELPER_MODEL_OPTIONS, normalize_helper_model_label, resolve_helper_model

        cfg = resolve_helper_model("Qwen3.7 Max (OpenCode Go)")

        self.assertIn("Qwen3.7 Max (OpenCode Go)", HELPER_MODEL_OPTIONS)
        self.assertEqual(normalize_helper_model_label("opencode-go/qwen3.7-max"), "Qwen3.7 Max (OpenCode Go)")
        self.assertEqual(normalize_helper_model_label("qwen3.7-max"), "Qwen3.7 Max (OpenCode Go)")
        self.assertEqual(cfg.provider, "anthropic")
        self.assertEqual(cfg.model, "qwen3.7-max")
        self.assertEqual(cfg.base_url, "https://opencode.ai/zen/go/v1/messages")

    def test_bedrock_models_route_to_bedrock_provider(self):
        from helper_models import resolve_helper_model, normalize_helper_model_label

        cfg = resolve_helper_model("Bedrock Claude 4.6 Sonnet")
        self.assertEqual(cfg.provider, "bedrock")
        self.assertEqual(cfg.model, "anthropic.claude-sonnet-4-6")
        self.assertEqual(cfg.base_url, "https://bedrock.dummy")

        cfg35 = resolve_helper_model("Bedrock Claude 3.5 Sonnet")
        self.assertEqual(cfg35.provider, "bedrock")
        self.assertEqual(cfg35.model, "anthropic.claude-3-5-sonnet-20241022-v2:0")

        cfgllama = resolve_helper_model("Bedrock Llama 3.3 70B")
        self.assertEqual(cfgllama.provider, "bedrock")
        self.assertEqual(cfgllama.model, "meta.llama3-3-70b-instruct-v1:0")

        # Aliases check
        self.assertEqual(normalize_helper_model_label("bedrock-claude-4.6-sonnet"), "Bedrock Claude 4.6 Sonnet")
        self.assertEqual(normalize_helper_model_label("anthropic.claude-sonnet-4-6"), "Bedrock Claude 4.6 Sonnet")
        self.assertEqual(normalize_helper_model_label("bedrock-claude-3.5-sonnet"), "Bedrock Claude 3.5 Sonnet")
        self.assertEqual(normalize_helper_model_label("bedrock claude 3 haiku"), "Bedrock Claude 3 Haiku")
        self.assertEqual(normalize_helper_model_label("bedrock-claude-3-5-haiku"), "Bedrock Claude 3.5 Haiku")
        self.assertEqual(normalize_helper_model_label("bedrock-llama-3.3-70b"), "Bedrock Llama 3.3 70B")
        self.assertEqual(normalize_helper_model_label("meta.llama3-3-70b-instruct-v1:0"), "Bedrock Llama 3.3 70B")

    def test_gemini_models_route_to_openai_provider_with_correct_url(self):
        from helper_models import resolve_helper_model, normalize_helper_model_label

        cfg35 = resolve_helper_model("Gemini 3.5 Flash")
        self.assertEqual(cfg35.provider, "openai")
        self.assertEqual(cfg35.model, "gemini-3.5-flash")
        self.assertEqual(cfg35.base_url, "https://generativelanguage.googleapis.com/v1beta/openai/")

        cfg25 = resolve_helper_model("Gemini 2.5 Flash")
        self.assertEqual(cfg25.provider, "openai")
        self.assertEqual(cfg25.model, "gemini-2.5-flash")
        self.assertEqual(cfg25.base_url, "https://generativelanguage.googleapis.com/v1beta/openai/")

        # Aliases and redirection of 3.0 to 3.5
        self.assertEqual(normalize_helper_model_label("gemini-3.0-flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini 3.0 flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini_3.0_flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini 3 flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini-3-flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini-3.5-flash"), "Gemini 3.5 Flash")
        self.assertEqual(normalize_helper_model_label("gemini-2.5-flash"), "Gemini 2.5 Flash")

    def test_reseller_gpt54_preset_routes_to_shuaiapi(self):
        # Kullanıcı Analiz/Polish/Critic rollerinde tek tıkla reseller'a geçebilsin
        # diye eklenen hazır seçenek — "Özel (Custom)" alanlarını elle doldurmaya gerek yok.
        from helper_models import HELPER_MODEL_OPTIONS, normalize_helper_model_label, resolve_helper_model

        cfg = resolve_helper_model("GPT-5.4 (Reseller)")

        self.assertIn("GPT-5.4 (Reseller)", HELPER_MODEL_OPTIONS)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-5.4")
        self.assertEqual(cfg.base_url, "https://api.shuaiapi.com/v1")
        self.assertEqual(normalize_helper_model_label("reseller gpt-5.4"), "GPT-5.4 (Reseller)")
        self.assertEqual(normalize_helper_model_label("gpt-5.4-reseller"), "GPT-5.4 (Reseller)")

    def test_claude_haiku_routes_to_147ai_anthropic_messages(self):
        from helper_models import HELPER_MODEL_OPTIONS, resolve_helper_model

        cfg = resolve_helper_model("claude-haiku-4-5-20251001")

        self.assertIn("claude-haiku-4-5-20251001", HELPER_MODEL_OPTIONS)
        self.assertEqual(cfg.provider, "anthropic")
        self.assertEqual(cfg.model, "claude-haiku-4-5-20251001")
        self.assertEqual(cfg.base_url, "https://147ai.online/v1/messages")


class AnthropicAuthHeaderTest(unittest.TestCase):
    """Regression: call_anthropic_messages'ın URL'den auth header çıkarımı.

    /v1/messages uçnoktaları (OpenCode Go, 147ai, vb.) x-api-key bekler.
    /v1 base URL'leri de x-api-key bekler (Anthropic native). Diğer proxy'ler Bearer."""

    def _header_for(self, base_url: str):
        import helper_models
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            # urllib normalizes header capitalization; capture via header_items
            captured["headers"] = dict(req.header_items())
            import json as _json
            body = _json.dumps({
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }).encode("utf-8")

            class _BytesResp:
                def __init__(self, b): self._b = b
                def read(self): return self._b
                def __enter__(self): return self
                def __exit__(self, *a): return False

            return _BytesResp(body)

        import urllib.request as _ur
        orig = _ur.urlopen
        _ur.urlopen = fake_urlopen
        try:
            helper_models.call_anthropic_messages(
                model_id="m", messages=[{"role": "user", "content": "x"}],
                api_key_str="sk-test", base_url=base_url,
            )
        finally:
            _ur.urlopen = orig
        return {k.lower(): v for k, v in captured["headers"].items()}

    def test_opencode_go_messages_endpoint_uses_x_api_key(self):
        h = self._header_for("https://opencode.ai/zen/go/v1/messages")
        self.assertEqual(h.get("x-api-key"), "sk-test")
        self.assertNotIn("Authorization", h)

    def test_147ai_messages_endpoint_uses_x_api_key(self):
        h = self._header_for("https://147ai.online/v1/messages")
        self.assertEqual(h.get("x-api-key"), "sk-test")
        self.assertNotIn("Authorization", h)

    def test_native_anthropic_v1_uses_x_api_key(self):
        h = self._header_for("https://api.anthropic.com/v1")
        self.assertEqual(h.get("x-api-key"), "sk-test")
        self.assertNotIn("Authorization", h)

    def test_native_anthropic_v1_messages_uses_x_api_key(self):
        h = self._header_for("https://api.anthropic.com/v1/messages")
        self.assertEqual(h.get("x-api-key"), "sk-test")
        self.assertNotIn("Authorization", h)

    def test_proxy_without_messages_path_uses_bearer(self):
        h = self._header_for("https://my-anthropic-proxy.example.com/api")
        self.assertEqual(h.get("authorization"), "Bearer sk-test")
        self.assertNotIn("x-api-key", h)


if __name__ == "__main__":
    unittest.main()
