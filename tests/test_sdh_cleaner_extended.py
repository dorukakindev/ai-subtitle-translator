"""
SDH cleaner extended tests for expanded keywords and speaker words.
"""
import unittest
from sdh_cleaner import (
    _SDH_KEYWORDS, _SPEAKER_WORDS, _SPEAKER_LABEL_TRANSLATIONS,
    is_sdh_descriptor, strip_sdh_line, is_sdh_only,
    normalize_sdh_descriptors, normalize_speaker_labels,
)


class SdhKeywordCoverageTest(unittest.TestCase):
    def test_new_english_keywords_recognized(self):
        new_keywords = [
            "footsteps", "walking", "crash", "crashing", "bark", "barking",
            "howl", "howling", "growl", "door slam", "heartbeat",
            "phone rings", "gunfire", "gunshots", "tires",
        ]
        for kw in new_keywords:
            self.assertIn(kw, _SDH_KEYWORDS, f"{kw} should be in _SDH_KEYWORDS")

    def test_descriptor_matches_new_keywords(self):
        self.assertTrue(is_sdh_descriptor("footsteps"))
        self.assertTrue(is_sdh_descriptor("door slam"))
        self.assertTrue(is_sdh_descriptor("heartbeat"))

    def test_all_caps_multiword_descriptor_is_not_mistaken_for_heading(self):
        self.assertTrue(is_sdh_descriptor("OMINOUS MUSIC"))

    def test_keyword_followed_by_sound_is_a_descriptor(self):
        self.assertTrue(is_sdh_descriptor("whistle sound", bare_text=False))
        self.assertFalse(is_sdh_descriptor("sound judgment", bare_text=False))

    def test_hamilton_sdh_descriptors_are_recognized(self):
        descriptors = [
            "Elk bugles", "Aircraft passing overhead", "Wolf howls",
            "Chorale climbs", "Grunt-spits", "Liquid sloshes",
            "Performer exclaims in Spanish", "Squeaking sharply",
            "Blade grinds", "Blows softly", "speaks foreign language",
        ]
        for descriptor in descriptors:
            with self.subTest(descriptor=descriptor):
                self.assertTrue(is_sdh_descriptor(descriptor, bare_text=False))



    def test_speaker_words_expanded(self):
        new_speakers = ["doctor", "nurse", "officer", "teacher", "judge",
                        "king", "queen", "soldier", "captain", "priest",
                        "baby", "patient"]
        for sw in new_speakers:
            self.assertIn(sw, _SPEAKER_WORDS, f"{sw} should be in _SPEAKER_WORDS")

    def test_speaker_label_translations_expanded(self):
        new_mappings = {
            "doctor": "Doktor", "nurse": "Hemşire", "officer": "Memur",
            "teacher": "Öğretmen", "judge": "Hakim", "king": "Kral",
            "queen": "Kraliçe", "soldier": "Asker", "captain": "Kaptan",
            "priest": "Rahip", "baby": "Bebek", "patient": "Hasta",
        }
        for eng, expected_tr in new_mappings.items():
            self.assertIn(eng, _SPEAKER_LABEL_TRANSLATIONS)
            self.assertEqual(_SPEAKER_LABEL_TRANSLATIONS[eng], expected_tr)


class SdhNormalizeTest(unittest.TestCase):
    def test_normalize_speaker_labels_handles_new_mappings(self):
        result = normalize_speaker_labels("Doctor: How are you?")
        self.assertIn("Doktor:", result)

    def test_speaker_label_normalize_nurse(self):
        result = normalize_speaker_labels("Nurse: Please wait here.")
        self.assertIn("Hemşire:", result)

    def test_speaker_label_normalize_judge(self):
        result = normalize_speaker_labels("Judge: Order in the court.")
        self.assertIn("Hakim:", result)

    def test_is_sdh_only_with_new_keyword(self):
        self.assertTrue(is_sdh_only("[gunfire]"))
        self.assertFalse(is_sdh_only("Hello there"))

    def test_music_descriptor_translated(self):
        result = normalize_sdh_descriptors("[Music playing]")
        self.assertIn("MÜZİK", result.upper())

    def test_strip_sdh_line_removes_new_descriptors(self):
        result = strip_sdh_line("[door slamming] Hello")
        self.assertEqual(result, "Hello")

    def test_descriptor_preserved_when_not_translated(self):
        result = normalize_sdh_descriptors("[Footsteps approaching]")
        self.assertIn("Footsteps", result)
