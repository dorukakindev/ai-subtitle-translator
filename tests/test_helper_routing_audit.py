"""
Unit tests for helper model / provider routing audit.
Directly invokes production functions from helper_models, hybrid_translate,
and subtitle_translator_gui (via class methods/stubs, NO App() instantiation).
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import helper_models
import hybrid_translate as ht
import subtitle_translator_gui as gui


class HelperRoutingAuditTests(unittest.TestCase):

    def test_claim1_polish_pass_in_sync_hybrid_uses_polish_key(self):
        """Claim 1: Verify Polish Pass in _write_results and _run_sync_hybrid resolves 'polish' key, not 'analysis'."""
        import inspect
        src_wr = inspect.getsource(gui.App._write_results)
        src_sh = inspect.getsource(gui.App._run_sync_hybrid)
        self.assertIn('self._helper_api_key("polish")', src_wr)
        self.assertIn('self._helper_api_key("polish")', src_sh)

    def test_claim1_qc_fix_uses_qc_role(self):
        """Claim 1: Verify _maybe_backtranslation_check fix mode uses 'qc' role first."""
        import inspect
        src = inspect.getsource(gui.App._maybe_backtranslation_check)
        self.assertIn('fix_key = self._helper_api_key("qc")', src,
                      "_maybe_backtranslation_check fix mode must use _helper_api_key('qc')")

    def test_helper_api_key_uses_general_helper_key_for_non_openai_provider(self):
        """The shared helper key is the documented fallback for every helper provider."""
        helper_entry = SimpleNamespace(get=lambda: "shared-helper-key")
        api_entry = SimpleNamespace(get=lambda: "sk-proj-main-key")
        
        stub = SimpleNamespace(
            helper_role_key_vars={},
            helper_custom_key_vars={},
            _helper_keys_cache={},
            helper_key_entry=helper_entry,
            api_key_entry=api_entry,
            _get_current_helper_provider=lambda role: "anthropic" if role == "critic" else "openai",
        )
        
        anthropic_key = gui.App._helper_api_key(stub, "critic")
        self.assertEqual(anthropic_key, "shared-helper-key")

        openai_key = gui.App._helper_api_key(stub, "analysis")
        self.assertEqual(openai_key, "shared-helper-key")

    def test_helper_api_key_does_not_leak_main_openai_key_to_anthropic(self):
        """Only an OpenAI helper role may fall back to the main OpenAI key."""
        stub = SimpleNamespace(
            helper_role_key_vars={},
            helper_custom_key_vars={},
            _helper_keys_cache={},
            helper_key_entry=SimpleNamespace(get=lambda: ""),
            api_key_entry=SimpleNamespace(get=lambda: "sk-proj-main-key"),
            _get_current_helper_provider=lambda role: "anthropic" if role == "critic" else "openai",
        )

        self.assertEqual(gui.App._helper_api_key(stub, "critic"), "")
        self.assertEqual(gui.App._helper_api_key(stub, "analysis"), "sk-proj-main-key")

    def test_claim3_native_reader_call_sites_use_critic_role_consistently(self):
        """Claim 3: All native_reader_pass calls in GUI must use 'critic' role."""
        import inspect
        src = inspect.getsource(gui.App)
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if "native_reader_pass(" in line:
                chunk = " ".join(lines[i:i+6])
                if "helper_api_key=" in chunk:
                    self.assertTrue(
                        'helper_api_key=self._helper_api_key("critic")' in chunk
                        or 'helper_api_key=helper_keys.get("critic", "")' in chunk,
                        f"native_reader_pass call site must use 'critic' role: {chunk}",
                    )

    def test_plain_batch_native_counts_critic_tokens_and_condense_uses_analysis(self):
        import inspect
        src = inspect.getsource(gui.App._write_results)
        native_at = src.index("sorted_blocks = ht.native_reader_pass(")
        native_call = src[native_at:src.index("_record_pass_change", native_at)]
        self.assertIn('token_callback=self._token_callback_for_model(', native_call)
        self.assertIn('self._helper_api_model("critic")', native_call)

        condense_at = src.index("sorted_blocks = self._maybe_condense(")
        condense_call = src[condense_at:src.index("if self.clean_sdh_var.get()", condense_at)]
        self.assertIn('self._helper_api_key("analysis")', condense_call)
        self.assertIn('self._helper_api_base_url("analysis")', condense_call)
        self.assertIn('self._helper_api_model("analysis")', condense_call)
        self.assertNotIn('self._helper_api_key("qc")', condense_call)

    def test_native_validation_and_cost_use_critic_role(self):
        import inspect
        validate_src = inspect.getsource(gui.App._validate)
        cost_src = inspect.getsource(gui.App._show_cost_estimate)
        self.assertIn(
            'if self.native_var.get():                  roles.append("critic")',
            validate_src,
        )
        self.assertIn(
            'nt_m = self._helper_api_model("critic")',
            cost_src,
        )
        self.assertIn(
            'qc_m = self._helper_api_model("qc")',
            cost_src,
        )
        self.assertIn("Native Reader", cost_src)
        self.assertIn("QC Pass", cost_src)
        self.assertNotIn("QC / Native Pass", cost_src)

    def test_resume_native_and_qc_receive_loaded_analysis(self):
        import inspect
        src = inspect.getsource(gui.App._wait_batch_hybrid)
        native_at = src.index("pp = ht.native_reader_pass(")
        native_call = src[native_at:src.index(
            "_record_pass_change", native_at
        )]
        qc_at = src.index("_issues = ht.quality_check_with_helper(")
        qc_call = src[qc_at:src.index("if _issues:", qc_at)]
        self.assertIn("analysis_result=_analysis_result", native_call)
        self.assertIn("analysis_result=_analysis_result", qc_call)

    def test_claim7_8_safe_chat_create_respects_explicit_openai_provider(self):
        """Claim 7 & 8: Reseller OpenAI model with 'claude' name or /messages URL must not be forced to Anthropic."""
        for safe_create in (ht._safe_chat_create, gui._safe_chat_create):
            with self.subTest(safe_create=safe_create.__module__):
                mock_client = MagicMock()
                mock_client.base_url = "https://api.shuaiapi.com/v1/messages"
                mock_client.api_key = "sk-reseller-key"

                with patch.object(mock_client.chat.completions, "create") as mock_create:
                    mock_create.return_value = SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="OK"))],
                        usage=None
                    )
                    resp = safe_create(
                        mock_client,
                        model="claude-sonnet-5",
                        messages=[{"role": "user", "content": "Hi"}],
                    )

                    mock_create.assert_called_once()
                    self.assertEqual(resp.choices[0].message.content, "OK")

    def test_claim9_call_anthropic_messages_strips_chat_completions_suffix(self):
        """Claim 9: base_url ending with /chat/completions must be properly formatted to /messages."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"content": [{"type": "text", "text": "Hello"}], "usage": {"input_tokens": 10, "output_tokens": 5}}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp
            
            resp = helper_models.call_anthropic_messages(
                model_id="claude-3-haiku",
                messages=[{"role": "user", "content": "Hi"}],
                api_key_str="test-key",
                base_url="https://custom.proxy.com/v1/chat/completions"
            )
            
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.full_url, "https://custom.proxy.com/v1/messages")
            self.assertEqual(resp.choices[0].message.content, "Hello")

    def test_claim5_dummy_usage_has_openai_attributes(self):
        """Claim 5: DummyUsage in Anthropic/Bedrock responses must provide prompt_tokens and completion_tokens."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"content": [{"type": "text", "text": "Hi"}], "usage": {"input_tokens": 12, "output_tokens": 8}}'
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp
            
            resp = helper_models.call_anthropic_messages("claude-haiku", [{"role": "user", "content": "test"}], api_key_str="key")
            self.assertEqual(resp.usage.input_tokens, 12)
            self.assertEqual(resp.usage.output_tokens, 8)
            self.assertEqual(resp.usage.prompt_tokens, 12)
            self.assertEqual(resp.usage.completion_tokens, 8)
            self.assertEqual(resp.usage.total_tokens, 20)


if __name__ == "__main__":
    unittest.main()
