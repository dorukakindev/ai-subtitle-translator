# -*- coding: utf-8 -*-
"""YENI_DERIN_BUGLAR_VE_DUZELTME_REHBERI.md (Part 2) regresyon testleri.

Her sınıf bir maddenin karşı örneğini kilitler; madde numarası docstring'de.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompt_constants as pc
import sdh_cleaner
import subtitle_formats as sf
import subtitle_translator_gui as g


class TwoWordNameStandaloneTest(unittest.TestCase):
    """Madde 1: cümle başındaki 'John Smith'te soyad tek başına sayılmamalı."""

    def test_surname_seen_only_inside_the_full_name_is_not_locked(self):
        source = ("John Smith went to town. John Smith arrived early. "
                  "Everyone knows John Smith here. John Smith left.")
        self.assertEqual(g.auto_locked_proper_nouns(source), {})

    def test_surname_that_also_stands_alone_is_still_locked(self):
        source = ("John Smith went to town. Later Smith arrived. "
                  "Everyone greeted Smith warmly. Smith left.")
        self.assertEqual(
            g.auto_locked_proper_nouns(source).get("Smith"), "Smith")


class ModernNamesAreNotIslamisedTest(unittest.TestCase):
    """Madde 5: 'David' → 'Davut' olmamalı."""

    MODERN = ("david", "mary", "adam", "jacob", "joseph", "isaac",
              "alexander", "jesus", "moses", "noah", "solomon", "abraham")

    def test_modern_given_names_left_the_canon_table(self):
        for name in self.MODERN:
            with self.subTest(name=name):
                self.assertNotIn(name, pc.CANONICAL_TURKISH_NAMES)

    def test_mythological_figures_stayed(self):
        self.assertEqual(pc.CANONICAL_TURKISH_NAMES["sisyphus"], "Sisifos")
        self.assertEqual(pc.CANONICAL_TURKISH_NAMES["plato"], "Platon")

    def test_a_character_named_david_is_not_renamed(self):
        source = ("David went home. David called Mary. "
                  "Mary saw David again. Mary left today.")
        locked = g.auto_locked_proper_nouns(source)
        self.assertNotEqual(locked.get("David"), "Davut")
        self.assertNotEqual(locked.get("Mary"), "Meryem")


class DialogueDashIsLineStartTest(unittest.TestCase):
    """Madde 6: '- Pain'i' → '- paini' olmamalı."""

    def test_dash_prefixed_line_keeps_its_capital(self):
        out, _count = g.fix_source_lowercase_apostrophes(
            "- Pain'i dindiremedik.", "We could not stop the pain.")
        self.assertTrue(out.startswith("- P"))

    def test_quote_prefixed_line_keeps_its_capital(self):
        out, _count = g.fix_source_lowercase_apostrophes(
            '"Dura\'sı kesildi."', "The dura is cut.")
        self.assertIn('"D', out)

    def test_mid_sentence_still_lowercases(self):
        out, _count = g.fix_source_lowercase_apostrophes(
            "Beynin Dura'sı kesilir.", "The dura of the brain is cut.")
        self.assertIn("durası", out)


class PossessiveSuffixHarmonyTest(unittest.TestCase):
    """Madde 7: iyelik ve iyelik+hâl ekleri de yeniden kurulmalı."""

    def test_possessive_forms_are_rebuilt(self):
        for stem, suffix, expected in (
                ("Yunanistan", "sında", "ında"),
                ("Çin", "sinde", "inde"),
                ("Mısır", "sini", "ını"),
                ("Amerika", "ında", "sında"),
                ("Almanya", "sından", "sından")):
            with self.subTest(stem=stem, suffix=suffix):
                self.assertEqual(
                    g.turkish_suffix_for_stem(stem, suffix), expected)

    def test_plain_cases_are_unchanged(self):
        self.assertEqual(g.turkish_suffix_for_stem("Çin", "daki"), "deki")
        self.assertEqual(g.turkish_suffix_for_stem("Hindistan", "ya"), "a")
        self.assertEqual(g.turkish_suffix_for_stem("Almanya", "in"), "nın")


class MayIsATranslatableMonthTest(unittest.TestCase):
    """Madde 34: 'May' ayı stop listesinde eksikti."""

    def test_every_month_is_listed(self):
        months = ("january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november",
                  "december")
        for month in months:
            with self.subTest(month=month):
                self.assertIn(month, pc.TRANSLATABLE_CAPITALISED_STOPS)


class TimestampWithTrailingCoordinatesTest(unittest.TestCase):
    """Madde 23: koordinat taşıyan zaman satırı çökmemeli."""

    TS = "00:01:20,000 --> 00:01:23,500 X1:100 Y1:200"

    def test_start_and_end_are_parsed(self):
        self.assertEqual(g._ts_to_sec_gui(self.TS), 80.0)
        self.assertEqual(g._ts_end_sec_gui(self.TS), 83.5)

    def test_plain_timestamps_still_work(self):
        plain = "00:01:20,000 --> 00:01:23,500"
        self.assertEqual(g._ts_to_sec_gui(plain), 80.0)
        self.assertEqual(g._ts_end_sec_gui(plain), 83.5)


class TagAwareLineBreakingTest(unittest.TestCase):
    """Madde 39, 40: satır kırma etiketi ortasından bölmemeli."""

    def test_short_tagged_line_is_not_split(self):
        value = '<font color="#FFFFFF" face="Arial" size="20">Kısa satır</font>'
        self.assertEqual(g._break_to_line_budget(value), value)

    def test_long_tagged_line_splits_outside_the_tag(self):
        value = ("<i>Bu gerçekten uzun bir cümle ve iki satıra bölünmesi "
                 "gerekiyor çünkü sınırı aşıyor</i>")
        out = g._break_to_line_budget(value)
        self.assertEqual(len(out.split("\n")), 2)
        for line in out.split("\n"):
            with self.subTest(line=line):
                self.assertNotIn('="', line.split(">")[0][1:])

    def test_split_never_lands_inside_a_tag(self):
        value = ('<font color="#FF0000" size="20">Bu cümle yeterince uzun '
                 'olduğu için ikiye bölünecek ve etiket bozulmamalı</font>')
        out = g._break_to_line_budget(value)
        for line in out.split("\n"):
            with self.subTest(line=line):
                self.assertEqual(line.count("<"), line.count(">"))


class RebalanceWithTagsTest(unittest.TestCase):
    """Madde 12, 42: dengeleme etiketleri soymalı, tırnaklı bitişi görmeli."""

    def test_tagged_conjunction_is_pushed_down(self):
        value = "<i>Bunu gerçekten merak ediyordum ve</i>\nsonra öğrendim."
        out = g._rebalance_line_break(value)
        self.assertNotEqual(out, value)
        self.assertTrue(out.split("\n")[1].startswith("ve</i>"))

    def test_quoted_sentence_end_is_respected(self):
        value = '"Bunu yapacağını biliyordum." Gibi\ndavranma bana.'
        self.assertEqual(g._rebalance_line_break(value), value)

    def test_plain_push_down_still_works(self):
        value = "Bu gerçekten uzun bir cümledir ve\nsonra devam ediyor."
        self.assertNotEqual(g._rebalance_line_break(value), value)


class ScreenSignsAreNotSdhTest(unittest.TestCase):
    """Madde 27: ekran tabelaları silinmemeli."""

    def test_signs_are_kept(self):
        for sign in ("EMERGENCY EXIT", "WARNING", "POLICE DEPARTMENT",
                     "DANGER", "KEEP OUT", "FOR SALE", "WELCOME"):
            with self.subTest(sign=sign):
                self.assertFalse(sdh_cleaner.is_structural_sdh_label(sign))

    def test_sound_labels_are_still_removed(self):
        for label in ("APPLAUSE", "LAUGHTER", "MUSIC PLAYING", "GUNSHOT",
                      "DOOR SLAMS", "SIREN WAILING"):
            with self.subTest(label=label):
                self.assertTrue(sdh_cleaner.is_structural_sdh_label(label))


class SeasonAddressPronounTest(unittest.TestCase):
    """Madde 33: 'sizde' bulunma hâli denetimden kaçıyordu."""

    def test_sizde_is_matched(self):
        for word in ("sizde", "sende", "sizin", "size", "senin"):
            with self.subTest(word=word):
                self.assertTrue(g._SEASON_ADDRESS_RE.search(f"{word} kaldı"))


class AssAndVttParsingTest(unittest.TestCase):
    """Madde 45, 46, 48: biçim ayrıştırma."""

    def test_four_digit_ass_fraction_is_converted(self):
        for value in ("0:01:23.5000", "0:01:23.500", "0:01:23.50",
                      "0:01:23.5"):
            with self.subTest(value=value):
                self.assertEqual(sf._ass_ts_to_srt(value), "00:01:23,500")

    def test_same_prefix_vtt_ids_are_recognised(self):
        for previous, value in (("sub-1", "sub-2"), ("item-1", "item-2"),
                                ("caption_1", "caption_2"),
                                ("seq-1", "seq-2"), ("part-1", "part-2")):
            with self.subTest(value=value):
                self.assertTrue(sf._adjacent_vtt_cue_id(value, 2, previous))

    def test_dialogue_that_looks_like_an_id_is_kept(self):
        for value in ("Caption1", "line-0-797"):
            with self.subTest(value=value):
                self.assertFalse(sf._adjacent_vtt_cue_id(value, 2, ""))

    def test_translator_notes_are_stripped(self):
        self.assertEqual(
            sf._ASS_COMMENT.sub("", "{TL Note: pun}Gerçek replik"),
            "Gerçek replik")
        self.assertEqual(sf._ASS_COMMENT.sub("", "{SFX}Patlama"), "Patlama")
        self.assertEqual(sf._ASS_COMMENT.sub("", "{=13}Metin"), "Metin")

    def test_placeholders_and_overrides_survive(self):
        self.assertEqual(
            sf._clean_ass_text("Use {username} {" + chr(92) + "an8}now"),
            "Use {username} now")


class ShoutedForeignTitleTest(unittest.TestCase):
    """Madde 8: bagirilan satirda 'MR. YI' de unvandir."""

    def test_shouted_titles_are_translated(self):
        for value, expected in (
                ("MR. YI dedi.", "BAY YI dedi."),
                ("MISS XIAO girdi.", "BAYAN XIAO girdi."),
                ("MRS. LEE geldi", "BAYAN LEE geldi"),
                ("MS. SMITH!", "BAYAN SMITH!")):
            with self.subTest(value=value):
                self.assertEqual(g.normalize_foreign_titles(value)[0], expected)

    def test_turkish_abbreviations_are_untouched(self):
        for value in ("MS hastasi", "MR goruntuleme", "MS HASTASI olabilir",
                      "MR CEKILDI"):
            with self.subTest(value=value):
                self.assertEqual(g.normalize_foreign_titles(value)[0], value)

    def test_normal_case_titles_still_work(self):
        self.assertEqual(
            g.normalize_foreign_titles("Mr. Yi dedi.")[0], "Bay Yi dedi.")


if __name__ == "__main__":
    unittest.main()
