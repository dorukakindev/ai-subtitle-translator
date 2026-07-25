import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class _Var:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class TokenCostRoutingTest(unittest.TestCase):
    def _app(self):
        return SimpleNamespace(
            _token_lock=threading.Lock(),
            _token_total=0,
            _token_cached=0,
            _cost_total=0.0,
            _unknown_cost_tokens=0,
            _token_sparkline_points=[],
            stat_tokens_var=_Var(),
            stat_tokens_sub_var=_Var(),
            _main_model_name=lambda: "gpt-5.4",
            _update_token_sparkline=lambda: None,
        )

    def test_mixed_models_keep_their_own_prices(self):
        app = self._app()
        app._update_tokens = lambda added, price=gui._DEFAULT_TOKEN_PRICE, cached=0: (
            gui.App._update_tokens(app, added, price, cached)
        )
        with patch.object(gui, "_post_ui", side_effect=lambda _app, fn: fn()):
            gui.App._update_tokens(app, 1_000_000)
            gui.App._token_callback_for_model(
                app, "gpt-5.4-mini")(1_000_000)
            gui.App._token_callback_for_model(
                app, "gpt-4o-mini")(1_000_000)

        self.assertAlmostEqual(app._cost_total, 30.23, places=6)
        self.assertEqual(app._unknown_cost_tokens, 0)

    def test_unknown_model_tokens_are_marked_not_guessed(self):
        app = self._app()
        app._update_tokens = lambda added, price=gui._DEFAULT_TOKEN_PRICE, cached=0: (
            gui.App._update_tokens(app, added, price, cached)
        )
        with patch.object(gui, "_post_ui", side_effect=lambda _app, fn: fn()):
            gui.App._token_callback_for_model(
                app, "vendor-model-without-price")(1234)

        self.assertEqual(app._cost_total, 0.0)
        self.assertEqual(app._unknown_cost_tokens, 1234)
        self.assertIn("fiyatı bilinmiyor", app.stat_tokens_sub_var.value)


if __name__ == "__main__":
    unittest.main()
