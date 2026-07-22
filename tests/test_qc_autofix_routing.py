"""
Deterministic unit tests for QC auto-fix provider/model/key routing audit.
Directly invokes production functions and App method call sites with stub objects.
Does NOT instantiate App() or make network calls.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class QCAutoFixRoutingTest(unittest.TestCase):

    def setUp(self):
        self.sample_issues = [
            {
                "id": "1",
                "original": "Good morning.",
                "current": "Günaydın.",
                "problem": "Formatting error",
                "suggestion": "Günaydın!",
                "severity": "low",
            }
        ]
        self.sample_blocks = [(1, "00:00:01,000 --> 00:00:03,000", "Günaydın.")]

    def test_qc_auto_fix_uses_helper_api_key_and_custom_provider(self):
        """Verify ht.qc_auto_fix routes through _safe_chat_create using the helper key/model/url."""
        with patch("hybrid_translate._safe_chat_create") as mock_safe_create:
            mock_resp = MagicMock()
            mock_resp.choices = [SimpleNamespace(message=SimpleNamespace(content="Günaydın!"))]
            mock_safe_create.return_value = mock_resp

            result = ht.qc_auto_fix(
                issues=self.sample_issues,
                tr_blocks=self.sample_blocks,
                helper_api_key="sk-qc-helper-key",
                model="claude-3-5-sonnet",
                base_url="https://api.anthropic.com/v1",
                tgt_lang="Turkish",
            )

            # _safe_chat_create should be called once with correct model
            mock_safe_create.assert_called_once()
            client_used = mock_safe_create.call_args[0][0]
            model_used = mock_safe_create.call_args[1].get("model")

            self.assertEqual(client_used.api_key, "sk-qc-helper-key")
            self.assertEqual(str(client_used.base_url).rstrip("/"), "https://api.anthropic.com/v1")
            self.assertEqual(model_used, "claude-3-5-sonnet")
            self.assertEqual(result[0][2], "Günaydın!")

    def test_app_qc_auto_fix_call_sites_parity(self):
        """Verify that stub App methods pass helper_api_key('qc'), helper_api_model('qc'), and helper_api_base_url('qc')."""
        # Create a stub App that simulates the GUI helper resolvers
        stub = SimpleNamespace(
            _main_api_key=lambda: "sk-MAIN-MODEL-KEY-MUST-NOT-LEAK",
            _main_model_name=lambda: "main-model-must-not-leak",
            _helper_api_key=lambda r: "sk-QC-HELPER-KEY" if r == "qc" else "sk-OTHER-KEY",
            _helper_api_model=lambda r: "qc-helper-model-v1" if r == "qc" else "other-model",
            _helper_api_base_url=lambda r: "https://qc.endpoint.ai/v1" if r == "qc" else "https://other.ai/v1",
            _log=lambda *args, **kwargs: None,
            _log_exc=lambda *args, **kwargs: None,
            _write_qc_change_report=lambda *args, **kwargs: None,
            _show_qc_dialog=lambda *args, **kwargs: None,
            _dismiss_modal_dialog=lambda *args, **kwargs: None,
            _stop_flag=False,
            after=lambda ms, fn: None,
        )

        call_records = []

        def mock_qc_auto_fix(**kwargs):
            call_records.append(kwargs)
            return kwargs.get("tr_blocks", [])

        with patch("hybrid_translate.quality_check_with_helper", return_value=self.sample_issues), \
             patch("hybrid_translate.qc_auto_fix", side_effect=mock_qc_auto_fix):
            gui.App._run_quality_check_inline(
                stub,
                fp="test.srt",
                orig_cues=[],
                blocks=self.sample_blocks,
                mm_key="sk-MAIN-KEY",
                mm_url="https://api.openai.com/v1",
                mm_model="main-model",
                tgt="Turkish",
            )

        self.assertGreaterEqual(len(call_records), 1)
        for rec in call_records:
            self.assertEqual(rec.get("helper_api_key"), "sk-QC-HELPER-KEY",
                             "qc_auto_fix must receive QC helper key, NOT main model key")
            self.assertEqual(rec.get("model"), "qc-helper-model-v1",
                             "qc_auto_fix must receive QC helper model, NOT main model name")
            self.assertEqual(rec.get("base_url"), "https://qc.endpoint.ai/v1")
            self.assertNotEqual(rec.get("helper_api_key"), "sk-MAIN-MODEL-KEY-MUST-NOT-LEAK")
            self.assertNotEqual(rec.get("model"), "main-model-must-not-leak")

    def test_main_key_never_leaks_in_batch_or_sync_hybrid_flows(self):
        """Verify in source code that main model key/model are not passed to ht.qc_auto_fix across any flow."""
        import inspect

        methods_to_check = [
            ("_run_quality_check_inline", gui.App._run_quality_check_inline),
            ("_wait_batch_hybrid", gui.App._wait_batch_hybrid),
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
        ]

        total_qc_calls_checked = 0
        for name, method in methods_to_check:
            src = inspect.getsource(method)
            lines = src.splitlines()
            for i, line in enumerate(lines):
                if "ht.qc_auto_fix(" in line:
                    total_qc_calls_checked += 1
                    block = "\n".join(lines[i:i+12])
                    self.assertNotIn("openai_api_key=self._main_api_key()", block,
                                     f"Main API key leaked in {name}")
                    self.assertNotIn("openai_api_key=api_key", block,
                                     f"Main API key leaked in {name}")
                    self.assertNotIn("openai_api_key=openai_key", block,
                                     f"Main API key leaked in {name}")
                    self.assertNotIn("model=self._main_model_name()", block,
                                     f"Main model leaked in {name}")
                    self.assertNotIn("model=\"gpt-5.4-mini\"", block,
                                     f"Hardcoded main/helper model leaked in {name}")
                    self.assertIn("helper_api_key=self._helper_api_key(\"qc\")", block,
                                  f"QC helper key missing in {name}")
                    self.assertIn("model=self._helper_api_model(\"qc\")", block,
                                  f"QC helper model missing in {name}")

        self.assertEqual(total_qc_calls_checked, 6, "Expected exactly 6 ht.qc_auto_fix calls across execution flows")


if __name__ == "__main__":
    unittest.main()
