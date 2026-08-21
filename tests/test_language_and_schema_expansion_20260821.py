# -*- coding: utf-8 -*-
"""Dil listesi ve içerik türü genişletmesi (2026-08-21)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class ExpandedLanguageListTest(unittest.TestCase):
    """Kaynak dil tespiti daha çok dili tanımalı."""

    ADDED = ("Greek", "Hebrew", "Persian", "Hindi", "Urdu", "Thai",
             "Vietnamese", "Indonesian", "Ukrainian", "Czech", "Hungarian",
             "Romanian", "Bulgarian", "Serbian", "Croatian", "Georgian",
             "Armenian", "Azerbaijani", "Kurdish", "Filipino", "Latin")

    def test_the_new_languages_are_offered(self):
        for language in self.ADDED:
            with self.subTest(language=language):
                self.assertIn(language, g.LANGUAGES)

    def test_the_original_languages_are_untouched(self):
        for language in ("Turkish", "English", "German", "French", "Spanish",
                         "Italian", "Portuguese", "Russian", "Japanese",
                         "Korean", "Chinese", "Arabic", "Dutch", "Polish",
                         "Swedish", "Norwegian", "Danish", "Finnish"):
            with self.subTest(language=language):
                self.assertIn(language, g.LANGUAGES)

    def test_every_language_has_a_real_iso_code(self):
        seen = {}
        for language in g.LANGUAGES:
            code = g._lang_iso639_1(language)
            with self.subTest(language=language):
                self.assertEqual(len(code), 2, language)
                self.assertNotIn(code, seen, f"{language} ↔ {seen.get(code)}")
            seen[code] = language

    def test_turkish_still_resolves_to_tr(self):
        self.assertEqual(g._lang_iso639_1("Turkish"), "tr")


class LanguageAliasTest(unittest.TestCase):
    """Modelin ve dosya adının kullandığı diğer adlar da eşleşmeli."""

    def test_common_alternate_names_resolve(self):
        for value, expected in (("Farsi", "Persian"), ("Mandarin", "Chinese"),
                                ("Cantonese", "Chinese"),
                                ("Brazilian Portuguese", "Portuguese"),
                                ("Castilian", "Spanish"), ("Flemish", "Dutch"),
                                ("Tagalog", "Filipino"),
                                ("Serbo-Croatian", "Serbian"),
                                ("Bahasa Indonesia", "Indonesian"),
                                ("Azeri", "Azerbaijani"),
                                ("Kurmanji", "Kurdish")):
            with self.subTest(value=value):
                self.assertEqual(g.normalize_language_name(value), expected)

    def test_regional_suffixes_are_trimmed(self):
        for value, expected in (("English (US)", "English"),
                                ("Portuguese - Brazil", "Portuguese"),
                                ("Chinese (Simplified)", "Chinese"),
                                ("Spanish, Latin America", "Spanish")):
            with self.subTest(value=value):
                self.assertEqual(g.normalize_language_name(value), expected)

    def test_turkish_language_names_resolve(self):
        for value, expected in (("Türkçe", "Turkish"), ("Yunanca", "Greek"),
                                ("İbranice", "Hebrew"), ("Rusça", "Russian"),
                                ("Çince", "Chinese"), ("Kürtçe", "Kurdish"),
                                ("Sırpça", "Serbian"), ("Farsça", "Persian")):
            with self.subTest(value=value):
                self.assertEqual(g.normalize_language_name(value), expected)

    def test_iso_codes_resolve(self):
        for code, expected in (("fa", "Persian"), ("el", "Greek"),
                               ("uk", "Ukrainian"), ("vi", "Vietnamese"),
                               ("tr", "Turkish"), ("he", "Hebrew")):
            with self.subTest(code=code):
                self.assertEqual(g.normalize_language_name(code), expected)

    def test_an_unknown_language_is_still_auto(self):
        for value in ("Klingon", "", "   ", "zzz"):
            with self.subTest(value=value):
                self.assertEqual(
                    g.normalize_language_name(value), g.AUTO_LANGUAGE)
                self.assertEqual(
                    g.normalize_language_name(value, allow_auto=False), "")


class FilenameLanguageTokenTest(unittest.TestCase):
    """Release adlarındaki yeni dil kodları da tanınmalı."""

    def test_new_three_letter_codes_are_recognised(self):
        for name, expected in (("Movie.1990.gre.srt", "Greek"),
                               ("Show.S01E01.heb.srt", "Hebrew"),
                               ("Film.2020.per.srt", "Persian"),
                               ("X.1999.ukr.srt", "Ukrainian"),
                               ("Y.2001.tha.srt", "Thai"),
                               ("Z.2011.vie.srt", "Vietnamese")):
            with self.subTest(name=name):
                self.assertEqual(
                    g.infer_source_language_from_filename(name), expected)

    def test_the_original_codes_still_work(self):
        self.assertEqual(
            g.infer_source_language_from_filename("Movie.1990.eng.srt"),
            "English")


class TargetScriptCoverageTest(unittest.TestCase):
    """Yeni hedef diller kendi alfabelerinde sert hata almamalı."""

    SAMPLES = (("Greek", "Καλημέρα"), ("Hebrew", "שלום"),
               ("Persian", "سلام"), ("Hindi", "नमस्ते"), ("Thai", "สวัสดี"),
               ("Ukrainian", "Привіт"), ("Georgian", "გამარჯობა"),
               ("Armenian", "Բարեւ"), ("Tamil", "வணக்கம்"))

    @staticmethod
    def _blocks(text):
        return [("1", "00:00:01,000 --> 00:00:03,000", text)]

    def test_each_target_accepts_its_own_script(self):
        for language, text in self.SAMPLES:
            with self.subTest(language=language):
                self.assertEqual(
                    g._foreign_script_ids(self._blocks(text), language), [])

    def test_turkish_flags_all_of_them_as_leakage(self):
        for language, text in self.SAMPLES:
            with self.subTest(language=language):
                self.assertEqual(
                    g._foreign_script_ids(self._blocks(text), "Turkish"), ["1"])

    def test_a_latin_target_is_unaffected(self):
        self.assertEqual(
            g._foreign_script_ids(self._blocks("Xin chào"), "Vietnamese"), [])


class NewContentSchemaTest(unittest.TestCase):
    """Yeni içerik türleri seçilebilir ve tespit edilebilir olmalı."""

    ADDED = ("Kore Dizisi (K-Drama)", "Hukuk / Mahkeme Dramı",
             "Bilim / Uzay Belgeseli", "Casusluk / Politik Gerilim",
             "Western", "Kara Film / Neo-Noir",
             "Süper Kahraman / Çizgi Roman", "Dövüş Sanatları / Wuxia",
             "Bollywood / Hint Sineması", "Telenovela / Latin Melodram",
             "İskandinav Polisiyesi", "Prosedürel Polisiye / Adli Dizi",
             "Biyografi Filmi (Biopic)", "Müzik Belgeseli / Konser",
             "Teknoloji / Ürün İncelemesi", "Otomotiv / Motor Sporları",
             "Zanaat / Yapım / Nasıl Yapılır", "Ekonomi / İş Dünyası",
             "Psikoloji / Kişisel Gelişim", "Dram (Genel)")

    def test_the_new_schemas_exist(self):
        names = {schema["name"] for schema in g.CONTENT_SCHEMAS.values()}
        for name in self.ADDED:
            with self.subTest(name=name):
                self.assertIn(name, names)

    def test_the_new_schemas_are_detectable(self):
        categories = g._detect_categories()
        for name in self.ADDED:
            with self.subTest(name=name):
                self.assertIn(name, categories)
                self.assertEqual(g._match_category(name, categories), name)

    def test_schema_keys_also_resolve(self):
        categories = g._detect_categories()
        for key, expected in (("kdrama", "Kore Dizisi (K-Drama)"),
                              ("legal_courtroom", "Hukuk / Mahkeme Dramı"),
                              ("noir", "Kara Film / Neo-Noir"),
                              ("drama_general", "Dram (Genel)")):
            with self.subTest(key=key):
                self.assertEqual(g._match_category(key, categories), expected)

    def test_every_new_schema_carries_real_rules(self):
        by_name = {schema["name"]: schema
                   for schema in g.CONTENT_SCHEMAS.values()}
        for name in self.ADDED:
            schema = by_name[name]
            with self.subTest(name=name):
                self.assertGreaterEqual(len(schema["rules"]), 7)
                self.assertTrue(schema["detect"].strip())
                self.assertTrue(
                    any("[TR_ERROR]" in rule for rule in schema["rules"]),
                    f"{name}: TR_ERROR kuralı yok")


class ComboboxTypeaheadTest(unittest.TestCase):
    """Uzayan listelerde harfle atlama çalışmalı."""

    def test_a_prefix_selects_the_first_match(self):
        self.assertEqual(
            g.combobox_typeahead_match(g.LANGUAGES, "gre"), "Greek")
        self.assertEqual(
            g.combobox_typeahead_match(g.LANGUAGES, "tur"), "Turkish")

    def test_a_repeated_letter_cycles_through_the_matches(self):
        first = g.combobox_typeahead_match(g.LANGUAGES, "g")
        second = g.combobox_typeahead_match(g.LANGUAGES, "g", first)
        third = g.combobox_typeahead_match(g.LANGUAGES, "g", second)
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(
            g.combobox_typeahead_match(g.LANGUAGES, "g", third), first)

    def test_no_match_returns_empty(self):
        self.assertEqual(g.combobox_typeahead_match(g.LANGUAGES, "zzz"), "")
        self.assertEqual(g.combobox_typeahead_match(g.LANGUAGES, ""), "")

    def test_it_works_on_the_schema_names_too(self):
        names = [schema["name"] for schema in g.CONTENT_SCHEMAS.values()]
        self.assertEqual(
            g.combobox_typeahead_match(names, "kore"), "Kore Dizisi (K-Drama)")

    def test_turkish_letters_are_matched_case_insensitively(self):
        names = [schema["name"] for schema in g.CONTENT_SCHEMAS.values()]
        self.assertEqual(
            g.combobox_typeahead_match(names, "iskandinav"),
            "İskandinav Polisiyesi")


if __name__ == "__main__":
    unittest.main()
