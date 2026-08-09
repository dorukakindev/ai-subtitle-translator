import unittest

import subtitle_translator_gui as gui


class SourceIdentityRecognitionTest(unittest.TestCase):
    def test_patronymic_scientific_name_is_not_untranslated_dialogue(self):
        self.assertTrue(gui._src_is_scientific_name("Penicillium camemberti."))
        self.assertFalse(gui._src_is_scientific_name("The answer is ready."))


if __name__ == "__main__":
    unittest.main()
