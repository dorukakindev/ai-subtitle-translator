import unittest
from sdh_cleaner import strip_sdh_line

class TestSdhSpeaker(unittest.TestCase):
    def test_speakers_and_sdh_cleaned(self):
        self.assertEqual(strip_sdh_line("[JOHN]: Hello"), "Hello")
        self.assertEqual(strip_sdh_line("(John): Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[DR. SMITH]: Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[John] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[John]"), "")
        self.assertEqual(strip_sdh_line("[Narrator 2] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[laughing] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[MUSIC]"), "")
        self.assertEqual(strip_sdh_line("<i>Hello</i>", strip_format_tags=False), "<i>Hello</i>")

    def test_casing_variations_cleaned(self):
        self.assertEqual(strip_sdh_line("[glass breaking] John wakes up."), "John wakes up.")
        self.assertEqual(strip_sdh_line("[Glass breaking] John wakes up."), "John wakes up.")
        self.assertEqual(strip_sdh_line("[Glass Breaking] John wakes up."), "John wakes up.")
        self.assertEqual(strip_sdh_line("[GLASS BREAKING] John wakes up."), "John wakes up.")

        self.assertEqual(strip_sdh_line("[woman whispering] Don't move."), "Don't move.")
        self.assertEqual(strip_sdh_line("[Woman Whispering] Don't move."), "Don't move.")
        self.assertEqual(strip_sdh_line("[WOMAN WHISPERING] Don't move."), "Don't move.")

        self.assertEqual(strip_sdh_line("[door closes] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[Door Closes] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[DOOR CLOSES] Hello"), "Hello")

        self.assertEqual(strip_sdh_line("[soft music] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[Soft Music] Hello"), "Hello")
        self.assertEqual(strip_sdh_line("[SOFT MUSIC] Hello"), "Hello")

        self.assertEqual(strip_sdh_line("[speaking French] Bonjour"), "Bonjour")
        self.assertEqual(strip_sdh_line("[Speaking French] Bonjour"), "Bonjour")
        self.assertEqual(strip_sdh_line("[SPEAKING FRENCH] Bonjour"), "Bonjour")
        self.assertEqual(strip_sdh_line("[speaking German] Hallo"), "Hallo")
        self.assertEqual(strip_sdh_line("[speaks Latin] Salve"), "Salve")
        self.assertEqual(strip_sdh_line("[in Spanish] Hola"), "Hola")

    def test_generic_sound_forms_are_cleaned_without_removing_headings(self):
        self.assertEqual(strip_sdh_line("[loud crash] Run!"), "Run!")
        self.assertEqual(strip_sdh_line("[glass breaks] Run!"), "Run!")
        self.assertEqual(strip_sdh_line("[slams] Run!"), "Run!")
        self.assertEqual(strip_sdh_line("[Soft Power] A documentary."),
                         "[Soft Power] A documentary.")
        self.assertEqual(strip_sdh_line("[Breaking News] Markets fell."),
                         "[Breaking News] Markets fell.")

    def test_long_and_nested_descriptors_are_cleaned_with_bounded_scanner(self):
        long_descriptor = "[very " + ("loud " * 22) + "crashing]"
        self.assertEqual(strip_sdh_line(long_descriptor + " Run!"), "Run!")
        self.assertEqual(strip_sdh_line("[glass (loudly) crashing] Run!"), "Run!")
        over_limit = "[" + ("noise " * 60) + "] Keep"
        self.assertEqual(strip_sdh_line(over_limit), over_limit)

    def test_preserved_titles_and_names(self):
        self.assertEqual(strip_sdh_line("[Latin] title remains"), "[Latin] title remains")
        self.assertEqual(strip_sdh_line("[New York] is a city."), "[New York] is a city.")
        self.assertEqual(strip_sdh_line("[Chapter One] The beginning."), "[Chapter One] The beginning.")
        self.assertEqual(strip_sdh_line("[Breaking News] Markets fell."), "[Breaking News] Markets fell.")
        self.assertEqual(strip_sdh_line("[No Entry] Keep out."), "[No Entry] Keep out.")
        self.assertEqual(strip_sdh_line("[Breaking Bad] Previously on..."), "[Breaking Bad] Previously on...")
        self.assertEqual(strip_sdh_line("[King George] arrived."), "[King George] arrived.")
        self.assertEqual(strip_sdh_line("[Soft Power] A documentary."), "[Soft Power] A documentary.")
        self.assertEqual(strip_sdh_line("[The Voice] Tonight."), "[The Voice] Tonight.")
        self.assertEqual(strip_sdh_line("[World War II] A history."), "[World War II] A history.")
        self.assertEqual(strip_sdh_line("[Doctor Who] returns."), "[Doctor Who] returns.")
        self.assertEqual(strip_sdh_line("[Black Mirror] begins."), "[Black Mirror] begins.")
        self.assertEqual(strip_sdh_line("[House Music] A documentary title."), "[House Music] A documentary title.")
        self.assertEqual(strip_sdh_line("[Speaking Truth] A documentary title."), "[Speaking Truth] A documentary title.")

if __name__ == "__main__":
    unittest.main()
