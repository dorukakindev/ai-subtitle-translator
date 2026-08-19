# -*- coding: utf-8 -*-
"""2026-08-20 ikinci tur: kendi eklediğimiz tespitçilerin yanlış pozitifleri."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class MissingPredicateTest(unittest.TestCase):
    def test_ordinary_verb_final_sentences_are_not_flagged(self):
        blocks = [
            ("1", "ts", "Bugün eve gitti."),
            ("2", "ts", "Sonra kapıyı açtı."),
            ("3", "ts", "Adam bahçeye çıktı."),
            ("4", "ts", "Herkes onu bekliyordu."),
            ("5", "ts", "Çocuk okula başladı."),
            ("6", "ts", "Annesi çok sevindi."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), [])

    def test_noun_case_ending_alone_is_not_enough(self):
        blocks = [("1", "ts", "Sabah erkenden şehre."), ("2", "ts", "Yola çıktık.")]
        self.assertEqual(g._missing_predicate_ids(blocks), [])

    def test_verbal_noun_ending_is_flagged(self):
        blocks = [
            ("80", "ts", "Kalabalığı denetleyip ölüm arabasının hastaneye gitmesine."),
            ("81", "ts", "Sonraki cümle burada başlıyor."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), ["80"])

    def test_infinitive_ending_is_flagged(self):
        blocks = [
            ("10", "ts", "Tek amaçları o kapıyı açmak."),
            ("11", "ts", "Ama başaramadılar."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), ["10"])

    def test_continuation_cue_is_not_flagged(self):
        blocks = [
            ("10", "ts", "Tek amaçları o kapıyı açmak."),
            ("11", "ts", "ve içeri girmekti."),
        ]
        self.assertEqual(g._missing_predicate_ids(blocks), [])


class AddressRegisterMixTest(unittest.TestCase):
    def test_false_stems_do_not_count_as_informal(self):
        blocks = [(str(i), "ts", "Bu bir reçine ve resin karışımıdır.")
                  for i in range(1, 26)]
        result = g.detect_address_register_mix(blocks)
        self.assertEqual((result["informal"], result["formal"]), (0, 0))
        self.assertFalse(result["mixed"])

    def test_other_false_stems(self):
        for word in ("kesin", "bütün", "basın", "düşün", "üstün"):
            blocks = [(str(i), "ts", "Bu %s bir şey." % word) for i in range(1, 20)]
            with self.subTest(word=word):
                self.assertEqual(g.detect_address_register_mix(blocks)["informal"], 0)

    def test_real_mix_is_still_detected(self):
        blocks = ([(str(i), "ts", "Sen ne yaptın?") for i in range(1, 21)]
                  + [(str(i), "ts", "Siz ne yaptınız?") for i in range(21, 31)])
        result = g.detect_address_register_mix(blocks)
        self.assertEqual((result["informal"], result["formal"]), (20, 10))
        self.assertTrue(result["mixed"])

    def test_uniform_formal_file_is_not_mixed(self):
        blocks = [(str(i), "ts", "Siz ne düşünüyorsunuz?") for i in range(1, 31)]
        result = g.detect_address_register_mix(blocks)
        self.assertEqual(result["informal"], 0)
        self.assertFalse(result["mixed"])


class ScanLockedTermsTest(unittest.TestCase):
    def test_locked_proper_noun_is_not_source_residue(self):
        blocks = [("1", "ts", "Ocidente'de yaşayanlar."), ("2", "ts", "Sun'ın evi.")]
        cues = [(1, "ts", "In the Ocidente."), (2, "ts", "Sun's house.")]
        source_cues = [type("C", (), {"index": i, "text": t})()
                       for i, _ts, t in cues]
        loose = g._scan_delivery_blocks(blocks, source_cues)
        tight = g._scan_delivery_blocks(
            blocks, source_cues, locked_terms={"Ocidente": "Ocidente", "Sun": "Sun"})
        self.assertGreaterEqual(loose["source_residue"], tight["source_residue"])


class ForeignTitleFalsePositiveTest(unittest.TestCase):
    def test_all_caps_abbreviation_is_not_a_title(self):
        for text in ("MS hastası olduğunu söyledi.", "Bu bir MS taraması.",
                     "MR çekildi bugün."):
            with self.subTest(text=text):
                self.assertEqual(g.normalize_foreign_titles(text), (text, 0))

    def test_turkish_doctor_abbreviations_are_left_alone(self):
        for text in ("Dr. Ahmet geldi.", "Prof. Dr. Ayşe Yılmaz konuştu."):
            with self.subTest(text=text):
                self.assertEqual(g.normalize_foreign_titles(text), (text, 0))

    def test_real_foreign_titles_are_still_normalized(self):
        self.assertEqual(g.normalize_foreign_titles("Mr. Yi dedi.")[0],
                         "Bay Yi dedi.")
        self.assertEqual(g.normalize_foreign_titles("Miss Xiao girdi.")[0],
                         "Bayan Xiao girdi.")
        self.assertEqual(g.normalize_foreign_titles("Professor Sun konuştu.")[0],
                         "Profesör Sun konuştu.")


class SuffixBufferLetterTest(unittest.TestCase):
    def test_buffer_letter_follows_the_new_stem(self):
        # 'India'ya' → 'Hindistan'a' (eskiden 'Hindistan'ya' yazılıyordu)
        self.assertEqual(g.turkish_suffix_for_stem("Hindistan", "ya"), "a")
        self.assertEqual(g.turkish_suffix_for_stem("Amerika", "e"), "ya")
        self.assertEqual(g.turkish_suffix_for_stem("Yunanistan", "yi"), "ı")
        self.assertEqual(g.turkish_suffix_for_stem("Almanya", "in"), "nın")
        self.assertEqual(g.turkish_suffix_for_stem("Çin", "nin"), "in")

    def test_exonym_end_to_end(self):
        for text, expected in (
                ("India'ya gitti.", "Hindistan'a gitti."),
                ("China'daki fabrika.", "Çin'deki fabrika."),
                ("Greece'in tarihi.", "Yunanistan'ın tarihi."),
                ("Japan'a uçtu.", "Japonya'ya uçtu.")):
            with self.subTest(text=text):
                self.assertEqual(g.normalize_foreign_exonyms(text)[0], expected)


class CapitalisedCommonNounApostropheTest(unittest.TestCase):
    def test_source_lowercase_stem_loses_apostrophe_and_capital(self):
        out, count = g.fix_source_lowercase_apostrophes(
            "Beynin Dura'sı kesilir.", "The dura of the brain is cut.")
        self.assertEqual((out, count), ("Beynin durası kesilir.", 1))

    def test_line_initial_keeps_its_capital(self):
        out, _ = g.fix_source_lowercase_apostrophes(
            "Lamina'yı çıkardılar.", "They removed the lamina.")
        self.assertEqual(out, "Laminayı çıkardılar.")

    def test_proper_noun_is_untouched(self):
        for tr, src in (("Bugün Ankara'ya gitti.", "He went to Ankara today."),
                        ("O gün Lee'nin evindeydi.", "He was at Lee's house."),
                        ("Sonra Roma'ya döndü.", "He returned to rome and Roma.")):
            with self.subTest(tr=tr):
                self.assertEqual(g.fix_source_lowercase_apostrophes(tr, src),
                                 (tr, 0))

    def test_possessive_suffix_is_recognised(self):
        self.assertEqual(g.fix_common_noun_apostrophes("dura'sı kesildi")[0],
                         "durası kesildi")
        self.assertEqual(g.fix_common_noun_apostrophes("lamina'sını aldı")[0],
                         "laminasını aldı")
        self.assertEqual(g.fix_common_noun_apostrophes("d'Artagnan geldi")[0],
                         "d'Artagnan geldi")


class RepeatedHeadSyllableTest(unittest.TestCase):
    def test_typo_is_found_when_correct_form_exists_in_file(self):
        blocks = [("54", "ts", "15. yüzyıl Avrupası, neneredeyse karanlıktı."),
                  ("55", "ts", "Neredeyse hiç kimse okuma bilmiyordu.")]
        self.assertEqual(g._repeated_head_typo_ids(blocks),
                         [("54", "neneredeyse", "neredeyse")])

    def test_real_words_are_not_flagged(self):
        blocks = [("1", "ts", "Kakaosunu içti ve dışarı çıktı."),
                  ("2", "ts", "Babaannem bize geldi."),
                  ("3", "ts", "Bir hayat kadınının emrinde beklemek.")]
        self.assertEqual(g._repeated_head_typo_ids(blocks), [])

    def test_silent_when_correct_form_is_absent(self):
        blocks = [("1", "ts", "Bu neneredeyse tuhaf bir kelime."),
                  ("2", "ts", "Başka bir cümle.")]
        self.assertEqual(g._repeated_head_typo_ids(blocks), [])

class DeliveryScanInReportTest(unittest.TestCase):
    SCAN = {
        "missing": 0, "duplicates": 2, "cps": 5, "over_width": 3,
        "over_lines": 0, "cue_id_leak": 0, "midword_space": 1,
        "cue_fill": 2, "partial_echo": 1, "missing_predicate": 1,
        "source_residue": 4, "register_mixed": True, "syllable_typo": 1,
        "register": {"informal": 120, "formal": 300},
        "syllable_typo_details": [("54", "neneredeyse", "neredeyse")],
        "cue_fill_details": [],
    }

    def _report(self, scan):
        row = {"name": "Test.srt", "total": 700, "hata": 0, "dup": 2,
               "cps": 5, "delivery_scan": scan}
        return g.build_quality_report_text(
            [row], "gpt-5.4", "Turkish", "sync", 1000)

    def test_nonzero_classes_reach_the_report(self):
        text = self._report(self.SCAN)
        for expected in ("Teslim taraması:", "Aşırı uzun satır",
                         "Komşu cue'da kısmi yankı", "Yüklemsiz biten cue",
                         "Türkçe ekli kaynak kalıntısı",
                         "Dosya içinde sen/siz karışık",
                         "#54 'neneredeyse' → 'neredeyse'"):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_zero_classes_are_not_listed(self):
        text = self._report(self.SCAN)
        self.assertNotIn("Fazla satırlı cue", text)
        self.assertNotIn("Metne sızmış cue numarası", text)

    def test_clean_file_gets_no_scan_section(self):
        clean = {key: 0 for key in self.SCAN if key not in
                 ("register", "register_mixed", "syllable_typo_details",
                  "cue_fill_details")}
        clean.update({"register_mixed": False, "register": {},
                      "syllable_typo_details": [], "cue_fill_details": []})
        self.assertNotIn("Teslim taraması:", self._report(clean))

    def test_missing_scan_key_is_tolerated(self):
        row = {"name": "Test.srt", "total": 10, "hata": 0}
        text = g.build_quality_report_text(
            [row], "gpt-5.4", "Turkish", "sync", 10)
        self.assertNotIn("Teslim taraması:", text)

if __name__ == "__main__":
    unittest.main()
