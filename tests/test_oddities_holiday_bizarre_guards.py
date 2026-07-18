"""
Uzbek/Turkic residue (BAYRAMONA, KO'RSATIB-TUSUNTIRISH),
straitjacket, alligator, sinek, [CEVIRI EKSIK] report visibility.
"""

import unittest

import subtitle_translator_gui as gui

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]


class UzbekResidueTest(unittest.TestCase):
    def test_bayramona_fixed(self):
        self.assertEqual(_APPLY("BAYRAMONA"), "bayram")

    def test_bayramona_lowercase_fixed(self):
        self.assertEqual(_APPLY("bayramona"), "bayram")

    def test_korsatib_tusuntirish_fixed(self):
        self.assertEqual(_APPLY("KO'RSATIB-TUSUNTIRISH"), "gösterip açıklama")

    def test_korsatib_tusuntirish_curly_apostrophe_fixed(self):
        self.assertEqual(_APPLY("KO\u2019RSATIB-TUSUNTIRISH"), "gösterip açıklama")

    def test_korsatib_tusuntirish_no_hyphen_fixed(self):
        self.assertEqual(_APPLY("KO'RSATIB TUSUNTIRISH"), "gösterip açıklama")


    def test_turkic_drift_re_matches_bayramona(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("BAYRAMONA"))


    def test_turkic_drift_re_matches_korsatib(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("KO'RSATIB-TUSUNTIRISH"))


    def test_source_lang_leftover_matches_bayramona(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("BAYRAMONA"))


    def test_source_lang_leftover_matches_korsatib(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("KO'RSATIB-TUSUNTIRISH"))



class StraitjacketResidueTest(unittest.TestCase):
    def test_straitjacket_fixed(self):
        self.assertEqual(_APPLY("straitjacket"), "deli gömleği")

    def test_straitjacket_turkish_i_fixed(self):
        self.assertEqual(_APPLY("straıtjacket"), "deli gömleği")

    def test_straitjacket_short_form_fixed(self):
        self.assertEqual(_APPLY("straıtjaket"), "deli gömleği")

    def test_straitjacket_in_sentence_fixed(self):
        result = _APPLY("O bir straitjacket giymiş.")
        self.assertIn("deli gömleği", result)

    def test_en_leftover_matches_straitjacket(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._EN_LEFTOVER.search("straitjacket"))

    def test_source_lang_leftover_matches_straitjacket(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("straitjacket"))



class AlligatorResidueTest(unittest.TestCase):
    def test_alligator_fixed(self):
        self.assertEqual(_APPLY("alligator"), "timsah")

    def test_alligator_dili_fixed(self):
        self.assertEqual(_APPLY("alligator dili"), "timsah dili")

    def test_alligator_saldirilari_fixed(self):
        self.assertEqual(_APPLY("alligator saldırıları"), "timsah saldırıları")

    def test_alligator_in_sentence_fixed(self):
        result = _APPLY("Bir alligator gördüm.")
        self.assertIn("timsah", result)

    def test_en_leftover_matches_alligator(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._EN_LEFTOVER.search("alligator"))

    def test_source_lang_leftover_matches_alligator(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("alligator"))



class SinekResidueTest(unittest.TestCase):
    def test_sinek_fixed(self):
        self.assertEqual(_APPLY("şinek"), "sinek")

    def test_sinek_egin_in_sentence_fixed(self):
        result = _APPLY("Bir şineğin tuvaleti.")
        self.assertEqual(result, "Bir sineğin tuvaleti.")

    def test_sinek_ege_in_sentence_fixed(self):
        result = _APPLY("şineğe bak")
        self.assertEqual(result, "sineğe bak")

    def test_source_lang_leftover_matches_sinek(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("şinek"))

    def test_source_lang_leftover_matches_sinegin(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("şineğin"))

    def test_source_lang_leftover_matches_sinege(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("şineğe"))



class CeviriEksikReportVisibilityTest(unittest.TestCase):
    def test_hata_indices_shown_in_report(self):
        rows = [{
            "name": "test.srt",
            "total": 10,
            "hata": 2,
            "hata_indices": [3, 7],
        }]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "batch", 0)
        self.assertIn("[ÇEVİRİ EKSİK] kalan satır indeksleri", txt)
        self.assertIn("3, 7", txt)

    def test_hata_indices_banner_shown(self):
        rows = [{
            "name": "test.srt",
            "total": 10,
            "hata": 1,
            "hata_indices": [5],
        }]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "sync", 0)
        self.assertIn("!!! UYARI: [ÇEVİRİ EKSİK]", txt)

    def test_hata_no_indices_no_output(self):
        rows = [{"name": "x.srt", "total": 10, "hata": 0}]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "sync", 0)
        self.assertNotIn("[ÇEVİRİ EKSİK]", txt)

    def test_multiple_hata_indices_sorted(self):
        rows = [{
            "name": "a.srt",
            "total": 10,
            "hata": 3,
            "hata_indices": [9, 2, 5],
        }]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "batch", 0)
        self.assertIn("2, 5, 9", txt)

    def test_multiple_files_with_hata_indices(self):
        rows = [
            {"name": "a.srt", "total": 10, "hata": 1, "hata_indices": [4]},
            {"name": "b.srt", "total": 10, "hata": 2, "hata_indices": [1, 8]},
        ]
        txt = gui.build_quality_report_text(rows, "gpt-5.4-mini", "Turkish",
                                            "hybrid", 0)
        self.assertIn("a.srt", txt)
        self.assertIn("b.srt", txt)
        self.assertIn("4", txt)
        self.assertIn("1, 8", txt)


if __name__ == "__main__":
    unittest.main()
