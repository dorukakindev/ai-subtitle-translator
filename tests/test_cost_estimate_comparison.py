"""_show_cost_estimate — mevcut plan vs gpt-5.4 (Batch, %50 indirimli) karşılaştırma satırı.

NEDEN: A/B testi (2026-07-10) desync/cue-kayma sınıfının YALNIZCA gpt-5.4-full ana
model olduğunda ortadan kalktığını kanıtladı (bkz. mini-main-model-quality-2026-07
hafızası). Kullanıcının maliyet penceresinde bu alternatifi görmesi, dosya başına
'hangi model?' kararını veriye dayandırır."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class CostEstimateComparisonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = gui.App.__new__(gui.App)
        cls.app.model_var = _Var("gpt-5.4")
        cls.app.main_custom_var = _Var(False)
        cls.app.hybrid_var = _Var(False)
        cls.app.critic_var = _Var(False)
        cls.app.polish_var = _Var(False)
        cls.app.native_var = _Var(False)
        cls.app.qc_var = _Var(False)
        cls.app._log = lambda *_args, **_kwargs: None

    @classmethod
    def tearDownClass(cls):
        pass

    def _write_srt(self, td, n_lines=20):
        p = Path(td) / "f.srt"
        body = []
        for i in range(1, n_lines + 1):
            body.append(f"{i}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n"
                       f"Bu satır maliyet hesabı için yeterince uzun bir örnek metindir.\n")
        p.write_text("\n".join(body), encoding="utf-8")
        return p

    def test_custom_route_cost_is_marked_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td)
            self.app.model_var.set("gpt-5.4-mini")
            if hasattr(self.app, "main_custom_var"): self.app.main_custom_var.set(False)
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch.object(self.app, "_main_api_base_url", return_value="https://reseller.test/v1"), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            mock_info.assert_called_once()
            _, body = mock_info.call_args[0]
            self.assertIn("sağlayıcı panelinden doğrulanmalı", body)
            self.assertNotIn("Mevcut plan", body)

    def test_official_route_keeps_verified_usd_estimate(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td)
            self.app.model_var.set("gpt-5.4")
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch.object(self.app, "_main_api_base_url", return_value="https://api.openai.com/v1"), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            _, body = mock_info.call_args[0]
            self.assertIn("Ana Çeviri Modeli (gpt-5.4): ~$", body)

    def test_custom_route_never_fabricates_official_comparison_price(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td, n_lines=200)   # büyütülmüş fark net görünsün
            self.app.model_var.set("gpt-5.4-mini")
            if hasattr(self.app, "main_custom_var"): self.app.main_custom_var.set(False)
            self.app.critic_var.set(False)
            self.app.polish_var.set(False)
            self.app.qc_var.set(False)
            self.app.native_var.set(False)
            self.app.hybrid_var.set(False)
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch.object(self.app, "_main_api_base_url", return_value="https://reseller.test/v1"), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            _, body = mock_info.call_args[0]
            self.assertIn("sağlayıcı panelini kullanın", body)
            self.assertNotIn("Alternatif", body)


if __name__ == "__main__":
    unittest.main()
