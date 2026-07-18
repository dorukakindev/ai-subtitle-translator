"""
build_precontext_hint: karakter cinsiyet etiketi (#5).
Türkçe 'o' cinsiyetsiz olduğundan ön-analiz cinsiyeti taşımalı; bilinmeyen
cinsiyet etiketlenmemeli, bilinen en az bir cinsiyet varsa açıklama satırı eklenmeli.
"""
import unittest

import subtitle_translator_gui as gui


class PrecontextGenderTest(unittest.TestCase):
    def test_known_gender_tagged(self):
        data = {"characters": [
            {"name": "John", "gender": "m", "role": "dedektif"},
            {"name": "Mary", "gender": "f"},
        ]}
        out = gui.build_precontext_hint(data)
        self.assertIn("John [erkek]", out)
        self.assertIn("Mary [kadın]", out)
        self.assertIn("genderless", out)   # açıklama satırı

    def test_unknown_gender_not_tagged(self):
        data = {"characters": [{"name": "Narrator", "gender": "unknown"}]}
        out = gui.build_precontext_hint(data)
        self.assertIn("Narrator", out)
        self.assertNotIn("[erkek]", out)
        self.assertNotIn("[kadın]", out)
        self.assertNotIn("genderless", out)  # hiç bilinen cinsiyet yok → açıklama yok

    def test_no_characters_no_crash(self):
        self.assertIsInstance(gui.build_precontext_hint({"summary": "x"}), str)
        self.assertEqual(gui.build_precontext_hint(None), "")


if __name__ == "__main__":
    unittest.main()
