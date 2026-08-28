# -*- coding: utf-8 -*-
"""Dil ve tür tespitine giden yol kanıtı, ve tespitin loga düşmesi.

Ölçüm (2026-08-28, gerçek arşiv):
  * Klasör adı KURAL yapılamaz: dosya adı sessizken isabeti %72, ve dosya
    adıyla çeliştiği yerlerde klasör çoğu kez çok dilli altyazı PAKETİNİ
    anlatıyor (`Gang.of.Four.1989.FRENCH` dosyası `English` klasöründe).
    Bu yüzden klasör modele KANIT olarak veriliyor, karar modelin.
  * İki harfli dil kodu (`.es`, `.fr`) tabloya EKLENMEDİ: son jetonu iki
    harfli kod olan dosyalarda içerikle uyum %53 çıktı.
"""
import unittest

import subtitle_translator_gui as gui


class PathEvidenceTest(unittest.TestCase):
    def test_release_folder_reaches_the_model(self):
        """Dosya adında dil etiketi yok, klasörde var — kanıt taşınmalı."""
        got = gui._path_evidence(
            r"D:\iş\peter.ibbetson.(1935).spa.1cd"
            r"\Peter.Ibbetson.1935.1080p.BluRay.srt", depth=1)
        self.assertIn("Peter.Ibbetson.1935.1080p.BluRay.srt", got)
        self.assertIn("peter.ibbetson.(1935).spa.1cd", got)

    def test_generic_folder_does_not_consume_the_budget(self):
        """`episode 1` bütçeyi yerse sürüm klasörüne hiç ulaşılamıyordu."""
        got = gui._path_evidence(
            r"D:\iş\black.market.(2016).tv.s01.eng.6cd\episode 1"
            r"\black.market.s01e01.480p.srt", depth=1)
        self.assertIn("black.market.(2016).tv.s01.eng.6cd", got)
        self.assertNotIn("episode 1", got)

    def test_generic_names_are_skipped(self):
        for folder in ("episode 4", "Sezon 2", "bolum 3", "CD1", "Subs"):
            with self.subTest(folder=folder):
                got = gui._path_evidence(
                    "D:/kök/Filmler/%s/x.srt" % folder, depth=1)
                self.assertNotIn(folder, got)
                self.assertIn("Filmler", got)

    def test_bare_filename_still_works(self):
        self.assertEqual(gui._path_evidence("tek-dosya.srt"), "tek-dosya.srt")
        self.assertEqual(gui._path_evidence(""), "")

    def test_log_label_is_bracketed_and_short(self):
        label = gui._detect_log_label(r"D:\iş\Filmler\x.srt")
        self.assertTrue(label.startswith(" ["))
        self.assertTrue(label.endswith("]"))
        self.assertIn("x.srt", label)
        self.assertEqual(gui._detect_log_label(""), "")


class FilenameLanguageTableTest(unittest.TestCase):
    """İki harfli kodlar tabloda YOK ve olmamalı (ölçüm: %53 isabet)."""

    def test_no_two_letter_codes(self):
        two = [k for k in gui._FILENAME_LANGUAGE_TOKENS if len(k) == 2]
        self.assertEqual(two, [])

    def test_three_letter_tags_still_work(self):
        for name, expected in (("Film.2019.1080p.spa.srt", "Spanish"),
                               ("Film.2019.1080p.fre.srt", "French"),
                               ("Film.2019.1080p.ger.srt", "German")):
            with self.subTest(name=name):
                self.assertEqual(
                    gui.infer_source_language_from_filename(name), expected)

    def test_single_token_name_is_not_a_language_tag(self):
        """`Ara.srt` filmin adıdır, dil kodu değil."""
        self.assertEqual(
            gui.infer_source_language_from_filename("Ara.srt"),
            gui.AUTO_LANGUAGE)


class DetectionPromptEvidenceTest(unittest.TestCase):
    """Prompt klasörü KANIT diye sunmalı, otorite diye değil."""

    def test_batch_prompt_says_supporting_evidence(self):
        import inspect
        source = inspect.getsource(gui.detect_source_languages_batch_with_ai)
        self.assertIn("parent folder names", source)
        self.assertIn("supporting evidence", source)
        self.assertIn("trust dominant dialogue", source)

    def test_batch_sample_matches_the_single_file_path(self):
        """Toplu yol örneği kısıyordu; iki yol aynı kanıtı görmeli."""
        import inspect
        batch = inspect.getsource(gui.detect_source_languages_batch_with_ai)
        self.assertIn("_distributed_language_sample(cues)", batch)
        self.assertNotIn("max_lines=24", batch)

    def test_content_type_prompt_carries_the_path(self):
        import inspect
        source = inspect.getsource(gui.detect_content_type_with_ai)
        self.assertIn("_path_evidence", source)
        self.assertIn("_detect_log_label", source)


if __name__ == "__main__":
    unittest.main()
