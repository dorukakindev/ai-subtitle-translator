# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 31-39."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import project_memory as pm
import sdh_cleaner as sc
import series_memory as sm
import subtitle_formats as sf
import subtitle_translator_gui as g
import translation_memory as tm

NL = chr(10)


class OutputPathCarriesTheTargetLanguageTest(unittest.TestCase):
    """Madde 31: farklı hedef diller aynı yolu paylaşmamalı."""

    SOURCE = "X:/f/Film.tur.srt"

    def _same_folder(self, language):
        return g._resolve_output_path(
            "", "", self.SOURCE, same_folder=True,
            target_language=language).name

    def test_three_targets_produce_three_paths(self):
        names = {self._same_folder(language)
                 for language in ("Turkish", "German", "French")}
        self.assertEqual(len(names), 3)

    def test_turkish_keeps_the_existing_name(self):
        self.assertEqual(
            g._resolve_output_path("", "", "X:/f/Film.srt",
                                   same_folder=True).name,
            "Film.tr.srt")

    def test_repeating_the_same_target_is_stable(self):
        self.assertEqual(self._same_folder("German"), self._same_folder("German"))

    def test_a_language_tagged_source_does_not_collide(self):
        name = g._resolve_output_path(
            "", "", "X:/f/film.de.srt", same_folder=True,
            target_language="German").name
        self.assertNotEqual(name, "film.de.srt")

    def test_a_separate_output_folder_also_separates_languages(self):
        turkish = g._resolve_output_path("X:/in", "X:/out", "X:/in/Film.srt")
        german = g._resolve_output_path("X:/in", "X:/out", "X:/in/Film.srt",
                                        target_language="German")
        self.assertNotEqual(turkish, german)
        self.assertEqual(turkish.name, "Film.srt")


class FuzzyPunctuationGateTest(unittest.TestCase):
    """Madde 32: anlam taşıyan iç noktalama farkı reuse'u kapatmalı."""

    def test_meaning_changing_commas_block_reuse(self):
        for first, second in (
                ("Lets eat, Grandma!", "Lets eat Grandma!"),
                ("Please help, Jack, off the horse.",
                 "Please help Jack off the horse."),
                ("I enjoy cooking, my family, and my dog.",
                 "I enjoy cooking my family and my dog.")):
            with self.subTest(first=first):
                self.assertFalse(
                    tm._fuzzy_semantically_compatible(first, second))

    def test_typographic_variants_still_reuse(self):
        self.assertTrue(tm._fuzzy_semantically_compatible("It's fine", "It’s fine"))
        self.assertTrue(tm._fuzzy_semantically_compatible("Wait...", "Wait…"))

    def test_a_terminal_exclamation_is_not_a_meaning_change(self):
        self.assertTrue(tm._fuzzy_semantically_compatible(
            "This is a great day", "This is a great day!"))

    def test_a_question_is_not_a_statement(self):
        self.assertFalse(tm._fuzzy_semantically_compatible("Really?", "Really!"))
        self.assertFalse(tm._fuzzy_semantically_compatible("Fine.", "Fine?"))


class AmbiguousSourceDisablesExactReuseTest(unittest.TestCase):
    """Madde 34: aynı dosyada iki anlamı olan kaynak yeniden kullanılmamalı."""

    SETTINGS = {"tgt_lang": "tr", "model": "gpt", "schema_name": "film",
                "source_language": "english", "context_fingerprint": "ctx"}

    def _memory(self):
        folder = tempfile.mkdtemp()
        memory = tm.TranslationMemory(os.path.join(folder, "tm.db"))
        self.addCleanup(memory.close)
        return memory

    def test_two_meanings_disable_reuse_for_that_source(self):
        memory = self._memory()
        memory.store_batch(
            [("Right.", "Sag."), ("Right.", "Dogru."), ("Hello.", "Merhaba.")],
            **self.SETTINGS)
        self.assertIsNone(memory.lookup("Right.", **self.SETTINGS))
        self.assertEqual(memory.lookup("Hello.", **self.SETTINGS), "Merhaba.")

    def test_an_earlier_single_meaning_row_is_dropped(self):
        memory = self._memory()
        memory.store("Right.", "Sag.", **self.SETTINGS)
        self.assertEqual(memory.lookup("Right.", **self.SETTINGS), "Sag.")
        memory.store_batch([("Right.", "Sag."), ("Right.", "Dogru.")],
                           **self.SETTINGS)
        self.assertIsNone(memory.lookup("Right.", **self.SETTINGS))

    def test_genuine_repeats_still_reuse(self):
        memory = self._memory()
        memory.store_batch([("Fine.", "Iyi."), ("Fine.", "Iyi.")],
                           **self.SETTINGS)
        self.assertEqual(memory.lookup("Fine.", **self.SETTINGS), "Iyi.")


class CapitalisedCommonWordsAreNotLockedTest(unittest.TestCase):
    """Madde 35: 'Camera → Camera' kalıcı kilit olmamalı."""

    def test_ordinary_words_are_rejected_in_any_case(self):
        for word in ("camera", "Camera", "Train", "TRAIN", "Doctor", "Police"):
            with self.subTest(word=word):
                self.assertTrue(pm.is_self_translation(word, word))

    def test_real_proper_nouns_and_acronyms_survive(self):
        for word in ("NASA", "IQ", "Yi", "Sisyphus", "Berlin", "Ayn Rand",
                     "Göbekli Tepe"):
            with self.subTest(word=word):
                self.assertFalse(pm.is_self_translation(word, word))

    def test_a_real_translation_is_never_a_self_translation(self):
        self.assertFalse(pm.is_self_translation("Camera", "Kamera"))


class UnicodeEquivalentIdentityTest(unittest.TestCase):
    """Madde 36: NFC/NFD yazımlar aynı kimliğe düşmeli."""

    DECOMPOSED = "Cafe" + chr(0x0301)
    COMPOSED = "Caf" + chr(0x00e9)

    def test_series_keys_match(self):
        first = sm.parse_series_key(self.DECOMPOSED + ".S01E01.srt")
        second = sm.parse_series_key(self.COMPOSED + ".S01E02.srt")
        self.assertEqual(first[0], second[0])

    def test_term_identity_matches(self):
        self.assertEqual(sm._term_identity(self.DECOMPOSED),
                         sm._term_identity(self.COMPOSED))

    def test_different_names_stay_different(self):
        self.assertNotEqual(sm._term_identity("Cafe"), sm._term_identity("Cafó"))


class VisibleTimecodeStaysInTheCueTest(unittest.TestCase):
    """Madde 37: numaralı cue içindeki zaman kodu metni cue bölmemeli."""

    def _parse(self, body):
        handle, path = tempfile.mkstemp(suffix=".srt")
        os.close(handle)
        try:
            with open(path, "w", encoding="utf-8") as out:
                out.write(body)
            return list(g.parse_srt(path))
        finally:
            os.unlink(path)

    def test_a_timecode_line_inside_a_numbered_cue_is_text(self):
        rows = self._parse(
            "1" + NL + "00:00:01,000 --> 00:00:06,000" + NL
            + "The screen says:" + NL + "00:10:00,000 --> 00:20:00,000" + NL
            + "Do not copy that timecode." + NL + NL
            + "2" + NL + "00:00:07,000 --> 00:00:09,000" + NL
            + "Next line." + NL)
        self.assertEqual(len(rows), 2)
        self.assertIn("00:10:00,000", rows[0][2])
        self.assertEqual(rows[0][1], "00:00:01,000 --> 00:00:06,000")

    def test_an_unnumbered_srt_still_parses(self):
        rows = self._parse(
            "00:00:01,000 --> 00:00:03,000" + NL + "Bir." + NL + NL
            + "00:00:04,000 --> 00:00:05,000" + NL + "Iki." + NL)
        self.assertEqual(len(rows), 2)

    def test_numbered_cues_without_a_blank_separator_still_split(self):
        rows = self._parse(
            "1" + NL + "00:00:01,000 --> 00:00:03,000" + NL + "Bir." + NL
            + "2" + NL + "00:00:04,000 --> 00:00:05,000" + NL + "Iki." + NL)
        self.assertEqual(len(rows), 2)


class NonLatinScreenTextIsKeptTest(unittest.TestCase):
    """Madde 38: Latin dışı ekran yazıları SDH sanılmamalı."""

    def test_real_signs_survive(self):
        for sign in ("東京都庁", "Мэрия Москвы", "서울시청"):
            with self.subTest(sign=sign):
                self.assertFalse(sc.is_sdh_descriptor(sign))

    def test_genuine_sound_labels_are_still_removed(self):
        for label in ("ドアが開く", "ЗВОНОК", "музыка", "음악", "صوت"):
            with self.subTest(label=label):
                self.assertTrue(sc.is_sdh_descriptor(label))

    def test_latin_labels_are_unaffected(self):
        self.assertTrue(sc.is_sdh_descriptor("DOOR OPENS"))


class RubyReadingIsSeparatedTest(unittest.TestCase):
    """Madde 39: `<rt>` okunuşu ana sözcüğe yapışmamalı."""

    def test_the_reading_is_dropped(self):
        self.assertEqual(
            sf.clean_translation_source_text("<ruby>漢<rt>kan</rt></ruby>"), "漢")

    def test_ruby_parentheses_are_dropped_too(self):
        value = "<ruby>東京<rp>(</rp><rt>とうきょう</rt><rp>)</rp></ruby>"
        self.assertEqual(sf.clean_translation_source_text(value), "東京")

    def test_ordinary_markup_is_unaffected(self):
        self.assertEqual(
            sf.clean_translation_source_text("<i>Normal</i>"), "Normal")


if __name__ == "__main__":
    unittest.main()
