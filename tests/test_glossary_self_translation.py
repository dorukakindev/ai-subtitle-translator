"""
Kaynak==hedef (İngilizce kendine eşlenen) sözlük girdisi koruması.
Bug: project_memory/series_memory, 'train'→'train' gibi girdileri dondurup
İngilizce'yi Türkçe çıktıya sızdırıyordu (TM'deki koruma bunlarda yoktu).
"""
import tempfile
import unittest
from pathlib import Path

from project_memory import ProjectMemory, is_self_translation
import series_memory as sm


class IsSelfTranslationTest(unittest.TestCase):
    def test_lowercase_common_word_rejected(self):
        self.assertTrue(is_self_translation("train", "train"))
        self.assertTrue(is_self_translation("camera", "Camera"))   # case-insensitive
        self.assertTrue(is_self_translation("police", "police"))

    def test_proper_noun_and_acronym_kept(self):
        self.assertFalse(is_self_translation("Ayn Rand", "Ayn Rand"))  # özel ad
        self.assertFalse(is_self_translation("IQ", "IQ"))              # kısaltma
        self.assertFalse(is_self_translation("Killface", "Killface"))  # karakter adı

    def test_real_translation_kept(self):
        self.assertFalse(is_self_translation("train", "tren"))
        self.assertFalse(is_self_translation("police", "polis"))


class ProjectMemoryGlossaryGuardTest(unittest.TestCase):
    def test_self_translation_not_stored_but_proper_noun_is(self):
        with tempfile.TemporaryDirectory() as td:
            pm = ProjectMemory(td)
            pm.update_glossary({
                "train": "train",       # reddedilmeli
                "police": "police",     # reddedilmeli
                "camera": "kamera",     # gerçek çeviri — kabul
                "Ayn Rand": "Ayn Rand", # özel ad — kabul
                "IQ": "IQ",             # kısaltma — kabul
            })
            gl = pm.get_glossary()
            self.assertNotIn("train", gl)
            self.assertNotIn("police", gl)
            self.assertEqual(gl.get("camera"), "kamera")
            self.assertEqual(gl.get("Ayn Rand"), "Ayn Rand")
            self.assertEqual(gl.get("IQ"), "IQ")


class SeriesMemoryTermGuardTest(unittest.TestCase):
    def test_self_translation_not_stored(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "version": 1, "show": "x", "updated_eps": [],
            "terms": {}, "characters": {}, "address_map": []})
        m.merge_terms({"train": "train", "the Hive": "Kovan", "Killface": "Killface"})
        self.assertNotIn("train", m._data["terms"])
        self.assertEqual(m._data["terms"].get("the Hive"), "Kovan")
        self.assertEqual(m._data["terms"].get("Killface"), "Killface")  # özel ad korunur


if __name__ == "__main__":
    unittest.main()
