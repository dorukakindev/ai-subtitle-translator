# -*- coding: utf-8 -*-
"""Dış denetim tur 3 — altı bulgu, hepsi gerçek dosyalarda ölçüldü."""
import inspect
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)


class LineBudgetReflowTest(unittest.TestCase):
    """Madde 3: 3+ satırlı cue hiç düzeltilmiyordu.

    Fonksiyon 'satır sayısı ASLA max_lines'ı aşmaz (EBU)' diyor ama sarma
    döngüsü yalnız `len(lines) < max_lines` iken çalışıyordu. Gerçek ölçüm:
    192.870 teslim cue'sunun 2.562'si 3+ satır, 2.515'i düz metin.
    """

    def test_a_three_line_plain_cue_is_reflowed(self):
        text = NL.join(["Birinci satır", "İkinci satır", "Üçüncü satır"])
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertLessEqual(len(out.split(NL)), g._MAX_LINES)

    def test_a_real_delivery_sample_becomes_two_lines(self):
        text = NL.join([
            "Saygın Viktorya dönemi insanları spiritüalizmle,",
            "seanslarla,",
            "tarotla ve daha fazlasıyla uğraşıyordu.",
        ])
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertEqual(len(out.split(NL)), 2)

    def test_no_word_is_lost_when_reflowing(self):
        text = NL.join(["Bir iki üç", "dört beş altı", "yedi sekiz dokuz"])
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertEqual(out.split(), text.split())

    def test_dialogue_structure_is_never_merged(self):
        # İki tireli cue'da satır yapısı konuşmacı ayrımıdır.
        text = NL.join(["- Merhaba.", "- Nasılsın?", "- İyiyim."])
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertEqual(out, text)

    def test_two_line_input_is_still_left_alone(self):
        long_line = "Bu oldukça uzun bir altyazı satırıdır ve bölünmesi gerekir"
        text = long_line + NL + long_line
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertEqual(len(out.split(NL)), g._MAX_LINES)

    def test_rebalance_does_not_restore_an_overwide_line(self):
        text = ("ve şirketlerle bireylerin," + NL
                + "istedikleri gibi harcama hakkı olduğunu")
        out = g.apply_line_breaks([("1", "ts", text)])[0][2]
        self.assertTrue(all(g._visible_len(line) <= g._LINE_THRESHOLD
                            for line in out.split(NL)))


class VisibleCpsTest(unittest.TestCase):
    """Madde 4: CPS görünmez biçim etiketlerini karakter sayıyordu.

    Gerçek ölçüm: 192.870 cue'da 6.607 SAHTE alarm (55 dosya).
    """

    RAW = "<i>figürler bu duvara yansıtılır.</i>"
    TS = "00:00:01,000 --> 00:00:02,500"

    def test_tags_do_not_count_as_characters(self):
        self.assertLess(g._visible_len(self.RAW), len(self.RAW))

    def test_scan_does_not_flag_a_tagged_but_normal_cue(self):
        stats = g._scan_delivery_blocks([("1", self.TS, self.RAW)], None)
        self.assertEqual(stats.get("cps", 0), 0)

    def test_hata_cps_counter_agrees(self):
        _hata, cps = g._count_hata_cps([("1", self.TS, self.RAW)])
        self.assertEqual(cps, 0)

    def test_cps_stats_use_visible_characters(self):
        avg, top = g._cps_stats([("1", self.TS, self.RAW)])
        self.assertAlmostEqual(top, 20.0, places=1)

    def test_a_genuinely_fast_cue_is_still_flagged(self):
        fast = "Bu cümle gerçekten çok uzun ve okunamayacak kadar hızlı akıyor."
        _hata, cps = g._count_hata_cps([("1", self.TS, fast)])
        self.assertEqual(cps, 1)


class DeliveryLineCountTest(unittest.TestCase):
    """Madde 5: rapordaki 'N satır' teslim edilen cue sayısı olmalı."""

    def test_signature_cues_are_excluded(self):
        blocks = [
            ("0", "ts", "discord: ceviri2"),
            ("1", "ts", "Merhaba."),
            ("2", "ts", "discord: ceviri2"),
        ]
        self.assertEqual(g.delivery_line_count(blocks), 1)

    def test_empty_input(self):
        self.assertEqual(g.delivery_line_count([]), 0)
        self.assertEqual(g.delivery_line_count(None), 0)

    def test_every_flow_reports_the_delivered_count(self):
        source = inspect.getsource(g)
        self.assertEqual(source.count('"total": delivery_line_count('), 4)
        self.assertNotIn('"total": len(sorted_blocks),', source)
        self.assertNotIn('"total": len(_final_blocks),', source)


class EnglishTrackSelectionTest(unittest.TestCase):
    """Madde 6: BCP-47 bölge etiketli İngilizce iz seçilmiyordu."""

    def test_regional_english_tags_are_english(self):
        for tag in ("eng", "en", "english", "en-US", "en_GB", "EN-us"):
            with self.subTest(tag=tag):
                self.assertEqual(g._video_track_language(tag), "English")

    def test_other_languages_are_unaffected(self):
        self.assertEqual(g._video_track_language("spa"), "Spanish")
        self.assertEqual(g._video_track_language("it-IT"), "Italian")

    def test_the_selector_uses_the_normalizer(self):
        source = inspect.getsource(g)
        self.assertIn(
            '_video_track_language(stream.language) == "English"', source)
        self.assertNotIn('in {"eng", "en", "english"}', source)


class ResumeUnfinishedMarkerTest(unittest.TestCase):
    """Madde 1: resume kısmi çıktıyı ayırıyor ama TAMAMLANMADI yazmıyordu."""

    def test_both_partial_branches_write_the_marker(self):
        source = inspect.getsource(g.App._wait_batch_hybrid)
        self.assertEqual(source.count("_write_unfinished_run_marker("), 2)

    def test_the_missing_cue_branch_reports_the_count(self):
        source = inspect.getsource(g.App._wait_batch_hybrid)
        marker = source.index("reason=\"eksik çeviri satırı kaldı\"")
        self.assertIn("missing=_hata_n_pre", source[marker:marker + 200])


class ResumeKeepsAnalysisTermsTest(unittest.TestCase):
    """Madde 2: fmap'e istekleri kuran sözlüğün AYNISI yazılmalı."""

    def test_submit_batch_persists_the_effective_locked_terms(self):
        source = inspect.getsource(g.App._run_hybrid)
        marker = source.index("ht.submit_batch(")
        window = source[marker:marker + 1600]
        self.assertIn("locked_terms=_file_locked_terms", window)
        self.assertNotIn(
            "locked_terms=self._get_locked_terms_dict(filepath, tgt)", window)

    def test_the_effective_dict_merges_analysis_terms(self):
        context = SimpleNamespace(recurring_terms={"Vessel": "Kap"})
        merged = g._hybrid_file_locked_terms(
            {"Oracle": "Kahin"}, (context,), {"Oracle": "Kullanici"},
            "Turkish")
        self.assertEqual(merged.get("Oracle"), "Kullanici")
        self.assertIn("Vessel", merged)


if __name__ == "__main__":
    unittest.main()
