"""Tests for Secret Life of Symbols output-driven residue guards."""
import unittest
import hybrid_translate as ht


class GodAllahResidueTest(unittest.TestCase):
    def test_god_allah_fixed(self):
        text, n = ht._apply_local_fixes("God / Allah")
        self.assertEqual(text, "Tanrı")

    def test_god_allah_plain_fixed(self):
        text, n = ht._apply_local_fixes("God / Allah")
        self.assertEqual(text, "Tanrı")

    def test_god_allah_with_suffix_fixed(self):
        text, n = ht._apply_local_fixes("God / Allah'tan")
        self.assertEqual(text, "Tanrı'tan")

    def test_god_allah_not_in_normal(self):
        text, n = ht._apply_local_fixes("Tanrı")
        self.assertEqual(text, "Tanrı")
        self.assertEqual(n, 0)


class BibleResidueTest(unittest.TestCase):
    def test_bible_fixed(self):
        text, n = ht._apply_local_fixes("Bible")
        self.assertEqual(text, "Kutsal Kitap")

    def test_hebrew_bible_fixed(self):
        text, n = ht._apply_local_fixes("Hebrew Bible")
        self.assertEqual(text, "İbrani Kutsal Kitabı")

    def test_bible_en_leftover_flagged(self):
        self.assertTrue(ht._EN_LEFTOVER.search("Bible"))

    def test_bible_locative_fixed(self):
        text, n = ht._apply_local_fixes("Bible'da")
        self.assertEqual(text, "Kutsal Kitap'ta")

    def test_bible_locative_right_apostrophe_fixed(self):
        text, n = ht._apply_local_fixes("Bible\u2019da")
        self.assertEqual(text, "Kutsal Kitap'ta")

    def test_bible_ablative_fixed(self):
        text, n = ht._apply_local_fixes("Bible'dan")
        self.assertEqual(text, "Kutsal Kitap'tan")

    def test_bible_ablative_right_apostrophe_fixed(self):
        text, n = ht._apply_local_fixes("Bible\u2019dan")
        self.assertEqual(text, "Kutsal Kitap'tan")

    def test_bible_accusative_fixed(self):
        text, n = ht._apply_local_fixes("Bible'ı")
        self.assertEqual(text, "Kutsal Kitap'ı")

    def test_bible_genitive_fixed(self):
        text, n = ht._apply_local_fixes("Bible'ın")
        self.assertEqual(text, "Kutsal Kitap'ın")

    def test_bible_genitive_front_vowel_fixed(self):
        text, n = ht._apply_local_fixes("Bible'in")
        self.assertEqual(text, "Kutsal Kitap'ın")


class SourceLangResidueTest(unittest.TestCase):
    def test_ilaahyada_flagged(self):
        self.assertTrue(ht._SOURCE_LANG_LEFTOVER.search("ilaahyada"))

    def test_doorashada_flagged(self):
        self.assertTrue(ht._SOURCE_LANG_LEFTOVER.search("doorashada"))

    def test_tawxiid_flagged(self):
        self.assertTrue(ht._SOURCE_LANG_LEFTOVER.search("tawxiid"))


class CibraaniContextTest(unittest.TestCase):
    def test_cibraani_dilinde_fixed(self):
        text, n = ht._apply_local_fixes("Cibraani dilinde")
        self.assertEqual(text, "İbranice")

    def test_cibraani_sozcugu_fixed(self):
        text, n = ht._apply_local_fixes("Cibraani sözcüğü")
        self.assertEqual(text, "İbranice")

    def test_cibraani_plural_fixed(self):
        text, n = ht._apply_local_fixes("kadim Cibraaniler")
        self.assertEqual(text, "kadim İbraniler")

    def test_cibraani_tanrisi_fixed(self):
        text, n = ht._apply_local_fixes("Cibraani tanrısı")
        self.assertEqual(text, "İbrani tanrısı")

    def test_cibraani_gelenegi_fixed(self):
        text, n = ht._apply_local_fixes("Cibraani geleneği")
        self.assertEqual(text, "İbrani geleneği")

    def test_cibraani_standalone_fixed(self):
        text, n = ht._apply_local_fixes("Cibraani")
        self.assertEqual(text, "İbrani")


class HenotheismMonotheismTest(unittest.TestCase):
    def test_henotheism_en_leftover_flagged(self):
        self.assertTrue(ht._EN_LEFTOVER.search("henotheism"))

    def test_monotheism_en_leftover_flagged(self):
        self.assertTrue(ht._EN_LEFTOVER.search("monotheism"))

    def test_henotheism_fixed(self):
        text, n = ht._apply_local_fixes("henotheism")
        self.assertEqual(text, "henoteizm")

    def test_monotheism_fixed(self):
        text, n = ht._apply_local_fixes("monotheism")
        self.assertEqual(text, "tek tanrıcılık")

    def test_monotheism_tawxiid_compound_fixed(self):
        text, n = ht._apply_local_fixes(
            "monotheism / tawxiid olarak başlamadı")
        self.assertEqual(text, "tek tanrıcılık olarak başlamadı")

    def test_henotheism_doorashada_compound_fixed(self):
        text, n = ht._apply_local_fixes(
            "henotheism / doorashada hal ilaah oo ka mid ah kuwo badan")
        self.assertEqual(text, "henoteizm")


class QuranResidueTest(unittest.TestCase):
    def test_quran_fixed(self):
        text, n = ht._apply_local_fixes("Quran")
        self.assertEqual(text, "Kuran")

    def test_quran_en_leftover_flagged(self):
        self.assertTrue(ht._EN_LEFTOVER.search("Quran"))


class ShortSourceOverexpansionTest(unittest.TestCase):
    def test_short_source_long_target_flagged(self):
        self.assertTrue(
            ht._has_short_source_overexpansion(
                "Bible.",
                "tanrısal çoğulluk üzerine makaleler vardı ve bunlar şekilde",
            )
        )

    def test_more_than_one_flagged(self):
        self.assertTrue(
            ht._has_short_source_overexpansion(
                "More than one.",
                "bize benzeyen yaratıcılar gibi olduğumuzu, birden fazla tanrı",
            )
        )

    def test_after_our_likeness_flagged(self):
        self.assertTrue(
            ht._has_short_source_overexpansion(
                "after our likeness.",
                "onu kendi suretimizde, benzeyişimize göre yapalım dediler artık",
            )
        )

    def test_normal_not_flagged(self):
        self.assertFalse(
            ht._has_short_source_overexpansion(
                "The Bible says God made man in his image.",
                "Kutsal Kitap Tanrı'nın insanı kendi suretinde yarattığını söyler.",
            )
        )

    def test_short_source_medium_target_not_flagged(self):
        self.assertFalse(
            ht._has_short_source_overexpansion(
                "God created.",
                "Tanrı yarattı",
            )
        )

    def test_short_source_overexpansion_in_run_validators(self):
        class FakeCue:
            index = 1
            text = "Bible"
        tr_blocks = [("1", "00:00:01 --> 00:00:04",
                      "tanrısal çoğulluk üzerine makaleler vardı ve bunlar şekilde")]
        suspicious = ht.run_validators(tr_blocks, cues=[FakeCue()])
        reasons = [r for _, _, _, r in suspicious
                   if "SHORT_SOURCE_OVEREXPANSION" in r]
        self.assertEqual(len(reasons), 1)

    def test_short_source_overexpansion_polish_rejected(self):
        ok, reason = ht.validate_polish_candidate(
            "Kutsal Kitap'ta.",
            "Kutsal Kitap'ta tanrısal çoğulluk üzerine makaleler vardı ve bunlar",
            source_text="Bible.",
        )
        self.assertFalse(ok)
        self.assertIn("short_source_overexpansion", reason)

    def test_adm_not_falsely_flagged(self):
        text, n = ht._apply_local_fixes("Adm")
        self.assertEqual(text, "Adm")
        self.assertEqual(n, 0)

    def test_ish_not_falsely_flagged(self):
        text, n = ht._apply_local_fixes("Ish")
        self.assertEqual(text, "Ish")
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()


