"""_log_startup_settings — açılışta girdi/çıktı/mod TEK log satırında görünür olsun.

NEDEN (2026-07-17): kullanıcının .gui_settings.json'ı fabrika varsayılanlarına dönmüş
bulundu ama HANGİ oturumun bunu kaydettiğini kanıtlayacak iz yoktu. Bu log satırı
sonraki olayda "hangi klasörle açıldı" sorusunu loglardan anında cevaplar."""
import unittest

import subtitle_translator_gui as gui
from tests._gui_app import make_app


class LogStartupSettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def _capture(self, note=""):
        captured = []
        orig = self.app._log
        self.app._log = lambda m, t="": captured.append((m, t))
        try:
            self.app._log_startup_settings(note)
        finally:
            self.app._log = orig
        return captured

    def test_logs_input_output_mode(self):
        self.app.input_var.set(r"C:\in")
        self.app.output_var.set(r"C:\out")
        self.app.mode_var.set("batch")
        self.app.hybrid_var.set(True)
        logs = self._capture()
        self.assertEqual(len(logs), 1)
        msg, tag = logs[0]
        self.assertIn(r"C:\in", msg)
        self.assertIn(r"C:\out", msg)
        self.assertIn("batch", msg)
        self.assertIn("hybrid", msg)
        self.assertEqual(tag, "info")

    def test_note_appended(self):
        logs = self._capture("(ayar dosyası yok, varsayılanlar)")
        self.assertIn("varsayılanlar", logs[0][0])

    def test_no_settings_file_still_logs(self):
        # _load_settings dosya yokken de _log_startup_settings çağırmalı (not ile).
        import tempfile
        from pathlib import Path
        captured = []
        orig_log = self.app._log
        orig_path = self.app._settings_path
        self.app._log = lambda m, t="": captured.append((m, t))
        try:
            with tempfile.TemporaryDirectory() as td:
                self.app._settings_path = lambda: Path(td) / "yok.json"
                self.app._load_settings()
        finally:
            self.app._log = orig_log
            self.app._settings_path = orig_path
        self.assertTrue(any("Ayarlar yüklendi" in m for m, _ in captured))
        self.assertTrue(any("varsayılanlar" in m for m, _ in captured))


if __name__ == "__main__":
    unittest.main()
