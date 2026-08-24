# -*- coding: utf-8 -*-
"""Otomatik ad kilidi DOSYA kanıtına bakar; sıradan sözcük kilitlenmez."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_translator_gui as g

TR = "Türkçe"
NL = chr(10)


class TheEvidenceIsFileWideTest(unittest.TestCase):
    """Kilit kararı chunk'a değil dosyaya bakmalı.

    2026-08-24 canlı koşusu (American Movie): analiz 2 chunk'a bölündü ve
    'Okay', 'Check', 'Action', 'Hold' özel ad sanılıp kilitlendi — ana
    modele "bunları ÇEVİRME" denmiş oldu. Oysa 'okay' kaynakta 15, 'action'
    5 kez küçük harfle geçiyor; kanıt yalnız DİĞER chunk'taydı.
    """

    # Durak listesinde OLMAYAN nötr bir sözcük: gösterilen şey KAPSAM etkisi.
    # ('Okay' artık listede olduğu için kapsamdan bağımsız reddediliyor.)
    FIRST = (("He said Shimmer to that. " * 3)
             + "Mark went home. Mark called Mark again. Mark left.")
    SECOND = "It was shimmer, really shimmer, and shimmer again."

    def test_a_chunk_alone_locks_the_ordinary_word(self):
        locked = g.auto_locked_proper_nouns(self.FIRST, {}, target_language=TR)
        self.assertIn("Shimmer", locked)

    def test_the_whole_file_does_not(self):
        locked = g.auto_locked_proper_nouns(
            self.FIRST + " " + self.SECOND, {}, target_language=TR)
        self.assertNotIn("Shimmer", locked)

    def test_the_real_name_survives_either_way(self):
        locked = g.auto_locked_proper_nouns(
            self.FIRST + " " + self.SECOND, {}, target_language=TR)
        self.assertIn("Mark", locked)

    def test_the_analysis_passes_the_whole_file_down(self):
        source = inspect.getsource(ht._analyze_context_openai_compatible)
        self.assertIn("full_source_cues", source)
        self.assertIn("full_blob", source)
        marker = source.index("auto_locked_proper_nouns(")
        self.assertIn("full_blob", source[marker:marker + 120])

    def test_the_caller_supplies_the_full_cue_list(self):
        self.assertIn("full_source_cues=cues", inspect.getsource(ht))


class OrdinaryWordsAreNeverLockedTest(unittest.TestCase):
    """202 gerçek kaynakta ölçülen suçlular; hepsi gerçek dosyalardan."""

    # Ünlem/komut, meslek, akrabalık, yabancı sıradan sözcük
    ORDINARY = ("okay", "yeah", "sure", "listen", "look", "watch", "relax",
                "hold", "check", "action", "cause", "dying", "laughing",
                "shouts", "works", "petting", "mama", "papa", "grandad",
                "eminence", "baron", "archaeologists", "trooper",
                "monsieur", "quando", "dieu", "criador")

    def test_they_are_all_in_the_translatable_stop_list(self):
        for word in self.ORDINARY:
            with self.subTest(word=word):
                self.assertIn(word, g._AUTOLOCK_TRANSLATABLE_STOPS)

    def test_a_repeated_ordinary_word_is_refused(self):
        text = ("He called Action there. We shot the Action scene. "
                "Then Action again.")
        self.assertNotIn("Action",
                         g.auto_locked_proper_nouns(text, {}, target_language=TR))

    def test_the_reason_is_reported(self):
        rejected = {}
        # Komşuları küçük harfli olmalı: büyük harfli komşu varsa 'hep çok
        # kelimeli adın parçası' elemesi daha önce devreye giriyor.
        text = ("i said Listen to him. he would Listen to nobody. "
                "they never Listen at all.")
        g.auto_locked_proper_nouns(text, {}, rejected_out=rejected,
                                   target_language=TR)
        self.assertEqual(rejected.get("Listen"), "çevrilebilir sınıf")


class NamesWithATurkishFormAreLockedToItTest(unittest.TestCase):
    """Kimlikle kilitlemek onları Türkçe altyazıda İngilizce bırakıyordu."""

    def test_troy_becomes_truva(self):
        # Bilinen vaka: Strangest Things S02E03'te 35 cue elle düzeltilmişti.
        self.assertEqual(g.FOREIGN_EXONYM_MAP.get("troy"), "Truva")

    def test_the_measured_places_and_dates_are_mapped(self):
        for source, target in (("argentina", "Arjantin"),
                               ("california", "Kaliforniya"),
                               ("christmas", "Noel")):
            with self.subTest(source=source):
                self.assertEqual(g.FOREIGN_EXONYM_MAP.get(source), target)

    def test_a_locked_exonym_carries_the_turkish_form(self):
        text = ("The city Troy fell. The walls of Troy stood. "
                "At last Troy burned.")
        locked = g.auto_locked_proper_nouns(text, {}, target_language=TR)
        self.assertEqual(locked.get("Troy"), "Truva")

    def test_a_non_turkish_target_gets_no_turkish_form(self):
        text = ("The city Troy fell. The walls of Troy stood. "
                "At last Troy burned.")
        locked = g.auto_locked_proper_nouns(text, {}, target_language="German")
        self.assertNotEqual(locked.get("Troy"), "Truva")

    def test_modern_first_names_are_still_left_alone(self):
        # 'David' bir gün bu tabloda vardı ve "Davut" yapıyordu.
        for name in ("david", "mary", "adam", "jacob"):
            with self.subTest(name=name):
                self.assertNotIn(name, g.FOREIGN_EXONYM_MAP)


if __name__ == "__main__":
    unittest.main()
