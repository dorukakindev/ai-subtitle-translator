"""validate_condense_candidate (hybrid_translate.py) — condense_fast_lines için DAR
güvenlik doğrulaması. Bkz. plans/condense-safety-validators-brief.md.

Kritik tasarım kararı: validate_polish_candidate'in AKSİNE, kelime-kaybı/çok-kısa
kontrolleri BİLEREK YOK — condense kelime atmayı ve kısaltmayı KASITLI yapar; bu
dosyanın en önemli testi meşru kısaltmanın REDDEDİLMEDİĞİNİ kilitler.
"""
import unittest

import hybrid_translate as ht


class LegitimateShorteningAcceptedTest(unittest.TestCase):
    def test_word_dropped_but_safe_shortening_accepted(self):
        # condense'in özü budur — loss guard'ı kasıtlı yok, bu test tasarım
        # kararını kilitler.
        ok, reason = ht.validate_condense_candidate(
            "Bu çok uzun bir cümle, birçok gereksiz kelimeyle dolu.",
            "Uzun bir cümle burada.",
        )
        self.assertTrue(ok, msg=reason)

    def test_filler_removal_accepted(self):
        ok, reason = ht.validate_condense_candidate(
            "Şey, yani, aslında bence bu doğru olabilir.",
            "Bence bu doğru olabilir.",
        )
        self.assertTrue(ok, msg=reason)


class NewLeakRejectedTest(unittest.TestCase):
    def test_new_non_turkish_leak_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "Bu bir yılbaşı partisiydi.",
            "Bir bäýram/holidaý oturylyşyğıydı.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "non_turkish_target")


class IntroducedTypoRejectedTest(unittest.TestCase):
    def test_doubled_letter_typo_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "Şu an kafamdaki tek sorun bu.",
            "Şu an kafamdaki ttek sorun.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "introduced_typo")


class NumberDropRejectedTest(unittest.TestCase):
    def test_number_dropped_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "Bunun bedeli 150 lira tuttu.",
            "Bunun bedeli lira tuttu.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "numbers")


class NegationLossRejectedTest(unittest.TestCase):
    def test_negation_flip_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "katılmıyorum",
            "katılıyorum",
            source_text="I do NOT agree",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "source_negation")


class ContentWordDriftRejectedTest(unittest.TestCase):
    def test_unrelated_new_content_word_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "Adam kapıyı açtı ve içeri girdi.",
            "Kadın pencereyi kırdı ve dışarı çıktı.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "content_word_drift")


class FormatTagRejectedTest(unittest.TestCase):
    def test_dropped_italic_tag_rejected(self):
        ok, reason = ht.validate_condense_candidate(
            "<i>Bu önemli bir cümledir.</i>",
            "Bu önemli bir cümledir.",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "format_tags")


class EmptyCandidateRejectedTest(unittest.TestCase):
    def test_empty_candidate_rejected(self):
        ok, reason = ht.validate_condense_candidate("Bir şeyler.", "")
        self.assertFalse(ok)
        self.assertEqual(reason, "empty")


if __name__ == "__main__":
    unittest.main()
