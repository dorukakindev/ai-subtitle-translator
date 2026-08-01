"""
Ham çeviri yedeği (.ham.srt) + Geri Çeviri Anlam Kontrolü (rapor-only).

- _save_raw_backup: toggle açıkken <stem>.ham.srt yazar, kapalıyken yazmaz.
- back_translation_check: prefilter ([HATA]/çok kısa/etiket-only) hepsini elerse
  API'ye GİTMEDEN [] döner (ağ gerektirmeyen yol).
"""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import subtitle_translator_gui as gui
import hybrid_translate as ht

_TS = "00:00:01,000 --> 00:00:02,000"


class RawBackupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = SimpleNamespace(
            backup_raw_var=SimpleNamespace(get=lambda: True, set=lambda _v: None),
            _log=lambda *_args, **_kwargs: None,
        )

    @classmethod
    def tearDownClass(cls):
        pass

    def test_writes_ham_srt_when_on(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var = SimpleNamespace(get=lambda: True)
        gui.App._save_raw_backup(
            self.app, out, [("1", _TS, "Merhaba")], {"1": "Hello"})
        self.assertEqual(len(list(Path(d, "Raporlar", "Ham").glob("movie.*.ham.srt"))), 1)

    def test_skips_when_off(self):
        d = tempfile.mkdtemp()
        out = os.path.join(d, "movie.srt")
        self.app.backup_raw_var = SimpleNamespace(get=lambda: False)
        try:
            gui.App._save_raw_backup(
                self.app, out, [("1", _TS, "x")], {"1": "y"})
            self.assertFalse(list(Path(d, "Raporlar", "Ham").glob("movie.*.ham.srt")))
        finally:
            self.app.backup_raw_var = SimpleNamespace(get=lambda: True)

    def test_backup_unaffected_by_later_pass_mutation(self):
        # Ham snapshot (list kopyası) sonradan pass'ler listeyi değiştirse de korunur
        d = tempfile.mkdtemp()
        out = os.path.join(d, "m.srt")
        raw = [("1", _TS, "ham metin")]
        snapshot = list(raw)            # akışlardaki _raw_backup_blocks ile aynı desen
        raw[0] = ("1", _TS, "DEĞİŞTİ")  # bir pass yeniden atadı
        self.app.backup_raw_var = SimpleNamespace(get=lambda: True)
        gui.App._save_raw_backup(self.app, out, snapshot, {"1": "raw text"})
        backup = next(Path(d, "Raporlar", "Ham").glob("m.*.ham.srt"))
        with open(backup, encoding="utf-8") as fh:
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
