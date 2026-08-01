"""
scan_translation_quality: 'çevrilmemiş görünüyor' yanlış-pozitiflerini azaltma.
Özel ad öbekleri ve SDH/efekt satırları kaynakla aynı kalması NORMAL — bunları
işaretlememeli; gerçekten çevrilmemiş normal cümleleri yine işaretlemeli.
"""
import unittest

import subtitle_translator_gui as gui


def _scan(src_map, blocks):
    return gui.scan_translation_quality("x.srt", blocks, src_clean_map=src_map)


class ScannerFalsePositiveTest(unittest.TestCase):
    def test_proper_noun_phrase_not_flagged(self):
        # 3 kelimelik özel ad öbeği, aynı kalmış → çevrilmemiş SAYILMAMALI
        src = {"1": "Hurlan Hambrosia Boons"}
        blk = [("1", "00:00:01,000 --> 00:00:03,000", "Hurlan Hambrosia Boons")]
        self.assertEqual(_scan(src, blk), 0)

    def test_punctuated_single_names_from_live_run_not_flagged(self):
        for value in ("- Colly!", "- Peter.", "Taskerlands?", "Brock.", "Jill, Jill."):
            with self.subTest(value=value):
                self.assertEqual(
                    _scan({"1": value},
                          [("1", "00:00:01,000 --> 00:00:03,000", value)]),
                    0,
                )

    def test_punctuated_multiword_name_not_flagged(self):
        value = "William Crawshaw."
        self.assertEqual(
            _scan({"1": value}, [("1", "00:00:01,000 --> 00:00:03,000", value)]),
            0,
        )

    def test_place_names_with_lowercase_particles_not_flagged(self):
        for value in (
            "Valle de Guadalupe",
            "Sitio del Güije!",
            "Hato de Juan Díaz",
            "San Juan del Cayo",
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    _scan({"1": value},
                          [("1", "00:00:01,000 --> 00:00:03,000", value)]),
                    0,
                )

    def test_title_list_with_commas_not_flagged(self):
        value = "Coronation Street, Double\nYour Money, Come Dancing,"
        self.assertEqual(
            _scan({"1": value}, [("1", "00:00:01,000 --> 00:00:03,000", value)]),
            0,
        )

    def test_short_title_case_commands_still_flagged(self):
        for value in ("Come Here", "Wait Here", "Please Stop"):
            with self.subTest(value=value):
                self.assertEqual(
                    _scan({"1": value},
                          [("1", "00:00:01,000 --> 00:00:03,000", value)]),
                    1,
                )

    def test_sdh_effect_line_not_flagged(self):
        src = {"1": "(door slams loudly)"}
        blk = [("1", "00:00:01,000 --> 00:00:03,000", "(door slams loudly)")]
        self.assertEqual(_scan(src, blk), 0)

    def test_bracket_sdh_not_flagged(self):
        src = {"1": "[ominous music playing]"}
        blk = [("1", "00:00:01,000 --> 00:00:03,000", "[ominous music playing]")]
        self.assertEqual(_scan(src, blk), 0)

    def test_real_untranslated_still_flagged(self):
        # gerçekten çevrilmemiş normal cümle (küçük harf kelimeler) → İŞARETLENMELİ
        src = {"1": "he ran away very fast"}
        blk = [("1", "00:00:01,000 --> 00:00:08,000", "he ran away very fast")]
        self.assertEqual(_scan(src, blk), 1)

    def test_title_case_sentence_with_verb_still_flagged(self):
        src = {"1": "He Ran Away"}
        blk = [("1", "00:00:01,000 --> 00:00:03,000", "He Ran Away")]
        self.assertEqual(_scan(src, blk), 1)

    def test_properly_translated_not_flagged(self):
        src = {"1": "he ran away very fast"}
        blk = [("1", "00:00:01,000 --> 00:00:08,000", "çok hızlı kaçıp gitti")]
        self.assertEqual(_scan(src, blk), 0)


if __name__ == "__main__":
    unittest.main()
