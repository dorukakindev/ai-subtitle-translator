import threading
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class ProviderCostTransparencyTest(unittest.TestCase):
    def test_only_official_openai_route_gets_local_usd_price(self):
        self.assertTrue(gui._is_official_openai_api_route("https://api.openai.com/v1"))
        self.assertFalse(gui._is_official_openai_api_route("https://reseller.example/v1"))
        self.assertEqual(
            gui._verified_token_price("gpt-5.4", "https://api.openai.com/v1"),
            gui.MODEL_PRICE["gpt-5.4"],
        )
        self.assertIsNone(
            gui._verified_token_price("gpt-5.4", "https://reseller.example/v1"))

    def test_reseller_callback_marks_cost_unknown_and_missing_usage(self):
        record = {"files": {}, "api": {}}
        app = SimpleNamespace(
            _active_snapshot={
                "helper_models": {"critic": "gpt-5.4"},
                "helper_urls": {"critic": "https://reseller.example/v1"},
            },
            _token_lock=threading.Lock(),
            _run_record_lock=threading.Lock(),
            _active_run_record=record,
            _token_total=0,
            _token_cached=0,
            _unknown_cost_tokens=0,
            _cost_total=0.0,
            _token_sparkline_points=[],
            _main_model_name=lambda: "gpt-5.4",
            _update_token_sparkline=lambda: None,
        )
        callback = gui.App._token_callback_for_model(
            app, "gpt-5.4", pass_name="Critic Pass")
        callback(120)
        callback.report_missing_usage()

        self.assertEqual(app._unknown_cost_tokens, 120)
        self.assertEqual(app._cost_total, 0.0)
        usage = record["api"]["usage_by_pass"]["Critic Pass"]
        self.assertEqual(usage["unknown_cost_tokens"], 120)
        self.assertEqual(usage["usage_missing_responses"], 1)


if __name__ == "__main__":
    unittest.main()
