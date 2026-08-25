# -*- coding: utf-8 -*-
"""Madde 8: sweep'in birimi cümle; terim düzeyi görünmüyor ve '✓' yanıltıyor."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import subtitle_translator_gui as gui

TS = "00:00:01,000 --> 00:00:03,000"


def _pair(source_lines, target_lines):
    src = {str(i): text for i, text in enumerate(source_lines, 1)}
    blocks = [(str(i), TS, text) for i, text in enumerate(target_lines, 1)]
    return blocks, src


class TwoDifferentNamesAreNotOneMixedTermTest(unittest.TestCase):
    """Kümeleyici renderingleri yüzey benzerliğiyle eşliyor; 'Rama' ile
    'Ravana', 'Arjuna' ile 'Karna' benzer başladığı için aynı terimin iki
    yazımı sanılıyordu. Oysa ikisi de kaynakta geçen AYRI karakterlerdir ve
    öneri uygulansa kahramanın adı iblisin adıyla değiştirilirdi.

    278 gerçek çiftte 26 benzersiz bulgu ölçüldü: süzgeç 5'ini düşürdü,
    5'i de yanlış pozitifti (Arjuna/Karna ×2, Rama/Ravana ×2, Troy/Troad);
    kaybedilen gerçek bulgu 0.
    """

    def test_two_characters_are_not_merged(self):
        blocks, src = _pair(
            ["Rama fought Ravana.", "Rama was brave.", "Ravana was cruel.",
             "Rama won.", "Ravana fell."],
            ["Rama, Ravana ile savaştı.", "Rama cesurdu.", "Ravana zalimdi.",
             "Rama kazandı.", "Ravana düştü."])
        self.assertEqual(gui.detect_mixed_term_renderings(blocks, src), [])

    def test_the_filter_names_its_reason(self):
        self.assertTrue(gui._mixed_rendering_is_misalignment(
            "Rama", {"Rama*": 42, "Ravana*": 11},
            {"rama", "ravana"}, {"rama", "ravana"}))

    def test_a_source_word_alternative_is_a_misalignment(self):
        # 'Troad' kümelenmiş terim olmasa bile kaynakta geçiyor.
        self.assertTrue(gui._mixed_rendering_is_misalignment(
            "Troy", {"Troya*": 9, "Troad*": 2}, {"troy"}, {"troy", "troad"}))

    def test_a_turkish_rendering_is_never_a_misalignment(self):
        # Gerçek Türkçe karşılık İngilizce kaynakta geçmez.
        for term, renderings in (("London", {"Londra*": 8, "London*": 2}),
                                 ("Gothic", {"Gothic*": 67, "Gotik*": 10}),
                                 ("American", {"American*": 2,
                                               "Amerikalı*": 8})):
            with self.subTest(term=term):
                self.assertFalse(gui._mixed_rendering_is_misalignment(
                    term, renderings, {term.casefold()},
                    {term.casefold(), "the", "and"}))

    def test_a_real_inconsistency_survives(self):
        blocks, src = _pair(
            ["He went to London.", "London is old.", "London again.",
             "About London.", "London once more.", "London."],
            ["Londra'ya gitti.", "Londra eskidir.", "Londra yine.",
             "London hakkında.", "London bir kez daha.", "Londra."])
        findings = gui.detect_mixed_term_renderings(blocks, src)
        self.assertEqual([item["term"] for item in findings], ["London"])


class TheSweepStopsGivingAFalseAllClearTest(unittest.TestCase):
    """consistency_sweep'in birimi cue'nun TAMAMIDIR: ancak birebir aynı
    kaynak satır iki kez geçerse karşılaştırma yapılır. Terim düzeyi bu
    yüzden görünmüyor ve '✓ tutarsızlık bulunamadı' yanlış yeşil ışık
    oluyordu.

    278 gerçek çiftte 20 dosya sweep'ten temiz çıkarken gerçek terim
    tutarsızlığı taşıyor.
    """

    CUES = [(str(i), TS, "He went to London.") for i in range(1, 4)]
    BLOCKS = [(str(i), TS, "Londra'ya gitti.") for i in range(1, 4)]

    def _sweep(self, **kwargs):
        logs = []
        ht.consistency_sweep(
            self.CUES, self.BLOCKS,
            log_fn=lambda msg, kind="info": logs.append((kind, msg)),
            tgt_lang="Turkish", **kwargs)
        return logs[-1]

    def test_a_clean_file_says_what_it_checked(self):
        kind, message = self._sweep()
        self.assertEqual(kind, "ok")
        self.assertIn("tekrar eden cümlelerde", message)
        self.assertIn("terim düzeyi ayrıca taranır", message)

    def test_term_findings_turn_the_tick_into_a_warning(self):
        kind, message = self._sweep(term_findings=[
            {"term": "London", "renderings": {"Londra*": 8, "London*": 2}}])
        self.assertEqual(kind, "warn")
        self.assertIn("London", message)
        self.assertIn("karışık", message)
        self.assertNotIn("✓", message)

    def test_several_findings_are_counted(self):
        _kind, message = self._sweep(term_findings=[
            {"term": "London"}, {"term": "Gothic"}, {"term": "Pylos"}])
        self.assertIn("3 terim", message)

    def test_the_sweep_still_reports_its_own_fixes_first(self):
        # Cümle düzeyi bulgu varsa mesaj eskisi gibi kalır.
        cues = [("1", TS, "He went to London."), ("2", TS, "He went to London.")]
        blocks = [("1", TS, "Londra'ya gitti."), ("2", TS, "Londraya vardı.")]
        logs = []
        ht.consistency_sweep(
            cues, blocks,
            log_fn=lambda msg, kind="info": logs.append((kind, msg)),
            tgt_lang="Turkish", min_words=3,
            term_findings=[{"term": "London"}])
        self.assertTrue(any("Consistency sweep" in msg for _k, msg in logs))


class EveryFlowPassesTheTermFindingsTest(unittest.TestCase):
    """Bir değişiklik dört akışa da uygulanmalı."""

    def test_all_four_call_sites_are_wired(self):
        source = inspect.getsource(gui)
        self.assertEqual(
            source.count("term_findings=App._term_level_findings("), 4)

    def test_the_helper_is_report_only(self):
        doc = gui.App._term_level_findings.__doc__ or ""
        self.assertIn("YALNIZ raporlanır", doc)


if __name__ == "__main__":
    unittest.main()
