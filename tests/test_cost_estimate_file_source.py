"""_show_cost_estimate (subtitle_translator_gui.py) — canlı çeviri sırasında kullanıcının
karşılaştığı gerçek çökme: 'Maliyet Tahmini' butonu `self.file_listbox` diye VAR OLMAYAN
bir widget'a erişiyordu (muhtemelen eski bir arayüzden kalma ölü kod — dosyada bu isimde
bir widget hiç tanımlanmamış). Düzeltme: dosya listesi için zaten var olan `_get_srt_files()`
kullanılır (seçili dosyalar ya da girdi klasöründeki dosyalar — diğer akışlarla aynı kaynak)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui
from tests._gui_app import make_app


class ShowCostEstimateFileSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_source_has_no_dead_widget_or_bad_import(self):
        # Regresyon kilidi KAYNAK düzeyinde: `hasattr(app, ...)` iddiası kırılgandı —
        # Tk kökünün __getattr__ delegasyonu, diğer test modüllerinin customtkinter
        # stub'larıyla birlikte test SIRASINA bağlı sonuç veriyordu (izolasyonda geçip
        # tam pakette kalıyordu). Niyet zaten kaynak düzeyinde: bu iki ölü referans
        # geri gelmemeli.
        src = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertNotIn("file_listbox", src,
                         "file_listbox diye bir widget hiç tanımlanmadı — ölü referans")
        self.assertNotIn("from subtitle_formats import parse_subtitle", src,
                         "parse_subtitle subtitle_formats'ta DEĞİL, bu modülde tanımlı")

    def test_does_not_crash_with_no_files_selected(self):
        # NOT: input_var'ı "" bırakmıyoruz — boş klasörle _get_srt_files() glob'u
        # '/**/*.srt'e dönüşüp TÜM SÜRÜCÜYÜ tarıyor (ayrı, mevcut bir sorun; bkz.
        # oturum notları). Burada boş bir geçici klasör kullanılır.
        self.app._selected_files = []
        with tempfile.TemporaryDirectory() as td:
            self.app.input_var.set(td)
            with patch("subtitle_translator_gui.messagebox.showwarning") as mock_warn:
                self.app._show_cost_estimate()  # AttributeError fırlatmamalı
        mock_warn.assert_called_once()

    def test_uses_get_srt_files_as_source(self):
        sentinel = ["dummy_a.srt", "dummy_b.srt"]
        with patch.object(self.app, "_get_srt_files", return_value=sentinel) as mock_get, \
             patch("subtitle_translator_gui.messagebox.showwarning") as mock_warn:
            self.app._show_cost_estimate()
        mock_get.assert_called_once()
        # Geçersiz/olmayan dosyalar parse hatası verir → "geçerli altyazı yok" uyarısı
        # (total_chars==0 dalı) — asıl kilitlenmesi gereken şey dosya KAYNAĞININ
        # _get_srt_files'tan geldiği, parse başarısı değil.
        mock_warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()
