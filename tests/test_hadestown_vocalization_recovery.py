import unittest

import hybrid_translate as ht
import subtitle_translator_gui as gui


class HadestownVocalizationRecoveryTest(unittest.TestCase):
    def test_pure_song_syllables_are_not_untranslated(self):
        source = "<i>-Laaa la la la la laaa</i>\n<i>-Huh, kkh, huh, kkh</i>"
        target = "-Laaa la la la la laaa\n-Hah, hıh, hah, hıh"
        self.assertTrue(ht.is_vocalization_only_text(source))
        self.assertEqual("", gui._untranslated_reason(source, target))

    def test_song_syllables_do_not_mask_translated_lyric(self):
        source = "<i>-La la la la</i>\n<i>-If you wanna keep your head</i>"
        target = "-La la la la\n-Başını korumak istiyorsan"
        self.assertFalse(ht.has_source_english_overlap(source, target))
        self.assertEqual("", gui._untranslated_reason(source, target))

    def test_real_english_lyric_still_triggers_overlap(self):
        source = "<i>-La la la la</i>\n<i>-If you wanna keep your head</i>"
        target = "-La la la la\n-If you wanna keep your head"
        self.assertTrue(ht.has_source_english_overlap(source, target))

    def test_japanese_technique_name_can_stay_identical(self):
        source = "Hifuki no Kozuchi!"
        self.assertEqual("", gui._untranslated_reason(source, source))

    def test_tagged_character_name_can_stay_identical(self):
        source = "<i>Eurydice</i>"
        self.assertEqual("", gui._untranslated_reason(source, source))


if __name__ == "__main__":
    unittest.main()
