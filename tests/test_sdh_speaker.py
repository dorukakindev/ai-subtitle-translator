import unittest
from sdh_cleaner import strip_sdh_line

class TestSdhSpeaker(unittest.TestCase):
    def test_speakers_and_sdh_cleaned(self):
        self.assertEqual(strip_sdh_line("[JOHN]: Hello"), "Hello")
        self.assertEqual(strip_sdh_line("(John): Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[DR. SMITH]: Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[John] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[John]"), "")
        self.assertEqual(strip_sdh_line("[laughing] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[MUSIC]"), "")
        self.assertEqual(strip_sdh_line("[glass breaking] John wakes up."), "John wakes up.")
        self.assertEqual(strip_sdh_line("[door closes] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[soft music] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("<i>Hello</i>", strip_format_tags=False), "<i>Hello</i>")

    def test_preserved_bracketed_phrases(self):
        self.assertEqual(strip_sdh_line("[New York] is a city."), "[New York] is a city.")
        self.assertEqual(strip_sdh_line("[Chapter One] The beginning."), "[Chapter One] The beginning.")
        self.assertEqual(strip_sdh_line("[Breaking News] Markets fell."), "[Breaking News] Markets fell.")
        self.assertEqual(strip_sdh_line("[No Entry] Keep out."), "[No Entry] Keep out.")
        self.assertEqual(strip_sdh_line("[Breaking Bad] Previously on..."), "[Breaking Bad] Previously on...")
        self.assertEqual(strip_sdh_line("[King George] arrived."), "[King George] arrived.")
        self.assertEqual(strip_sdh_line("[Soft Power] A documentary."), "[Soft Power] A documentary.")
        self.assertEqual(strip_sdh_line("[The Voice] Tonight."), "[The Voice] Tonight.")

if __name__ == "__main__":
    unittest.main()
