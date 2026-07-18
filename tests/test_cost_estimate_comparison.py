"""_show_cost_estimate — mevcut plan vs gpt-5.4 (Batch, %50 indirimli) karşılaştırma satırı.

NEDEN: A/B testi (2026-07-10) desync/cue-kayma sınıfının YALNIZCA gpt-5.4-full ana
model olduğunda ortadan kalktığını kanıtladı (bkz. mini-main-model-quality-2026-07
hafızası). Kullanıcının maliyet penceresinde bu alternatifi görmesi, dosya başına
'hangi model?' kararını veriye dayandırır."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui
from tests._gui_app import make_app


class CostEstimateComparisonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def _write_srt(self, td, n_lines=20):
        p = Path(td) / "f.srt"
        body = []
        for i in range(1, n_lines + 1):
            body.append(f"{i}\n00:00:{i:02d},000 --> 00:00:{i+1:02d},000\n"
                       f"Bu satır maliyet hesabı için yeterince uzun bir örnek metindir.\n")
        p.write_text("\n".join(body), encoding="utf-8")
        return p

    def test_comparison_line_shown_when_main_model_not_gpt54(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td)
            self.app.model_var.set("gpt-5.4-mini")
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            mock_info.assert_called_once()
            _, body = mock_info.call_args[0]
            self.assertIn("Karşılaştırma", body)
            self.assertIn("gpt-5.4 (Batch, %50 indirimli)", body)
            self.assertIn("Mevcut plan (gpt-5.4-mini)", body)

    def test_comparison_line_omitted_when_main_model_already_gpt54(self):
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td)
            self.app.model_var.set("gpt-5.4")
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            _, body = mock_info.call_args[0]
            self.assertNotIn("Karşılaştırma", body,
                             "zaten gpt-5.4 iken kendisiyle karşılaştırma gösterilmemeli")

    def test_alt_total_uses_batch_discount_on_main_only(self):
        # Alternatif toplam = (gpt-5.4 ana çeviri maliyeti * 0.5) + (mevcut geçiş
        # maliyetleri, ANA MODELDEN bağımsız — indirim SADECE ana çeviriye uygulanır).
        with tempfile.TemporaryDirectory() as td:
            f = self._write_srt(td, n_lines=200)   # büyütülmüş fark net görünsün
            self.app.model_var.set("gpt-5.4-mini")
            self.app.critic_var.set(False)
            self.app.polish_var.set(False)
            self.app.qc_var.set(False)
            self.app.native_var.set(False)
            self.app.hybrid_var.set(False)
            with patch.object(self.app, "_get_srt_files", return_value=[str(f)]), \
                 patch("subtitle_translator_gui.messagebox.showinfo") as mock_info:
                self.app._show_cost_estimate()
            _, body = mock_info.call_args[0]
            # Yardımcı geçişler kapalıyken alternatif toplam yalnızca gpt-5.4
            # batch ana-çeviri maliyeti olmalı; mini'nin ~5x daha ucuz olduğu
            # düşünülünce alternatif rakam mevcut plandan BÜYÜK olmalı.
            import re
            m_plan = re.search(r"Mevcut plan.*?~\$([\d.]+)", body)
            m_alt = re.search(r"Alternatif.*?~\$([\d.]+)", body)
            self.assertIsNotNone(m_plan)
            self.assertIsNotNone(m_alt)
            self.assertGreater(float(m_alt.group(1)), float(m_plan.group(1)))


if __name__ == "__main__":
    unittest.main()
