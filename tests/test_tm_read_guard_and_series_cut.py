# -*- coding: utf-8 -*-
"""Okuma tarafındaki iki sessiz sızıntı.

1) TM kapıları yalnız YAZARKEN uygulanıyordu; kapı eklenmeden önce yazılmış
   satır doğrudan nihai altyazı oluyordu. Gerçek veritabanı: 500.015 satırın
   351'i bugünün kapılarından geçemez, 10'u okunabilir durumdaydı.
2) `build_hint` terim listesini MAX_TERMS'te kırpıyor, `get_terms` kırpmıyordu;
   modele hiç söylenmemiş terim kilitli kümeye giriyordu. 15 gerçek
   .series_memory dosyasının 2'sinde 12 ve 48 terim böyleydi.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import series_memory as sm
import translation_memory as tm


class StoredTargetGuardTest(unittest.TestCase):

    def test_a_model_json_leak_is_never_served(self):
        self.assertFalse(tm._stored_target_is_usable(
            "that produces hallucinations?", "halüsinasyon yapan?},{", "tr"))

    def test_a_placeholder_is_never_served(self):
        for bad in ("[HATA]", "<i>[HATA]</i>", "[ÇEVİRİ EKSİK]", "   "):
            with self.subTest(bad=bad):
                self.assertFalse(
                    tm._stored_target_is_usable("Hello.", bad, "tr"))

    def test_an_untranslated_row_is_never_served(self):
        self.assertFalse(tm._stored_target_is_usable("Hey!", "Hey!", "tr"))
        self.assertFalse(tm._stored_target_is_usable("Hey!", "hey!", "tr"))

    def test_a_healthy_row_still_passes(self):
        self.assertTrue(tm._stored_target_is_usable(
            "Good morning.", "Günaydın.", "tr"))

    def test_the_read_paths_all_apply_it(self):
        import inspect
        for fn in (tm.TranslationMemory.lookup,
                   tm.TranslationMemory.lookup_batch,
                   tm.TranslationMemory.fuzzy_lookup):
            with self.subTest(fn=fn.__name__):
                self.assertIn("_stored_target_is_usable",
                              inspect.getsource(fn))

    def test_a_broken_guard_does_not_blind_the_memory(self):
        # Ağır guard patlarsa ucuz denetimler yine çalışmalı, ama sağlam
        # satırlar servis edilmeye devam etmeli — yoksa TM tamamen körelir.
        original = tm._TM_GUARD_AVAILABLE
        tm._TM_GUARD_AVAILABLE = False
        try:
            self.assertTrue(tm._stored_target_is_usable(
                "Good morning.", "Günaydın.", "tr"))
            self.assertFalse(tm._stored_target_is_usable("Hey!", "Hey!", "tr"))
            self.assertFalse(tm._stored_target_is_usable("Hi.", "[HATA]", "tr"))
        finally:
            tm._TM_GUARD_AVAILABLE = original


class SeriesTermCutTest(unittest.TestCase):
    """Kilitli küme, modele söylenen kümeden BÜYÜK olamaz."""

    def _memory(self, term_count):
        terms = {"Term%03d" % i: "Terim%03d" % i for i in range(term_count)}
        origins = {sm._term_origin_key(k): "s01e001" for k in terms}
        data = {
            "terms": terms, "term_origins": origins,
            "characters": {}, "character_origins": {},
            "address_map": [], "address_origins": {},
            "updated_eps": ["s01e01"],
        }
        return sm.SeriesMemory(Path("x.json"), data)

    def test_get_terms_is_capped_like_the_hint(self):
        mem = self._memory(sm.SeriesMemory.MAX_TERMS + 40)
        locked = mem.get_terms(before_episode=(1, 2))
        self.assertEqual(len(locked), sm.SeriesMemory.MAX_TERMS)

    def test_every_locked_term_appears_in_the_hint(self):
        mem = self._memory(sm.SeriesMemory.MAX_TERMS + 40)
        hint = mem.build_hint(before_episode=(1, 2))
        for source in mem.get_terms(before_episode=(1, 2)):
            with self.subTest(source=source):
                self.assertIn(source, hint)

    def test_a_small_series_is_unaffected(self):
        mem = self._memory(5)
        self.assertEqual(len(mem.get_terms(before_episode=(1, 2))), 5)

    def test_later_episode_decisions_are_still_cut(self):
        mem = self._memory(3)
        mem._data["term_origins"][sm._term_origin_key("Term000")] = "s01e009"
        locked = mem.get_terms(before_episode=(1, 2))
        self.assertNotIn("Term000", locked)

    def test_both_sides_share_one_filter(self):
        import inspect
        self.assertIn("_origin_allowed",
                      inspect.getsource(sm.SeriesMemory.build_hint))
        self.assertIn("_origin_allowed",
                      inspect.getsource(sm.SeriesMemory.get_terms))



class ProjectGlossaryCutTest(unittest.TestCase):
    """Proje hafızasında da kilitli küme ipucundan büyüktü.

    Kullanıcının gerçek `.project_memory` dosyası: 49 terim, ipucunda 30 —
    19 terim modele hiç söylenmeden dayatılıyordu.
    """

    def _memory(self, count):
        import project_memory as pm
        with TemporaryDirectory() as td:
            memory = pm.ProjectMemory(td)
            memory.update_glossary(
                {"Term%03d" % i: "Terim%03d" % i for i in range(count)})
            return memory, memory.build_context_hint()

    def test_the_locked_set_is_capped(self):
        import project_memory as pm
        memory, _hint = self._memory(49)
        self.assertEqual(len(memory.get_glossary()), 49)
        self.assertEqual(len(memory.get_locked_glossary()),
                         pm.ProjectMemory.MAX_HINT_TERMS)

    def test_every_locked_term_is_in_the_hint(self):
        memory, hint = self._memory(49)
        for source in memory.get_locked_glossary():
            with self.subTest(source=source):
                self.assertIn(source, hint)

    def test_the_full_glossary_is_still_available_for_display(self):
        memory, _hint = self._memory(49)
        self.assertEqual(len(memory.get_glossary()), 49)

    def test_a_small_glossary_is_unaffected(self):
        memory, _hint = self._memory(5)
        self.assertEqual(memory.get_locked_glossary(), memory.get_glossary())

    def test_the_run_uses_the_capped_accessor(self):
        import inspect
        import subtitle_translator_gui as g
        source = inspect.getsource(g.App._get_locked_terms_dict)
        self.assertIn("get_locked_glossary()", source)
        self.assertNotIn("file_pm.get_glossary()", source)

if __name__ == "__main__":
    unittest.main()
