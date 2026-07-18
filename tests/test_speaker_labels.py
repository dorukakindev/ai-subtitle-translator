import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _CtkStub(SimpleNamespace):
    def __getattr__(self, name):
        if name.startswith("CTk"):
            return _DummyWidget
        return lambda *args, **kwargs: None


with patch.dict(sys.modules, {
    "customtkinter": _CtkStub(),
    "openai": SimpleNamespace(OpenAI=object),
}):
    import subtitle_translator_gui as gui

class TestSpeakerLabels(unittest.TestCase):
    def test_translate_speaker_labels(self):
        tests = [
            ("Narrator: Hello", "Anlatıcı: Hello"),
            ("NARRATOR: Hello", "ANLATICI: Hello"),
            ("[NARRATOR]: Hello", "[ANLATICI]: Hello"),
            ("- MAN: Hello", "- ADAM: Hello"),
            ("Woman (V.O.): Hello", "Kadın (D.S.): Hello"),
            ("[WOMAN (VO)]: Hello", "[KADIN (DS)]: Hello"),
            ("[Narrator] Hello", "[Anlatıcı] Hello"),
            ("Narrator (VO) : Hello", "Anlatıcı (DS) : Hello"),
            ("No speaker label at all", "No speaker label at all"),
            ("MAN is a word in a sentence: the man walked.", "MAN is a word in a sentence: the man walked."),
        ]
        for src, expected in tests:
            res = gui._translate_speaker_labels(src)
            self.assertEqual(res, expected, f"Failed for: {src!r}")

if __name__ == "__main__":
    unittest.main()
