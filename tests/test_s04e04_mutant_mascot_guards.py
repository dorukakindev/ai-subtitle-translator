"""S04E04 (Mutant Mascot) gerçek çıktısında görülen kalıntılar:
- Türkmence 'gowak'/'otag' sızıntısı ("WELCOME TO THE INNER LAIR" satırı)
- Polish geçişinin ürettiği yazım hatası ('tek' -> 'ttek')
- Kaynakta olmayan parantezli çevirmen notu eklenmesi ('(Doğu Yakası mahallesi)')
- Kaynakta olmayan ' / ' ile ayrılmış alternatif çeviri ('İçki gowak / içki otag'a')
"""
import unittest

import hybrid_translate as ht


class Cue:
    def __init__(self, index, text):
        self.index = index
        self.text = text


class InnerLairPhraseFixTest(unittest.TestCase):
    def test_inner_lair_singular_variant(self):
        self.assertEqual(
            ht._apply_local_fixes(
                "İçki gowak / içki otag'a hoş geldin. Ryan: Çok güzel, dostum."
            )[0],
            "İç mabede hoş geldin. Ryan: Çok güzel, dostum.",
        )

    def test_inner_lair_plural_variant_no_apostrophe(self):
        self.assertEqual(
            ht._apply_local_fixes("İçki gowak / içki otaga hoş geldiniz.")[0],
            "İç mabede hoş geldiniz.",
        )


class IntroducedTypoFixTest(unittest.TestCase):
    def test_ttek_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Şu an kafamdaki ttek sorun galiba,")[0],
            "Şu an kafamdaki tek sorun galiba,",
        )


class MutantMascotDetectionTest(unittest.TestCase):
    def test_source_lang_leftover_matches(self):
        for word in ("gowak", "otag", "otaga", "otagy"):
            self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search(word), word)

    def test_turkic_drift_matches(self):
        for word in ("gowak", "otag", "otaga", "otagy"):
            self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search(word), word)

    def test_leak_detector_fires_for_real_line(self):
        self.assertTrue(
            ht.has_non_turkish_target_leak("İçki gowak / içki otaga hoş geldiniz.")
        )

    def test_no_false_positive_on_otag_with_g_breve(self):
        # Gerçek Türkçe "otağ" (ğ ile) hiçbir zaman "otag" (g ile) yazılmaz —
        # yanlış alarm vermemeli.
        self.assertFalse(
            ht.has_non_turkish_target_leak("Padişahın otağı ovaya kuruldu.")
        )

    def test_apply_local_fixes_noop_on_clean_turkish(self):
        self.assertEqual(
            ht._apply_local_fixes("İyi ki geldin.")[0],
            "İyi ki geldin.",
        )


class IntroducedTypoValidatorTest(unittest.TestCase):
    def test_rejects_doubled_letter_typo(self):
        ok, reason = ht.validate_polish_candidate(
            "Şu an kafamdaki tek sorun galiba,",
            "Şu an kafamdaki ttek sorun galiba,",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "introduced_typo")

    def test_allows_legitimate_interjection_unchanged(self):
        # Bracket kaybı ayrı bir kuralla (bracket_labels) reddedilir — burada
        # doğrulanan şey sadece introduced_typo'nun yanlış alarm vermediği.
        _ok, reason = ht.validate_polish_candidate("Aaa.", "Aaa.")
        self.assertNotEqual(reason, "introduced_typo")

    def test_does_not_flag_short_interjection_intensifier(self):
        # "Aa" -> "Aaa" gibi kısa ünlem uzatmaları (2-3 harf) yanlış alarm vermemeli.
        ok, reason = ht.validate_polish_candidate("Aa!", "Aaa!")
        self.assertNotEqual(reason, "introduced_typo")


class ParenNoteValidatorTest(unittest.TestCase):
    def test_flags_parenthetical_note_absent_from_source(self):
        cues = [Cue(1, "FROM OUR OLD LOCATION HERE IN THE EAST VILLAGE.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000",
                   "öteye, East Village'a (Doğu Yakası mahallesi) taşıdık.")]
        hits = ht.run_validators(blocks, cues)
        self.assertTrue(any("PAREN_NOTE" in hit[3] for hit in hits))

    def test_no_flag_when_source_has_parentheses(self):
        cues = [Cue(1, "HE SAID (QUIETLY) THAT HE WAS FINE.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000",
                   "(sessizce) iyi olduğunu söyledi.")]
        hits = ht.run_validators(blocks, cues)
        self.assertFalse(any("PAREN_NOTE" in hit[3] for hit in hits))

    def test_flags_paren_note_even_when_source_has_sfx_bracket(self):
        # S04E12 #17 gerçek vakası: kaynakta '[' (SFX etiketi) var ama '(' yok —
        # eski kod "[" not in orig_clean şartıyla bunu YANLIŞLIKLA muaf tutuyordu.
        cues = [Cue(17, "[ Chuckling ] ONLY IN NEW YORK.")]
        blocks = [(17, "00:00:00,000 --> 00:00:01,000",
                   "[KIKIRDAMA] Sadece New York (New York açıklaması).")]
        hits = ht.run_validators(blocks, cues)
        reasons = [hit[3] for hit in hits]
        self.assertTrue(any("PAREN_NOTE" in r for r in reasons))
        # SFX_LEFTOVER de aynı anda tetiklenmeye devam etmeli — biri diğerini dışlamaz.
        self.assertTrue(any("SFX_LEFTOVER" in r for r in reasons))


class AltSlashValidatorTest(unittest.TestCase):
    def test_flags_alternative_translation_slash(self):
        cues = [Cue(1, "WELCOME TO THE INNER LAIR.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000",
                   "İçki gowak / içki otaga hoş geldiniz.")]
        hits = ht.run_validators(blocks, cues)
        self.assertTrue(any("ALT_SLASH" in hit[3] for hit in hits))

    def test_no_flag_when_source_has_slash(self):
        cues = [Cue(1, "OPEN 24 / 7 EVERY DAY.")]
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Her gün 24 / 7 açık.")]
        hits = ht.run_validators(blocks, cues)
        self.assertFalse(any("ALT_SLASH" in hit[3] for hit in hits))


class PromptAlignmentTest(unittest.TestCase):
    """CLAUDE.md: sync ve hybrid promptları semantik olarak hizalı kalmalı."""

    def test_sync_prompt_forbids_parenthetical_notes(self):
        import subtitle_translator_gui as gui
        p = gui._build_sync_system_prompt("English", "Turkish", None, "Orta")
        self.assertIn("parenthetical translator notes", p)

    def test_hybrid_prompt_source_forbids_parenthetical_notes(self):
        from pathlib import Path
        src = Path("hybrid_translate.py").read_text(encoding="utf-8")
        self.assertIn("parenthetical translator notes", src)


if __name__ == "__main__":
    unittest.main()
