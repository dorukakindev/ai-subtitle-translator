import unittest
from sdh_cleaner import strip_sdh_line

class TestSdhSpeaker(unittest.TestCase):
    def test_speakers(self):
        self.assertEqual(strip_sdh_line("[John] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[JOHN]: Hello"), "Hello")
        self.assertEqual(strip_sdh_line("(John): Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[John]"), "")
        self.assertEqual(strip_sdh_line("[laughing] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[MUSIC]"), "")
        self.assertEqual(strip_sdh_line("Normal dialogue"), "Normal dialogue")
        self.assertEqual(strip_sdh_line("<i>Hello</i>", strip_format_tags=False), "<i>Hello</i>")
        self.assertEqual(strip_sdh_line("[Narrator 2] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[DR. SMITH]: Hello"), "Hello")

if __name__ == "__main__":
    unittest.main()
