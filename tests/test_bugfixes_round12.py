"""
Round 12 bug-fix regresyon testleri:
- parse_vtt: açık cue ID ile sıralı sayaç çakışmaz (benzersiz index)
- credential_store.migrate_from_settings: JSON null değerinde çökmez
- _review_pass erken-dönüş 2-tuple (ValueError unpack çökmesi yok)
"""
import json
import os
import tempfile
import unittest
import importlib.util
from pathlib import Path
from unittest import mock

from subtitle_formats import parse_vtt
import credential_store as cs


class VttIndexCollisionTest(unittest.TestCase):
    def test_explicit_cue_id_does_not_collide(self):
        vtt = ("WEBVTT\n\n"
               "2\n00:00:01.000 --> 00:00:03.000\nFirst\n\n"
               "00:00:04.000 --> 00:00:06.000\nSecond\n\n"
               "00:00:07.000 --> 00:00:09.000\nThird\n")
        fd, fp = tempfile.mkstemp(suffix=".vtt"); os.close(fd)
        Path(fp).write_text(vtt, encoding="utf-8")
        try:
            blocks = parse_vtt(fp)
            indices = [b[0] for b in blocks]
            self.assertEqual(len(indices), len(set(indices)), f"index çakışması: {indices}")
            self.assertEqual(len(blocks), 3)
            # Metinler doğru sırada ve hiçbiri ezilmemiş
            self.assertEqual([b[2] for b in blocks], ["First", "Second", "Third"])
        finally:
            os.unlink(fp)


class MigrateNullValueTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._fb = Path(self._tmp.name) / ".credentials"
        self._patches = [
            mock.patch.object(cs, "_has_keyring", return_value=False),
            mock.patch.object(cs, "_fallback_path", return_value=self._fb),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_null_api_key_does_not_crash_and_migrates_other(self):
        settings = Path(self._tmp.name) / ".gui_settings.json"
        settings.write_text(json.dumps(
            {"api_key": None, "minimax_key": "sk-helper-abcdef", "model": "gpt-5.4-mini"}),
            encoding="utf-8")
        # Çökmemeli
        cs.migrate_from_settings(settings)
        # null api_key atlanmalı, geçerli minimax_key göç etmeli
        self.assertEqual(cs.load_key("minimax"), "sk-helper-abcdef")
        d = json.loads(settings.read_text(encoding="utf-8"))
        self.assertNotIn("minimax_key", d)        # göç etti → silindi
        self.assertEqual(d.get("model"), "gpt-5.4-mini")


class ReviewPassEarlyReturnTest(unittest.TestCase):
    """_review_pass erken dönüşleri 2-tuple olmalı; caller `a, b = ...` ile açıyor."""
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("customtkinter") is None:
            raise unittest.SkipTest("customtkinter yüklü değil; GUI testi atlandı")
        import subtitle_translator_gui as gui
        from tests._gui_app import make_app
        # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app = make_app(gui); cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_empty_api_key_returns_tuple(self):
        # API key boş → client kurulur ama src yoksa erken döner; her hâlükârda 2-tuple
        self.app.api_key_entry.delete(0, "end")
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba"),
                  ("2", "00:00:02,000 --> 00:00:03,000", "Dünya"),
                  ("3", "00:00:03,000 --> 00:00:04,000", "!")]
        # Olmayan dosya → src_map boş → erken dönüş; unpack patlamamalı
        res = self.app._review_pass("___yok___.srt", blocks, "gpt-4.1-mini", "Turkish")
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 2)
        out_blocks, fixes = res
        self.assertEqual(out_blocks, blocks)
        self.assertEqual(fixes, 0)


if __name__ == "__main__":
    unittest.main()
