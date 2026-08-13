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
from unittest import mock

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

    def test_tv_root_episode_directory(self):
        fp = Path("flag.(2006).tv.s01.fre.13cd fransızca") / "episode 3" / "Flag.03.srt"
        self.assertEqual(sm.parse_series_key(str(fp)), ("flag", 1, 3))

    def test_tv_root_puntata_filename(self):
        fp = Path("a.come.andromeda.(1972).tv.s01.eng.5cd") / "subs" / "A Come Andromeda - Puntata 4.srt"
        self.assertEqual(
            sm.parse_series_key(str(fp)), ("a-come-andromeda", 1, 4))

    def test_tv_root_n_of_total_filename(self):
        fp = Path("cold.lazarus.(1996).tv.s01.eng.5cd") / "subs" / "Cold Lazarus BBC 1996 2 of 4 eng sub.srt"
        self.assertEqual(
            sm.parse_series_key(str(fp)), ("cold-lazarus", 1, 2))

    def test_tv_root_overrides_release_name_for_consistent_slug(self):
        fp = Path("doomed.megalopolis.(1991).tv.s01.eng.4cd") / "episode 1" / "Doomed.Megalopolis.Release.S01E01.srt"
        self.assertEqual(
            sm.parse_series_key(str(fp)), ("doomed-megalopolis", 1, 1))

    def test_episode_words_without_tv_root_are_not_series(self):
        fp = Path("movies") / "episode 3" / "Film - Puntata 3.srt"
        self.assertIsNone(sm.parse_series_key(str(fp)))

    def test_series_memory_root_uses_marked_tv_parent(self):
        root = Path("flag.(2006).tv.s01.fre.13cd fransızca")
        fp = root / "episode 3" / "Flag.03.srt"
        self.assertEqual(sm.series_memory_root(str(fp)), root)

    def test_common_tv_root_shares_memory_across_seasons(self):
        root = Path("the.big.o.(1999).tv")
        first = root / "season 1" / "episode 3" / "BigO03.srt"
        second = root / "season 2" / "episode 3" / "BigO16.srt"
        self.assertEqual(sm.parse_series_key(str(first)), ("the-big-o", 1, 3))
        self.assertEqual(sm.parse_series_key(str(second)), ("the-big-o", 2, 3))
        self.assertEqual(sm.series_memory_root(str(first)), root)
        self.assertEqual(sm.series_memory_root(str(second)), root)

    def test_generic_tv_library_keeps_show_memories_separate(self):
        library = Path("TV")
        first = library / "Show One" / "Season 1" / "Show.One.S01E01.srt"
        second = library / "Show Two" / "Season 1" / "Show.Two.S01E01.srt"

        self.assertEqual(sm.parse_series_key(str(first)), ("show-one", 1, 1))
        self.assertEqual(sm.parse_series_key(str(second)), ("show-two", 1, 1))
        self.assertEqual(sm.series_memory_root(str(first)), library / "Show One")
        self.assertEqual(sm.series_memory_root(str(second)), library / "Show Two")


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

    def test_term_keys_are_case_insensitive_for_canonical_decisions(self):
        m = self._mem()
        m.merge_terms({"Security Services": "Güvenlik Servisi"})
        m.merge_terms({"security services": "Emniyet Birimi"})
        self.assertEqual(
            m._data["terms"], {"Security Services": "Güvenlik Servisi"})

    def test_acronym_and_lowercase_word_keep_separate_canonical_terms(self):
        m = self._mem()
        m.merge_terms({"US": "ABD", "us": "bize"})
        self.assertEqual(m.get_terms(), {"US": "ABD", "us": "bize"})

    def test_acronym_origin_does_not_expose_later_lowercase_term(self):
        m = self._mem()
        m.merge_terms({"US": "ABD"}, season=1, ep=1)
        m.merge_terms({"us": "bize"}, season=1, ep=10)
        hint = m.build_hint(before_episode=(1, 2))
        self.assertIn("'US' → 'ABD'", hint)
        self.assertNotIn("'us' → 'bize'", hint)

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

    def test_character_case_variant_does_not_create_duplicate(self):
        m = self._mem()
        m.merge_characters({"Sam": ""})
        m.merge_characters({"sam": "blunt"})
        self.assertEqual(list(m._data["characters"]), ["Sam"])
        self.assertEqual(m._data["characters"]["Sam"]["style"], "blunt")

    def test_turkish_dotted_character_case_variant_does_not_duplicate(self):
        m = self._mem()
        m.merge_characters({"İpek": ""})
        m.merge_characters({"ipek": "resmi"})

        self.assertEqual(list(m._data["characters"]), ["İpek"])
        self.assertEqual(m._data["characters"]["İpek"]["style"], "resmi")

    def test_english_i_character_case_variant_does_not_duplicate(self):
        m = self._mem()
        m.merge_characters({"Iris": ""})
        m.merge_characters({"iris": "resmi"})

        self.assertEqual(list(m._data["characters"]), ["Iris"])
        self.assertEqual(m._data["characters"]["Iris"]["style"], "resmi")

    def test_turkish_dotted_address_pair_does_not_duplicate(self):
        m = self._mem()
        m.merge_address_map([{"a": "İpek", "b": "Ali", "register": "siz"}])
        m.merge_address_map([{"a": "ipek", "b": "ali", "register": "sen"}])

        self.assertEqual(len(m._data["address_map"]), 1)
        self.assertEqual(m._data["address_map"][0]["register"], "siz")

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

    def test_term_filter_removes_stale_explanatory_decisions(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": {
                "psychedelic": "psikedelik; bağlama göre ayrıştırılmalı",
                "history": "tarih",
            },
            "characters": {}, "address_map": [],
        })
        h = m.build_hint(term_filter=lambda terms: {
            key: value for key, value in terms.items() if key == "history"
        })
        self.assertNotIn("psychedelic", h)
        self.assertIn("'history'", h)

    def test_term_cap(self):
        terms = {f"t{i}": f"v{i}" for i in range(100)}
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": terms, "characters": {}, "address_map": []})
        h = m.build_hint()
        self.assertEqual(h.count("→"), sm.SeriesMemory.MAX_TERMS)
        self.assertIn("'t0'", h)
        self.assertIn("'t99'", h)

    def test_future_episode_decisions_are_not_injected_into_earlier_episode(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": {}, "characters": {}, "address_map": []})
        m.merge_terms({"Late Reveal": "Geç Açığa Çıkan"}, season=1, ep=10)
        m.merge_characters(
            [{"name": "Future Character", "style": "cold"}], season=1, ep=10)
        m.merge_address_map(
            [{"a": "Sam", "b": "Chief", "register": "sen"}], season=1, ep=10)

        early = m.build_hint(before_episode=(1, 1))
        later = m.build_hint(before_episode=(1, 11))
        self.assertEqual(early, "")
        self.assertIn("Late Reveal", later)
        self.assertIn("Future Character", later)
        self.assertIn("Sam → Chief", later)

    def test_legacy_unscoped_memory_fails_closed_for_earlier_episode(self):
        m = sm.SeriesMemory(Path("x.json"), {
            "terms": {"Spoiler": "Sürpriz"}, "characters": {},
            "address_map": [], "updated_eps": ["s01e10"],
            "legacy_unscoped": True,
        })
        self.assertEqual(m.build_hint(before_episode=(1, 1)), "")
        self.assertIn("Spoiler", m.build_hint(before_episode=(1, 11)))


class SortTest(unittest.TestCase):
    def test_episode_order_and_non_series_last(self):
        files = ["Show.S01E03.srt", "Show.S01E01.srt", "Show.S02E01.srt",
                 "random_movie.srt", "Show.S01E02.srt"]
        out = sm.sort_files_by_episode(files)
        self.assertEqual(out[:4], ["Show.S01E01.srt", "Show.S01E02.srt",
                                   "Show.S01E03.srt", "Show.S02E01.srt"])
        self.assertEqual(out[-1], "random_movie.srt")


class PersistenceTest(unittest.TestCase):
    def test_rejects_path_traversal_show_slug(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                sm.SeriesMemory.load(td, "../outside")
            self.assertFalse((Path(td) / "outside.json").exists())

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            m = sm.SeriesMemory.load(td, "the-show")
            m.merge_terms({"Hive": "Kovan"})
            m.merge_characters([{"name": "Sam", "speaking_style": "blunt"}])
            m.mark_episode(1, 1)
            self.assertTrue(m.save())
            m2 = sm.SeriesMemory.load(td, "the-show")
            self.assertEqual(m2._data["terms"]["Hive"], "Kovan")
            self.assertEqual(m2._data["characters"]["Sam"]["style"], "blunt")
            self.assertIn("s01e01", m2._data["updated_eps"])

    def test_save_failure_is_reported_to_caller(self):
        with tempfile.TemporaryDirectory() as td:
            memory = sm.SeriesMemory.load(td, "the-show")
            with mock.patch.object(
                    sm, "atomic_write_json", side_effect=OSError("disk full")):
                self.assertFalse(memory.save())

    def test_corrupt_json_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".series_memory"
            p.mkdir()
            (p / "bad.json").write_text("{not valid", encoding="utf-8")
            m = sm.SeriesMemory.load(td, "bad")   # patlamamalı
            self.assertEqual(m._data["terms"], {})

    def test_target_languages_use_isolated_series_memory(self):
        with tempfile.TemporaryDirectory() as td:
            german = sm.SeriesMemory.load(td, "show", target_language="de")
            german.merge_terms({"hello": "hallo"})
            german.save()
            turkish = sm.SeriesMemory.load(td, "show", target_language="tr")
            turkish.merge_terms({"hello": "merhaba"})
            turkish.save()

            self.assertEqual(
                sm.SeriesMemory.load(
                    td, "show", target_language="de").get_terms(),
                {"hello": "hallo"},
            )
            self.assertEqual(
                sm.SeriesMemory.load(
                    td, "show", target_language="tr").get_terms(),
                {"hello": "merhaba"},
            )
            self.assertTrue(
                (Path(td) / ".series_memory" / "de" / "show.json").exists()
            )
            self.assertTrue(
                (Path(td) / ".series_memory" / "show.json").exists()
            )

    def test_source_languages_use_isolated_series_memory(self):
        with tempfile.TemporaryDirectory() as td:
            english = sm.SeriesMemory.load(
                td, "show", target_language="tr", source_language="en")
            english.merge_terms({"hello": "merhaba"})
            english.save()
            spanish = sm.SeriesMemory.load(
                td, "show", target_language="tr", source_language="es")
            spanish.merge_terms({"si": "evet"})
            spanish.save()

            self.assertEqual(
                sm.SeriesMemory.load(
                    td, "show", target_language="tr",
                    source_language="en").get_terms(),
                {"hello": "merhaba"},
            )
            self.assertEqual(
                sm.SeriesMemory.load(
                    td, "show", target_language="tr",
                    source_language="es").get_terms(),
                {"si": "evet"},
            )
            self.assertTrue(
                (Path(td) / ".series_memory" / "src-es"
                 / "tgt-tr" / "show.json").exists())

    def test_different_show_slugs_never_share_series_memory(self):
        with tempfile.TemporaryDirectory() as td:
            first = sm.SeriesMemory.load(td, "first-show")
            second = sm.SeriesMemory.load(td, "second-show")
            first.merge_terms({"term": "birinci"})
            first.save()
            second.merge_terms({"term": "ikinci"})
            second.save()

            self.assertEqual(
                sm.SeriesMemory.load(td, "first-show").get_terms()["term"],
                "birinci",
            )
            self.assertEqual(
                sm.SeriesMemory.load(td, "second-show").get_terms()["term"],
                "ikinci",
            )

    def test_two_stale_instances_merge_without_losing_first_decisions(self):
        with tempfile.TemporaryDirectory() as td:
            first = sm.SeriesMemory.load(td, "show")
            second = sm.SeriesMemory.load(td, "show")
            first.merge_terms({"Alpha": "Alfa"})
            first.mark_episode(1, 1)
            second.merge_terms({"Beta": "Beta TR", "Alpha": "Yanlış"})
            second.mark_episode(1, 2)
            first.save()
            second.save()

            loaded = sm.SeriesMemory.load(td, "show")
            self.assertEqual(loaded.get_terms(), {"Alpha": "Alfa", "Beta": "Beta TR"})
            self.assertEqual(loaded._data["updated_eps"], ["s01e01", "s01e02"])

    def test_stale_instances_keep_acronym_and_lowercase_term_separate(self):
        with tempfile.TemporaryDirectory() as td:
            first = sm.SeriesMemory.load(td, "show")
            second = sm.SeriesMemory.load(td, "show")
            first.merge_terms({"US": "ABD"})
            second.merge_terms({"us": "bize"})
            first.save()
            second.save()

            self.assertEqual(
                sm.SeriesMemory.load(td, "show").get_terms(),
                {"US": "ABD", "us": "bize"},
            )

    def test_concurrent_save_does_not_merge_wrong_language_disk_data(self):
        with tempfile.TemporaryDirectory() as td:
            memory = sm.SeriesMemory.load(td, "show", source_language="en")
            memory.merge_terms({"yes": "evet"})
            memory._path.parent.mkdir(parents=True, exist_ok=True)
            memory._path.write_text(json.dumps({
                "target_language": "tr", "source_language": "es",
                "terms": {"si": "evet"}, "characters": {},
                "address_map": [], "updated_eps": [],
            }), encoding="utf-8")
            memory.save()
            self.assertEqual(sm.SeriesMemory.load(td, "show").get_terms(), {"yes": "evet"})


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

    def test_existing_ambiguous_term_is_not_injected_as_fixed_decision(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            memory = sm.SeriesMemory.load(td, "show")
            memory.merge_terms({
                "psychedelic": (
                    "“psikedelik”; “halüsinojenik” ile bağlama göre "
                    "ayrıştırılmalı."
                ),
                "history": "tarih",
            }, season=1, ep=1)
            self.assertTrue(memory.save())

            hint = self._app([e1, e2])._series_hint_for(e2)
            self.assertNotIn("psychedelic", hint)
            self.assertIn("'history'", hint)

    def test_run_overlay_is_scoped_by_target_language(self):
        with tempfile.TemporaryDirectory() as td:
            e1 = str(Path(td) / "Show.S01E01.srt")
            e2 = str(Path(td) / "Show.S01E02.srt")
            app = self._app([e1, e2])
            app._active_snapshot["tgt_lang"] = "German"
            app._stage_series_memory_from_precontext(
                e1, {"terms": {"hello": "hallo"}}, "German")
            self.assertIn("'hello' → 'hallo'", app._series_hint_for(e2))

            app._active_snapshot["tgt_lang"] = "Turkish"
            self.assertEqual(app._series_hint_for(e2), "")

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

    def test_persistent_memory_failure_reaches_quality_status(self):
        app = self._app(["Show.S01E01.srt"])
        app._series_mem_for = lambda *_args, **_kwargs: (
            SimpleNamespace(save=lambda: False), 1, 1)
        app._merge_analysis_into_series_memory = lambda *_args: None
        status = {}

        app._update_series_memory_from_analysis(
            "Show.S01E01.srt", SimpleNamespace(), {}, "Turkish",
            status_out=status)

        self.assertEqual(status["status"], "failed")


if __name__ == "__main__":
    unittest.main()
