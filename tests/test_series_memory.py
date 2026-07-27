"""
series_memory testleri — dosya adı tespiti, ilk-karar-kanon birleştirme,
hint üretimi, bölüm sıralaması ve kalıcılık.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import series_memory as sm


class ParseSeriesKeyTest(unittest.TestCase):
    def test_standard_sxxexx(self):
        self.assertEqual(sm.parse_series_key("Show.Name.S01E05.720p.srt"),
                         ("show-name", 1, 5))

    def test_lowercase_compact(self):
        self.assertEqual(sm.parse_series_key("show_s1e5.srt"), ("show", 1, 5))

    def test_nxnn(self):
        self.assertEqual(sm.parse_series_key("Show 1x05.srt"), ("show", 1, 5))

    def test_movie_returns_none(self):
        self.assertIsNone(sm.parse_series_key("Movie.2024.1080p.srt"))

    def test_resolution_not_mistaken_for_episode(self):
        # '1280x720' bölüm sanılmamalı (ayraç yok)
        self.assertIsNone(sm.parse_series_key("Clip.1280x720.srt"))

    def test_turkish_show_name(self):
        slug, s, e = sm.parse_series_key("Çukur.S02E10.srt")
        self.assertEqual((s, e), (2, 10))
        self.assertIn("ukur", slug)  # slug Türkçe harfi koruyabilir veya sadeleştirir


class MergeTest(unittest.TestCase):
    def _mem(self):
        return sm.SeriesMemory(Path("x.json"), {
            "version": 1, "show": "x", "updated_eps": [],
            "terms": {}, "characters": {}, "address_map": []})

    def test_first_decision_is_canon(self):
        m = self._mem()
        m.merge_terms({"the Precinct": "Karakol"})
        m.merge_terms({"the Precinct": "Merkez"})   # ezmemeli
        self.assertEqual(m._data["terms"]["the Precinct"], "Karakol")

    def test_merge_characters_list_of_dicts(self):
        m = self._mem()
        m.merge_characters([{"name": "Sam", "speaking_style": "blunt"}])
        self.assertEqual(m._data["characters"]["Sam"]["style"], "blunt")

    def test_merge_characters_object(self):
        class C:
            def __init__(self, name, speaking_style):
                self.name, self.speaking_style = name, speaking_style
        m = self._mem()
        m.merge_characters([C("Lee", "calm")])
        self.assertEqual(m._data["characters"]["Lee"]["style"], "calm")

    def test_merge_address_map_pairwise_and_dict(self):
        m = self._mem()
        m.merge_address_map([{"a": "Sam", "b": "Chief", "register": "siz"}])
        m.merge_address_map({"Lee": "sen"})
        m.merge_address_map([{"a": "Sam", "b": "Chief", "register": "sen"}])  # dup, ezmemeli
        regs = {(p["a"], p["b"]): p["register"] for p in m._data["address_map"]}
        self.assertEqual(regs[("Sam", "Chief")], "siz")
        self.assertEqual(regs[("Lee", "")], "sen")

    def test_idempotent_remerge(self):
        m = self._mem()
        m.merge_terms({"a": "b"})
        m.merge_terms({"a": "b"})
        self.assertEqual(len(m._data["terms"]), 1)

    def test_get_terms_returns_defensive_copy(self):
        m = self._mem()
        m.merge_terms({"Hive": "Kovan"})
        terms = m.get_terms()
        terms["Hive"] = "Arı Kovanı"
        self.assertEqual(m.get_terms()["Hive"], "Kovan")


class BuildHintTest(unittest.TestCase):
    def test_empty_returns_empty(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": {}, "characters": {}, "address_map": []})
        self.assertEqual(m.build_hint(), "")

    def test_full_hint_has_sections(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": {"Hive": "Kovan"}, "characters": {"Sam": {"style": "blunt"}},
            "address_map": [{"a": "Sam", "b": "Chief", "register": "siz"}]})
        h = m.build_hint()
        self.assertIn("SERIES MEMORY", h)
        self.assertIn("'Hive' → 'Kovan'", h)
        self.assertIn("- Sam: blunt", h)
        self.assertIn("- Sam → Chief: 'siz'", h)

    def test_term_cap(self):
        terms = {f"t{i}": f"v{i}" for i in range(100)}
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": terms, "characters": {}, "address_map": []})
        h = m.build_hint()
        self.assertEqual(h.count("→"), sm.SeriesMemory.MAX_TERMS)


class SortTest(unittest.TestCase):
    def test_episode_order_and_non_series_last(self):
        files = ["Show.S01E03.srt", "Show.S01E01.srt", "Show.S02E01.srt",
                 "random_movie.srt", "Show.S01E02.srt"]
        out = sm.sort_files_by_episode(files)
        self.assertEqual(out[:4], ["Show.S01E01.srt", "Show.S01E02.srt",
                                   "Show.S01E03.srt", "Show.S02E01.srt"])
        self.assertEqual(out[-1], "random_movie.srt")


class PersistenceTest(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            m = sm.SeriesMemory.load(td, "the-show")
            m.merge_terms({"Hive": "Kovan"})
            m.merge_characters([{"name": "Sam", "speaking_style": "blunt"}])
            m.mark_episode(1, 1)
            m.save()
            m2 = sm.SeriesMemory.load(td, "the-show")
            self.assertEqual(m2._data["terms"]["Hive"], "Kovan")
            self.assertEqual(m2._data["characters"]["Sam"]["style"], "blunt")
            self.assertIn("s01e01", m2._data["updated_eps"])

    def test_corrupt_json_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".series_memory"
            p.mkdir()
            (p / "bad.json").write_text("{not valid", encoding="utf-8")
            m = sm.SeriesMemory.load(td, "bad")   # patlamamalı
            self.assertEqual(m._data["terms"], {})


class RunOverlayTest(unittest.TestCase):
    class _Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

    def _app(self, selected):
        from subtitle_translator_gui import App
        app = SimpleNamespace(
            series_memory_var=self._Var(True),
            tgt_var=self._Var("Turkish"),
            _active_snapshot={"selected_files": selected},
            _selected_files=selected,
            _run_series_memory={},
            _run_precontext_data={},
            _log=lambda *_args, **_kwargs: None,
        )
        for name in (
            "_series_mem_for", "_series_hint_for",
            "_merge_precontext_into_series_memory",
            "_stage_series_memory_from_precontext",
            "_commit_precontext_series_memory",
            "_merge_analysis_into_series_memory",
            "_stage_series_memory_from_analysis",
            "_update_series_memory_from_analysis",
        ):
            setattr(app, name, getattr(App, name).__get__(app))
        return app

    def test_overlay_flows_only_to_later_episode_without_writing_disk(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            app = self._app([e1, e2])

            self.assertEqual(app._series_hint_for(e1), "")
            app._stage_series_memory_from_precontext(
                e1, {"terms": {"Hive": "Kovan"}}, "Turkish")

            self.assertIn("'Hive' → 'Kovan'", app._series_hint_for(e2))
            self.assertFalse((Path(td) / ".series_memory" / "show.json").exists())

    def test_commit_persists_only_successful_episode_data(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            app = self._app([e1, e2])
            first = {"terms": {"Hive": "Kovan"}}
            future = {"terms": {"Precinct": "Karakol"}}
            app._run_precontext_data = {e1: first, e2: future}
            app._stage_series_memory_from_precontext(e1, first, "Turkish")
            app._stage_series_memory_from_precontext(e2, future, "Turkish")

            app._commit_precontext_series_memory(e1, "Turkish")

            persisted = sm.SeriesMemory.load(td, "show")
            self.assertEqual(persisted.get_terms(), {"Hive": "Kovan"})
            self.assertEqual(persisted._data["updated_eps"], ["s01e01"])

    def test_incomplete_precontext_never_enters_overlay_or_disk(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            app = self._app([e1, e2])
            partial = {
                "terms": {"Hive": "Kovan"},
                "_analysis_complete": False,
            }
            app._run_precontext_data = {e1: partial}

            app._stage_series_memory_from_precontext(e1, partial, "Turkish")
            app._commit_precontext_series_memory(e1, "Turkish")

            self.assertEqual(app._series_hint_for(e2), "")
            self.assertFalse((Path(td) / ".series_memory" / "show.json").exists())

    def test_hybrid_analysis_overlay_does_not_persist_until_success(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            app = self._app([e1, e2])
            context = SimpleNamespace(recurring_terms={"Hive": "Kovan"}, characters=[])

            app._stage_series_memory_from_analysis(e1, context, {}, "Turkish")

            self.assertIn("'Hive' → 'Kovan'", app._series_hint_for(e2))
            self.assertFalse((Path(td) / ".series_memory" / "show.json").exists())
            app._update_series_memory_from_analysis(e1, context, {})
            self.assertEqual(sm.SeriesMemory.load(td, "show").get_terms(),
                             {"Hive": "Kovan"})


if __name__ == "__main__":
    unittest.main()
