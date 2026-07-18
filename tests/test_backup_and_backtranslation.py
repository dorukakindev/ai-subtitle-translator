"""
Ham çeviri yedeği (.ham.srt) + Geri Çeviri Anlam Kontrolü (rapor-only).

- _save_raw_backup: toggle açıkken <stem>.ham.srt yazar, kapalıyken yazmaz.
- back_translation_check: prefilter ([HATA]/çok kısa/etiket-only) hepsini elerse
  API'ye GİTMEDEN [] döner (ağ gerektirmeyen yol).
"""
import os
import tempfile
import unittest

import subtitle_translator_gui as gui
import hybrid_translate as ht
from tests._gui_app import make_app

_TS = "00:00:01,000 --> 00:00:02,000"


class RawBackupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_writes_ham_srt_when_on(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var.set(True)
        self.app._save_raw_backup(out, [("1", _TS, "Merhaba")], {"1": "Hello"})
        self.assertTrue(os.path.exists(os.path.join(d, "movie.ham.srt")))

    def test_skips_when_off(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var.set(False)
        try:
            self.app._save_raw_backup(out, [("1", _TS, "x")], {"1": "y"})
            self.assertFalse(os.path.exists(os.path.join(d, "movie.ham.srt")))
        finally:
            self.app.backup_raw_var.set(True)   # varsayılanı geri al

    def test_backup_unaffected_by_later_pass_mutation(self):
        # Ham snapshot (list kopyası) sonradan pass'ler listeyi değiştirse de korunur
        d = tempfile.mkdtemp()
        out = os.path.join(d, "m.srt")
        raw = [("1", _TS, "ham metin")]
        snapshot = list(raw)            # akışlardaki _raw_backup_blocks ile aynı desen
        raw[0] = ("1", _TS, "DEĞİŞTİ")  # bir pass yeniden atadı
        self.app.backup_raw_var.set(True)
        self.app._save_raw_backup(out, snapshot, {"1": "raw text"})
        with open(os.path.join(d, "m.ham.srt"), encoding="utf-8") as fh:
            self.assertIn("ham metin", fh.read())


class BackTranslationPrefilterTest(unittest.TestCase):
    def test_empty_src_map_returns_empty(self):
        self.assertEqual(ht.back_translation_check({}, [("1", _TS, "Merhaba dünya")], api_key="x"), [])

    def test_all_filtered_no_network(self):
        # [HATA] + çok kısa (<12 öz karakter) + bracket-only → hepsi elenir → ağsız []
        blocks = [("1", _TS, "[HATA]"), ("2", _TS, "Tamam"), ("3", _TS, "[KAHKAHA]")]
        src = {"1": "whatever", "2": "Okay", "3": "[LAUGHS]"}
        self.assertEqual(ht.back_translation_check(src, blocks, api_key="x"), [])


if __name__ == "__main__":
    unittest.main()
