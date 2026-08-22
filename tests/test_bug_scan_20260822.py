# -*- coding: utf-8 -*-
"""plans/bug-taramasi-2026-08-22.md — 34 kendi bulgu + 7 harici (H1-H7)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_formats as sf
import subtitle_translator_gui as g
import hybrid_translate as ht
import series_memory as sm
from prompt_constants import JSON_INSTRUCTION

NL = chr(10)


class SentenceEndTwinParityTest(unittest.TestCase):
    """Madde 18/32: cümle-sonu tespiti iki akışta da AYNI olmalı."""

    CASES = (
        '"Welcome to Miami Beach. "', 'You said "we. "', 'Bitti."', 'Bitti.’',
        '‘Bitti.’', 'Gidiyorum.›', 'Bitti.’)', 'Bitti.”', 'Bitti.")', "Bitti.'",
        'Devam ediyor', '', None, 'Bitti…', '(Bitti.)',
    )

    def test_twins_never_disagree(self):
        for case in self.CASES:
            with self.subTest(case=case):
                self.assertEqual(
                    g._ends_sentence_gui(case), ht._ends_sentence(case))

    def test_closing_quote_after_space_still_ends_the_sentence(self):
        # Baskın gerçek vaka: hybrid tek geçişli strip yaptığı için boşlukta
        # patlıyor, iki ayrı cümleyi tek sentence_groups girdisinde birleştiriyordu.
        self.assertTrue(ht._ends_sentence('"Welcome to Miami Beach. "'))

    def test_none_does_not_crash(self):
        # Madde 19: hybrid ikizi None'da AttributeError atıyordu.
        self.assertFalse(ht._ends_sentence(None))
        self.assertFalse(g._ends_sentence_gui(None))


class TurkishGuardsStayOutOfOtherTargetsTest(unittest.TestCase):
    """Madde 20/21/28: Türkçe guard'ları Türkçe dışı hedefe sızmamalı."""

    def test_quality_glossary_is_turkish_only(self):
        text = "the centerpiece and the taxidermy"
        self.assertTrue(ht.quality_glossary_for_source(text, "Turkish"))
        self.assertEqual(ht.quality_glossary_for_source(text, "German"), {})
        self.assertEqual(ht.quality_glossary_for_source(text, "Spanish"), {})

    def test_empty_target_still_behaves_as_turkish(self):
        # Çağrı yerleri hedefi geçmediğinde eski davranış korunur.
        self.assertTrue(ht.quality_glossary_for_source("the centerpiece", ""))

    def test_final_sweep_forwards_target_to_inner_sweep(self):
        import inspect
        source = inspect.getsource(ht.final_consistency_sweep)
        inner = source.index("swept, fixes = consistency_sweep(")
        segment = source[inner:inner + 320]
        self.assertIn("tgt_lang=tgt_lang", segment)

    def test_drift_guards_accept_a_target_language(self):
        import inspect
        for fn in (ht._has_content_word_drift, ht._has_content_word_loss,
                   ht._has_medical_adjective_deletion, ht.is_safe_polish_edit):
            with self.subTest(fn=fn.__name__):
                self.assertIn(
                    "tgt_lang", inspect.signature(fn).parameters)


class AddressRegisterMorphologyTest(unittest.TestCase):
    """Madde 29/30/33: ek kuralı gövde/kip ayrımı yapmalı."""

    REAL = (
        "geliyorsun", "gelirsin", "geleceksin", "gelmişsin", "geldin",
        "yaptın", "gördün", "okudun", "gittin", "bilirsin", "alırsın",
        "yapmalısın", "gelebilirsin", "sordun",
    )
    NOT_ADDRESS = (
        # tamlayan/iyelik
        "herkesin", "kentin", "sanatın", "hayatın", "saatin", "devletin",
        "polisin", "zeytin", "metin", "latin", "altın", "satın",
        # 3. tekil istek kipi
        "olsun", "gelsin", "kahretsin", "gitsin", "kalsın", "etsin",
        "yaşasın", "dursun", "versin",
        # isim
        "kadın", "aydın", "günaydın", "odun",
        # 2. ÇOĞUL emir (SİZ) — sen sayılması TERS yönde hata
        "gidin", "affedin",
    )

    def test_real_second_person_forms_are_detected(self):
        for word in self.REAL:
            with self.subTest(word=word):
                self.assertTrue(sf.is_turkish_second_person_token(word))

    def test_grammatical_false_matches_are_rejected(self):
        for word in self.NOT_ADDRESS:
            with self.subTest(word=word):
                self.assertFalse(sf.is_turkish_second_person_token(word))

    def test_both_scans_share_one_implementation(self):
        # Madde 30: GUI ve hybrid ikizleri aynı morfolojiyi kullanmalı.
        self.assertIs(
            g._address_informal_suffix_token, sf.is_turkish_second_person_token)
        self.assertEqual(ht._turkish_second_person_register("Ne olursa olsun."), "")
        self.assertEqual(ht._turkish_second_person_register("Biliyorsun."), "informal")
        self.assertEqual(ht._turkish_second_person_register("Geldin mi?"), "informal")

    def test_a_fully_formal_file_is_not_flagged_by_noise_words(self):
        blocks = []
        for i in range(100):
            blocks.append((str(i + 1), "00:00:01,000 --> 00:00:03,000",
                           "Bunu siz yapmalısınız."))
        for i in range(15):
            blocks.append((str(200 + i), "00:00:01,000 --> 00:00:03,000",
                           "Ne olursa olsun, kadın altın satın aldı."))
        self.assertFalse(g.detect_address_register_mix(blocks)["mixed"])


class ScenePlanOwnershipTest(unittest.TestCase):
    """H1/H4: sahne sahipliği ve boş sahne sızıntısı."""

    PLAN = [
        {"start": 1, "end": 3, "summary": "A", "tone": "t1"},
        {"start": 4, "end": 8, "summary": "B", "tone": "t2"},
    ]

    def test_single_scene_payload_is_unchanged(self):
        self.assertEqual(
            ht._scene_context_for_chunk(self.PLAN, 1, 3),
            [{"summary": "A", "tone": "t1"}])

    def test_multi_scene_chunk_names_the_owning_cues(self):
        entries = ht._scene_context_for_chunk(self.PLAN, 2, 6)
        self.assertEqual([e.get("cues") for e in entries], ["2-3", "4-6"])

    def test_the_cues_field_is_documented_in_the_prompt(self):
        self.assertIn("cues", JSON_INSTRUCTION)

    def test_scene_spans_are_tracked_independently_of_payload(self):
        self.assertEqual(ht._scene_span_ids(self.PLAN, 2), ((1, 3),))
        self.assertEqual(ht._scene_span_ids(self.PLAN, 5), ((4, 8),))


class AnalysisCacheTest(unittest.TestCase):
    """Madde 6 + H2/H6/H7."""

    def test_stale_scene_plan_is_a_cache_miss(self):
        import inspect
        source = inspect.getsource(ht.load_context_cache)
        marker = source.index("_scene_plan_cache_is_stale(_scene_emotions)")
        self.assertIn("return None", source[marker:marker + 600])

    def test_cache_version_moved_past_the_2026_08_01_freeze(self):
        self.assertGreaterEqual(ht.CONTEXT_ANALYSIS_CACHE_VER, 5)

    def test_fallback_tone_never_wins_the_merge(self):
        import inspect
        source = inspect.getsource(ht._merge_memories)
        self.assertIn("_first_meaningful", source)
        self.assertIn('"fallback"', source)


class IsOstIsDocumentedTest(unittest.TestCase):
    """Madde 14: payload'a giden her anahtar prompt'ta tanımlı olmalı."""

    def test_is_ost_has_a_prompt_rule(self):
        self.assertIn("is_ost", JSON_INSTRUCTION)

    def test_both_flows_emit_the_same_key(self):
        import inspect
        self.assertIn('"is_ost"', inspect.getsource(g.build_requests))
        self.assertIn('"is_ost"', inspect.getsource(ht.build_batch_requests))


class SeriesMemoryTest(unittest.TestCase):
    """Madde 4/26 + H3."""

    def test_memory_path_is_a_shared_helper(self):
        root = tempfile.mkdtemp()
        path = sm.SeriesMemory.memory_path(root, "show")
        self.assertEqual(path.parent.name, ".series_memory")
        self.assertEqual(path.name, "show.json")

    def test_get_terms_applies_the_episode_cutoff(self):
        root = tempfile.mkdtemp()
        memory = sm.SeriesMemory.load(root, "show")
        memory.merge_terms({"Troy": "Truva"}, 1, 1)
        memory.merge_terms({"Hydra": "Hidra"}, 1, 5)
        self.assertEqual(
            set(memory.get_terms()), {"Troy", "Hydra"})
        early = memory.get_terms(before_episode=(1, 3))
        self.assertIn("Troy", early)
        self.assertNotIn("Hydra", early)

    def test_character_style_survives_save_and_reload(self):
        root = tempfile.mkdtemp()
        first = sm.SeriesMemory.load(root, "show")
        first.merge_characters({"John": ""}, 1, 1)
        self.assertIsNot(first.save(), False)
        second = sm.SeriesMemory.load(root, "show")
        second.merge_characters({"John": "formal"}, 1, 2)
        self.assertIsNot(second.save(), False)
        third = sm.SeriesMemory.load(root, "show")
        self.assertEqual(third._data["characters"]["John"]["style"], "formal")

    def test_first_decision_still_wins_for_terms(self):
        root = tempfile.mkdtemp()
        first = sm.SeriesMemory.load(root, "show")
        first.merge_terms({"Troy": "Truva"}, 1, 1)
        first.save()
        second = sm.SeriesMemory.load(root, "show")
        second.merge_terms({"Troy": "Troya"}, 1, 2)
        second.save()
        self.assertEqual(
            sm.SeriesMemory.load(root, "show").get_terms()["Troy"], "Truva")


class LockedTermResidueTest(unittest.TestCase):
    """H5: kesme işaretsiz Türkçe ek almış kilitli terim."""

    def _plan(self, translated):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", translated)]
        return g._locked_term_residue_plan(
            blocks, {"1": "Memories came back."}, {"Memories": "Anılar"})

    def test_all_three_residue_shapes_are_caught(self):
        for value in ("Memories geri geldi.",
                      "Memories'leri geri geldi.",
                      "Memoriesleri geri geldi."):
            with self.subTest(value=value):
                self.assertTrue(self._plan(value))

    def test_a_correct_translation_is_untouched(self):
        self.assertFalse(self._plan("Anılar geri geldi."))


class CueFillLineBreakTest(unittest.TestCase):
    """Madde 31: satır kırma toggle'a bağlı ve denetimli olmalı."""

    def test_line_breaks_flag_is_honoured(self):
        import inspect
        params = inspect.signature(g.rebalance_cue_fill_pairs).parameters
        self.assertIn("line_breaks", params)

    def test_no_plan_means_no_change(self):
        blocks = [("1", "00:00:01,000 --> 00:00:03,000", "Kısa satır.")]
        out, count = g.rebalance_cue_fill_pairs(blocks, {"1": "Short line."})
        self.assertEqual(count, 0)
        self.assertEqual(out, blocks)


class FailedCueDropIsCountedTest(unittest.TestCase):
    """Madde 16: salt-SDH kaynaklı başarısız cue sessizce silinmemeli."""

    def test_the_drop_is_logged(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "[HATA] çeviri yok"),
            ("2", "00:00:02,000 --> 00:00:03,000", "Gerçek replik."),
        ]
        messages = []
        out, marked = g._fill_hata_with_source(
            blocks, {"1": "[DOOR SLAMS]", "2": "Real line."},
            log_fn=lambda msg, level="": messages.append(msg))
        self.assertEqual([b[0] for b in out], ["2"])
        self.assertEqual(marked, 0)
        self.assertTrue(any("salt-SDH" in msg for msg in messages))


class WorkflowProfileTest(unittest.TestCase):
    """Madde 24: eksik callback ve 'Özel' işaretlemesi."""

    def test_the_callback_exists(self):
        self.assertTrue(callable(getattr(g.App, "_mark_workflow_custom", None)))
        self.assertTrue(
            callable(getattr(g.App, "_bind_workflow_profile_watchers", None)))

    def test_applying_a_profile_suppresses_the_custom_mark(self):
        import inspect
        source = inspect.getsource(g.App._apply_workflow_profile)
        self.assertIn("_applying_workflow_profile = True", source)
        self.assertIn("finally", source)


class DeliveryScanUsesWrittenBlocksTest(unittest.TestCase):
    """Madde 3/13/25: denetim diske yazılan listeyi ve doğru izi görmeli."""

    def test_quality_scan_reads_the_delivery_list(self):
        import inspect
        for method in (g.App._run_sync_hybrid, g.App._write_results,
                       g.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                call = source.index("scan_translation_quality(")
                self.assertIn("_delivery_blocks", source[call:call + 300])

    def test_suspect_ids_accept_locked_terms(self):
        import inspect
        self.assertIn(
            "locked_terms",
            inspect.signature(g._delivery_scan_suspect_ids).parameters)

    def test_source_is_parsed_with_the_file_source_language(self):
        import inspect
        source = inspect.getsource(g.scan_translation_quality)
        self.assertNotIn("parse_subtitle(fp)", source)
        self.assertIn("parse_subtitle(fp, source_language)", source)

    def test_a_supplied_source_map_is_not_overwritten(self):
        import inspect
        source = inspect.getsource(g.scan_translation_quality)
        self.assertIn("if source_rows and src_clean_map is None:", source)


class FragmentGroupTypeParityTest(unittest.TestCase):
    """Madde 23: her akış kendi id tipiyle tutarlı kalmalı."""

    ROWS = [
        ("1", "00:00:01,000 --> 00:00:02,000", "He said"),
        ("2", "00:00:02,000 --> 00:00:03,000", "that it was over."),
    ]

    def test_gui_groups_use_string_ids_like_gui_payload_ids(self):
        _by_id, groups = g._fragment_groups_gui(self.ROWS)
        for group in groups:
            for item in group.get("items") or []:
                self.assertIsInstance(item, str)


if __name__ == "__main__":
    unittest.main()
