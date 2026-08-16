import unittest

import subtitle_translator_gui as gui


class DeliverySdhDescriptorTests(unittest.TestCase):
    def test_documentary_action_descriptors_are_expected_removals(self):
        for text in (
                "(All exchanging greetings)",
                "(Plucks strings)",
                "(Man translating into French)"):
            with self.subTest(text=text):
                self.assertTrue(gui._source_cue_is_delivery_removable(text))

    def test_bare_documentary_reaction_and_music_descriptors_are_removable(self):
        for text in (
                "HE LAUGHS",
                "HE EXHALES",
                "GENTLE LAUGHTER",
                "THEME MUSIC AND APPLAUSE",
                "PULSING"):
            with self.subTest(text=text):
                self.assertTrue(gui._source_cue_is_delivery_removable(text))


if __name__ == "__main__":
    unittest.main()
