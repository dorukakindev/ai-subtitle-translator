# -*- coding: utf-8 -*-
"""Dizi anahtarı: klasör geri dönüşü, N-of-M ve bitişik sezon-bölüm."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import series_memory as sm


class FolderFallbackTest(unittest.TestCase):
    """934 gerçek dosyada ölçüldü: tanınan 751 -> 893, bozulan 0.

    Tanınmayan dosya dizi hafızasına hiç girmiyor; yani o dizide bölümler
    arası terim/özel ad kanonu çalışmıyordu.
    """

    def test_a_bare_episode_name_takes_its_show_from_the_folder(self):
        self.assertEqual(
            sm.parse_series_key("X:/Insomniac with Dave Attell/S01E01 New York.srt"),
            ("insomniac-with-dave-attell", 1, 1))

    def test_the_archive_layout_skips_the_per_file_folder(self):
        # Teslim arşivinde dosyanın kendi adıyla bir ara klasör var.
        self.assertEqual(
            sm.parse_series_key(
                "X:/Insomniac with Dave Attell/S01E01 New York"
                "/Raporlar/Kaynak/S01E01 New York.srt"),
            ("insomniac-with-dave-attell", 1, 1))

    def test_the_marker_may_live_only_in_the_folder_name(self):
        # Dosya adı Rusça sıralı; bölüm işareti yalnız klasörde.
        self.assertEqual(
            sm.parse_series_key(
                "X:/Mythic Warriors/Mythic Warriors - S01E02 - Hercules"
                "/Raporlar/Kaynak/02. Gerakl.srt"),
            ("mythic-warriors", 1, 2))

    def test_a_season_folder_is_not_mistaken_for_the_show(self):
        self.assertEqual(sm.parse_series_key("X:/Show/Season 2/S02E05 Title.srt"),
                         ("show", 2, 5))

    def test_dotted_ep_abbreviation_is_recognised(self):
        self.assertEqual(
            sm.parse_series_key(
                "X:/D/The Human Animal Ep. 6 - Beyond Survival.srt"),
            ("the-human-animal", 1, 6))

    def test_legacy_compact_code_outranks_wrapper_folder_order(self):
        self.assertEqual(
            sm.parse_series_key(
                "X:/the.secret.life.of.machines.(1988).tv.s01.eng.6cd/"
                "episode 2/Secret Life Of Machines 104 The Washing Machine.srt"),
            ("the-secret-life-of-machines", 1, 4))


class MultiPartDocumentaryTest(unittest.TestCase):

    def test_n_of_total_numbering_is_recognised(self):
        self.assertEqual(
            sm.parse_series_key("X:/D/The.Question.Of.God.1of4.DivX-AC3.srt"),
            ("the-question-of-god", 1, 1))

    def test_a_series_number_becomes_the_season_not_part_of_the_name(self):
        first = sm.parse_series_key("X:/D/BBC.Sacred.Music.Series1.1of4.Gothic.srt")
        second = sm.parse_series_key("X:/D/BBC.Sacred.Music.Series2.1of4.Brahms.srt")
        self.assertEqual(first, ("bbc-sacred-music", 1, 1))
        self.assertEqual(second, ("bbc-sacred-music", 2, 1))
        self.assertEqual(first[0], second[0])

    def test_a_split_movie_is_never_treated_as_a_series(self):
        for name in ("Casablanca.CD1of2.srt", "Lawrence of Arabia.Part1of2.srt",
                     "Film.disc1of2.srt"):
            with self.subTest(name=name):
                self.assertIsNone(sm.parse_series_key("X:/Filmler/" + name))

    def test_an_ordinary_movie_stays_unrecognised(self):
        self.assertIsNone(sm.parse_series_key("X:/Filmler/Casablanca (1942).srt"))

    def test_a_compact_season_episode_is_split(self):
        self.assertEqual(
            sm.parse_series_key("X:/D/A History of Art in Three Colours S0103 White.srt"),
            ("a-history-of-art-in-three-colours", 1, 3))


if __name__ == "__main__":
    unittest.main()
