# -*- coding: utf-8 -*-
"""HARIC_YENI_BUG_DENETIMI_2026-08-21.md — madde 1-6 regresyon testleri."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompt_constants  # noqa: F401  (import zinciri)
import subtitle_formats as sf
import subtitle_translator_gui as g
import translation_memory as tm


class VisibleSemanticGateTest(unittest.TestCase):
    """Madde 1: hata ve boşluk denetimi GÖRÜNÜR metin üzerinden yapılmalı."""

    SOURCE = [("1", "00:00:01,000 --> 00:00:03,000", "Hello.")]

    def _blocks(self, target):
        return [("1", "00:00:01,000 --> 00:00:03,000", target)]

    def test_wrapped_markers_and_empty_targets_are_not_complete(self):
        for target in ("<i>[HATA]</i>", "<i></i>", "...", "—",
                       "{\\an8}[HATA]", "<font color=\"#fff\"> </font>",
                       "[HATA]", "[ÇEVİRİ EKSİK]"):
            with self.subTest(target=target):
                self.assertFalse(
                    g._existing_output_is_complete(
                        self._blocks(target), self.SOURCE))

    def test_a_real_translation_is_still_complete(self):
        self.assertTrue(
            g._existing_output_is_complete(self._blocks("Merhaba."), self.SOURCE))

    def test_a_wordless_source_licenses_a_wordless_target(self):
        # Dosyada en az bir sozcuklu cue olmali; ikinci cue noktalama-only.
        source = [("1", "00:00:01,000 --> 00:00:03,000", "Hello."),
                  ("2", "00:00:04,000 --> 00:00:05,000", "...")]
        output = [("1", "00:00:01,000 --> 00:00:03,000", "Merhaba."),
                  ("2", "00:00:04,000 --> 00:00:05,000", "...")]
        self.assertTrue(g._existing_output_is_complete(output, source))

    def test_wrapped_marker_counts_as_a_translation_failure(self):
        self.assertTrue(
            g._blocks_have_translation_failures(self._blocks("<i>[HATA]</i>")))
        self.assertTrue(
            g._blocks_have_translation_failures(self._blocks("<i></i>")))
        self.assertFalse(
            g._blocks_have_translation_failures(self._blocks("Merhaba.")))

    def test_wordless_target_needs_the_source_to_be_flagged(self):
        blocks = self._blocks("—")
        self.assertFalse(g._blocks_have_translation_failures(blocks))
        self.assertTrue(
            g._blocks_have_translation_failures(blocks, {"1": "Hello."}))

    def test_translation_memory_rejects_wrapped_markers(self):
        for target in ("<i>[HATA]</i>", "<i></i>", "[HATA]", "[ÇEVİRİ EKSİK]"):
            with self.subTest(target=target):
                self.assertTrue(tm._is_missing_translation(target))
        self.assertFalse(tm._is_missing_translation("Merhaba."))

    def test_the_shared_reason_layer_names_the_problem(self):
        self.assertEqual(
            sf.translation_failure_reason("<i>[HATA]</i>", "Hello."),
            "hata_isareti")
        self.assertEqual(
            sf.translation_failure_reason("<i></i>", "Hello."), "bos_hedef")
        self.assertEqual(
            sf.translation_failure_reason("—", "Hello."), "sozcuksuz_hedef")
        self.assertEqual(sf.translation_failure_reason("—", "—"), "")


class UnknownAngleBracketContentTest(unittest.TestCase):
    """Madde 2: `<Enter>` gibi gerçek kaynak içeriği silinmemeli."""

    def test_unknown_bracketed_content_survives(self):
        for value in ("Press <Enter> now.",
                      "The variable <x> is unknown.",
                      "Send it to <PRIVATE_PERSON>.",
                      "<BAD_TAG>x</BAD_TAG>"):
            with self.subTest(value=value):
                self.assertEqual(
                    sf.clean_translation_source_text(value), value)

    def test_real_format_tags_are_still_stripped(self):
        self.assertEqual(
            sf.clean_translation_source_text("<i>Hello.</i>"), "Hello.")
        self.assertEqual(
            sf.clean_translation_source_text("<b>Bold</b> and <u>under</u>"),
            "Bold and under")
        self.assertEqual(
            sf.clean_translation_source_text('<font color="#fff">Renk</font>'),
            "Renk")

    def test_the_vtt_voice_tag_is_still_preserved(self):
        self.assertEqual(
            sf.clean_translation_source_text("<v Ali>Merhaba</v>"),
            "<v Ali>Merhaba</v>")

    def test_bare_comparison_operators_are_untouched(self):
        self.assertEqual(
            sf.clean_translation_source_text("5 < 7 and 8 > 3"),
            "5 < 7 and 8 > 3")


class TargetScriptAwarenessTest(unittest.TestCase):
    """Madde 3: hedef dilin kendi alfabesi yabancı sayılmamalı."""

    SAMPLES = (("Arabic", "مرحبا"), ("Russian", "Привет"),
               ("Japanese", "こんにちは"), ("Chinese", "你好"),
               ("Korean", "안녕하세요"))

    @staticmethod
    def _blocks(text):
        return [("1", "00:00:01,000 --> 00:00:03,000", text)]

    def test_each_target_accepts_its_own_script(self):
        for language, text in self.SAMPLES:
            with self.subTest(language=language):
                self.assertEqual(
                    g._foreign_script_ids(self._blocks(text), language), [])

    def test_turkish_still_rejects_every_foreign_script(self):
        for language, text in self.SAMPLES:
            with self.subTest(language=language):
                self.assertEqual(
                    g._foreign_script_ids(self._blocks(text), "Turkish"), ["1"])

    def test_a_russian_target_still_catches_arabic_leakage(self):
        self.assertEqual(
            g._foreign_script_ids(self._blocks("Привет مرحبا"), "Russian"),
            ["1"])

    def test_latin_names_and_numbers_are_fine_in_any_target(self):
        for language, _text in self.SAMPLES:
            with self.subTest(language=language):
                self.assertEqual(
                    g._foreign_script_ids(
                        self._blocks("NASA 1969"), language), [])


class HattedLetterPolicyIsTurkishOnlyTest(unittest.TestCase):
    """Madde 4: Fransizca `a/i/u` sapkali harfleri sert hata olmamali."""

    TIMESTAMP = "00:00:01,000 --> 00:00:03,000"

    def _audit(self, target_text, language):
        with tempfile.TemporaryDirectory() as folder:
            source_path = os.path.join(folder, "in.srt")
            output_path = os.path.join(folder, "out.srt")
            for path, body in ((source_path, "Thanks to him."),
                               (output_path, target_text)):
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(("1", self.TIMESTAMP, body, "", "")))
            return g._subtitle_delivery_audit(
                source_path, output_path, target_language=language)

    def test_french_hatted_letters_are_not_counted(self):
        audit = self._audit("Grâce à lui. Âme sûre.", "French")
        self.assertEqual(audit.get("hatted_letters"), 0)

    def test_turkish_still_counts_them(self):
        audit = self._audit("Kâr âlem sûret îman.", "Turkish")
        self.assertGreater(audit.get("hatted_letters"), 0)


class MeaningfulUnicodeControlsTest(unittest.TestCase):
    """Madde 5: ZWJ/ZWNJ ve bidi isolate anlam taşıdığında korunmalı."""

    def test_emoji_and_rtl_sequences_round_trip(self):
        for value in ("\U0001F469‍\U0001F469‍\U0001F467‍\U0001F466",
                      "قال ⁦NASA⁩ اليوم",
                      "می‌روم"):
            with self.subTest(value=value):
                self.assertEqual(
                    sf.normalize_subtitle_control_artifacts(value), value)

    def test_latin_internal_joiners_are_still_removed(self):
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("A‍B"), "AB")
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("A‌B"), "AB")

    def test_known_artefacts_are_still_cleaned(self):
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("﻿Merhaba"), "Merhaba")
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("ay­ni"), "ayni")
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("a‎b"), "ab")
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("a b"), "a b")


class AllCapsDeliveryNormalisationTest(unittest.TestCase):
    """Madde 6: kısaltmalar, Roma rakamları ve noktalı `i` korunmalı."""

    @staticmethod
    def _run(target, source):
        blocks = [("1", "00:00:01,000 --> 00:00:03,000", target)]
        out, _n = g._normalize_all_caps_delivery(blocks, {"1": source})
        return out[0][2]

    def test_acronyms_survive(self):
        for target, source, expected in (
                ("LSD VE MDMA", "LSD AND MDMA", "LSD ve MDMA"),
                ("DMT ETKISI", "DMT EFFECT", "DMT etkisi"),
                ("NYPD GELDI", "NYPD ARRIVED", "NYPD geldi"),
                ("UNESCO KARARI", "UNESCO DECISION", "UNESCO kararı")):
            with self.subTest(target=target):
                self.assertEqual(self._run(target, source), expected)

    def test_roman_numerals_survive(self):
        self.assertEqual(
            self._run("BÖLÜM VIII", "CHAPTER VIII"), "Bölüm VIII")
        self.assertEqual(
            self._run("II. DÜNYA SAVAŞI", "WORLD WAR II"), "II. Dünya savaşı")

    def test_ordinary_sentences_are_still_normalised(self):
        self.assertEqual(
            self._run("BU BIR CÜMLEDIR", "THIS IS A SENTENCE"),
            "Bu bir cümledir")
        self.assertEqual(
            self._run("BERLIN SOĞUKTU", "BERLIN WAS COLD"), "Berlin soğuktu")

    def test_ascii_i_follows_turkish_vowel_harmony(self):
        for target, source, expected in (
                ("ONU IYI TANIRIM", "I KNOW HIM WELL", "Onu iyi tanırım"),
                ("BILIYORUM KI", "I KNOW THAT", "Biliyorum ki"),
                ("INSAN HAKLARI", "HUMAN RIGHTS", "İnsan hakları"),
                ("KIZ KARDEŞIM", "MY SISTER", "Kız kardeşim")):
            with self.subTest(target=target):
                self.assertEqual(self._run(target, source), expected)


if __name__ == "__main__":
    unittest.main()
