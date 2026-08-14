"""
scan_translation_quality: 'çevrilmemiş görünüyor' yanlış-pozitiflerini azaltma.
Özel ad öbekleri ve SDH/efekt satırları kaynakla aynı kalması NORMAL — bunları
işaretlememeli; gerçekten çevrilmemiş normal cümleleri yine işaretlemeli.
"""
import tempfile
import unittest
from pathlib import Path

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

    def test_title_with_and_connector_not_flagged(self):
        value = "Sparks and Quencher!"
        self.assertEqual(
            _scan({"1": value}, [("1", "00:00:01,000 --> 00:00:03,000", value)]),
            0,
        )

    def test_locked_identity_term_not_flagged(self):
        value = "ACME-X 7"
        self.assertEqual(
            gui.scan_translation_quality(
                "x.srt",
                [("1", "00:00:01,000 --> 00:00:03,000", value)],
                src_clean_map={"1": value},
                locked_terms={value: value},
                source_language="English",
            ),
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

    def test_long_cast_name_list_not_flagged_or_retried(self):
        value = (
            "M. Andreeva, N. Krujkov, B. Bratkovsky\n"
            "G. Stahanova, R. Brijjikaite, V. Surikov"
        )
        self.assertEqual(
            _scan({"1": value}, [("1", "00:00:01,000 --> 00:00:06,000", value)]),
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

    def test_source_etymology_token_is_not_reported_as_target_garble(self):
        src = {"1": "The face was ondwlita in Old English."}
        blk = [("1", "00:00:01,000 --> 00:00:05,000",
                "Eski İngilizcede yüze ondwlita denirdi.")]
        self.assertEqual(_scan(src, blk), 0)

    def test_cross_cue_sentence_redistribution_is_not_length_outlier(self):
        src = {
            "1": "Listen, it's been several days now",
            "2": "that we pretend that nothing",
            "3": "You have no reason to act this way",
            "4": "if you are not afraid for yourself.",
        }
        blk = [
            ("1", "00:00:01,000 --> 00:00:03,000",
             "Dinle, birkaç gündür hiçbir şey olmamış gibi davranıyoruz,"),
            ("2", "00:00:03,000 --> 00:00:04,000", "ama"),
            ("3", "00:00:04,000 --> 00:00:06,000",
             "Kendin için korkmuyorsan böyle davranmaya hakkın yok"),
            ("4", "00:00:06,000 --> 00:00:07,000", "ya."),
        ]
        self.assertEqual(_scan(src, blk), 0)

    def test_tag_wrapped_music_interjection_is_not_untranslated(self):
        source = (
            "248\n00:10:00,000 --> 00:10:02,000\n"
            "<i>♪ Hey, hey ♪</i>\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.srt"
            path.write_text(source, encoding="utf-8")
            warnings = gui.scan_translation_quality(
                str(path),
                [("248", "00:10:00,000 --> 00:10:02,000", "♪ Hey, hey ♪")],
                src_clean_map={"248": "♪ Hey, hey ♪"},
                source_language="English",
            )
        self.assertEqual(warnings, 0)

    def test_short_tag_question_translation_is_not_length_outlier(self):
        src = {
            "476": "do you think a working girl is just sitting around",
            "477": "waiting at your disposal, huh?",
        }
        blk = [
            ("476", "00:20:00,000 --> 00:20:03,000",
             "Bir hayat kadınının emrinde öylece oturup beklediğini mi sanıyorsun,"),
            ("477", "00:20:03,000 --> 00:20:04,000", "ha?"),
        ]
        self.assertEqual(_scan(src, blk), 0)

    def test_isolated_truncation_remains_length_outlier(self):
        src = {"1": "This complete sentence contains important information."}
        blk = [("1", "00:00:01,000 --> 00:00:03,000", "Bu")]
        self.assertEqual(_scan(src, blk), 1)

    def test_source_aware_residue_uses_timestamp_when_ids_shift(self):
        source = (
            "765\n00:37:54,576 --> 00:37:56,099\n"
            "The aluminum is amalgamated with aqueous mercury nitrate.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.srt"
            path.write_text(source, encoding="utf-8")
            warnings = gui.scan_translation_quality(
                str(path),
                [("766", "00:37:54,576 --> 00:37:56,099",
                  "Alüminyum aqueous mercury nitrate ile amalgamlanır.")],
                src_clean_map={"765": "The aluminum is amalgamated with aqueous mercury nitrate."},
                source_language="English",
            )
        self.assertGreaterEqual(warnings, 1)


if __name__ == "__main__":
    unittest.main()
