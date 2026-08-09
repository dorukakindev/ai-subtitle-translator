"""
Oddities round — write_srt integration + S05E10 residue + S05E01 polish guards + Instant Chimera re-test.

1. write_srt integration test (local fixes applied at write time)
2. S05E10 residue (medisina, türme, ejir, azap, başy kesmek, mızrağı deken)
3. S05E01 polish regression guards
4. Instant Chimera guard re-test
"""

import os
import tempfile
import unittest
from pathlib import Path

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]


# ── 1. write_srt integration ──────────────────────────────────────────────

class WriteSrtIntegrationTest(unittest.TestCase):
    def _write_and_read(self, blocks):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.srt"
            __import__("subtitle_translator_gui", fromlist=["write_srt"]).write_srt(p, blocks)
            return p.read_text(encoding="utf-8")

    def test_turkic_residue_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bu bir vaxt mashinasi.")]
        raw = self._write_and_read(blocks)
        self.assertIn("vaxt mashinasi", raw)

    def test_detonatoer_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bu bir detonatör.")]
        raw = self._write_and_read(blocks)
        self.assertIn("detonatör", raw)

    def test_kulak_kapaklarimi_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Kulak kapaklarımı indireyim.")]
        raw = self._write_and_read(blocks)
        self.assertIn("Kulak kapaklarımı", raw)

    def test_medisina_nusgasy_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Bu bir medisina nusgasy.")]
        raw = self._write_and_read(blocks)
        self.assertIn("medisina nusgasy", raw)

    def test_hata_lines_not_corrupted_by_local_fixes(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        raw = self._write_and_read(blocks)
        self.assertIn("[HATA]", raw)

    def test_ceviri_eksik_not_corrupted(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]")]
        raw = self._write_and_read(blocks)
        self.assertIn("[ÇEVİRİ EKSİK]", raw)


# ── 2. S05E10 residue ─────────────────────────────────────────────────────

class MedisinaResidueTest(unittest.TestCase):
    def test_medisina_nusgasy_fixed(self):
        self.assertEqual(_APPLY("medisina nusgasy"), "tıbbi örnek")

    def test_medisina_koleksiyonu_fixed(self):
        self.assertEqual(_APPLY("medisina koleksiyonu"), "tıbbi örnek koleksiyonu")

    def test_medisina_fixed(self):
        self.assertEqual(_APPLY("medisina"), "tıbbi")

    def test_medisina_in_sentence_fixed(self):
        result = _APPLY("Bu bir medisina örneği.")
        self.assertEqual(result, "Bu bir tıbbi örneği.")

    def test_source_lang_leftover_matches_medisina(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("medisina"))

    def test_source_lang_leftover_matches_nusgasy(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("nusgasy"))

    def test_turkic_drift_re_matches_medisina(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("medisina"))

    def test_turkic_drift_re_matches_nusgasy(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("nusgasy"))


class TurmeResidueTest(unittest.TestCase):
    def test_turmede_fixed(self):
        self.assertEqual(_APPLY("türmede"), "hapishanede")

    def test_turme_fixed(self):
        self.assertEqual(_APPLY("türme"), "hapishane")

    def test_turme_in_sentence_fixed(self):
        result = _APPLY("Onu türmede tuttular.")
        self.assertEqual(result, "Onu hapishanede tuttular.")

    def test_source_lang_leftover_matches_turme(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("türme"))

    def test_turkic_drift_re_matches_turme(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("türme"))


class EjirAzapResidueTest(unittest.TestCase):
    def test_ejir_yetirmek_fixed(self):
        self.assertEqual(_APPLY("ejir ýetirmek"), "işkence")

    def test_azap_fixed(self):
        self.assertEqual(_APPLY("azap"), "işkence")

    def test_source_lang_leftover_matches_ejir(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("ejir"))

    def test_source_lang_leftover_matches_yetirmek(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("ýetirmek"))

    def test_turkic_drift_re_matches_ejir(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("ejir"))

    def test_turkic_drift_re_matches_yetirmek(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("ýetirmek"))


class BassyDekenResidueTest(unittest.TestCase):
    def test_basy_kesmek_fixed(self):
        self.assertEqual(_APPLY("başy kesmek"), "baş kesme")

    def test_mizragi_deken_fixed(self):
        self.assertEqual(_APPLY("mızrağı deken"), "mızrağı atan")

    def test_source_lang_leftover_matches_basy(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("başy"))

    def test_source_lang_leftover_matches_deken(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("deken"))

    def test_turkic_drift_re_matches_basy(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("başy"))

    def test_turkic_drift_re_matches_deken(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("deken"))


# ── 3. Polish regression guards ────────────────────────────────────────────

class PolishWelcomeDeletionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_welcome_deletion(self):
        ok, reason = self._validate("hoş geldiniz", "geldiniz")
        self.assertFalse(ok)
        self.assertEqual(reason, "welcome_deletion")

    def test_allows_unchanged_welcome(self):
        ok, _ = self._validate("hoş geldiniz", "hoş geldiniz")
        self.assertTrue(ok)


class PolishLetsSeeImperativeTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_bogulsun_regression(self):
        ok, reason = self._validate("boğuluşunu görelim", "boğulsun")
        self.assertFalse(ok)
        self.assertEqual(reason, "lets_see_to_imperative_regression")

    def test_allows_bogulsun_without_gorelim_context(self):
        ok, _ = self._validate("boğulsun", "boğulsun")
        self.assertTrue(ok)

    def test_allows_boguluşunu_gorelim_unchanged(self):
        ok, _ = self._validate("boğuluşunu görelim", "boğuluşunu görelim")
        self.assertTrue(ok)


class PolishInvitationSubjectTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_gelmeye_sevinirim(self):
        ok, reason = self._validate(
            "gelmenize sevinirim", "gelmeye sevinirim"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "invitation_subject_regression")

    def test_local_fix_cleans_gelmeye_sevinirim(self):
        self.assertEqual(_APPLY("gelmeye sevinirim"), "gelmenize sevinirim")

    def test_allows_unchanged(self):
        ok, _ = self._validate(
            "gelmenize sevinirim", "gelmenize sevinirim"
        )
        self.assertTrue(ok)


class PolishOdditiesIntroIdiomTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_suyunu_cikardik_with_ustalik(self):
        ok, reason = self._validate(
            "bu işteki ustalığımız", "işin suyunu çıkardık"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_idiom_regression")

    def test_rejects_suyunu_cikardik_with_ustalas(self):
        ok, reason = self._validate(
            "ustalaşmak", "işin suyunu çıkardık"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_idiom_regression")

    def test_rejects_suyunu_cikardik_with_sistemlestir(self):
        ok, reason = self._validate(
            "sistemleştirdik", "işin suyunu çıkardık"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_idiom_regression")

    def test_local_fix_cleans_suyunu_cikardik(self):
        self.assertEqual(
            _APPLY("işin suyunu çıkardık"),
            "işin tekniğini oturttuk",
        )

    def test_allows_suyunu_cikardik_without_intro_hint(self):
        ok, _ = self._validate(
            "normal bir şey", "normal bir şey oldu"
        )
        self.assertTrue(ok)


class PolishStoreDukkanTest(unittest.TestCase):
    def test_store_u_fixed(self):
        self.assertEqual(_APPLY("store'u"), "dükkânı")

    def test_store_unda_fixed(self):
        self.assertEqual(_APPLY("store'unda"), "dükkânında")

    def test_store_u_curly_apostrophe_fixed(self):
        self.assertEqual(_APPLY("store\u2019u"), "dükkânı")

    def test_store_unda_in_sentence_fixed(self):
        result = _APPLY("store'unda bir şey var")
        self.assertEqual(result, "dükkânında bir şey var")


# ── 4. Instant Chimera re-test ────────────────────────────────────────────

class InstantChimeraReTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_research_to_hunting_still_rejected(self):
        ok, reason = self._validate(
            "araştırıp seçerek...", "avlanıp seçerek..."
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "research_to_hunting_regression")

    def test_intro_regression_still_rejected(self):
        ok, reason = self._validate(
            "iyice ustalaştırmaya verdik", "bilim gibi yapmaya verdik"
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_detonatoer_still_fixed(self):
        self.assertEqual(_APPLY("Bu bir detonatör."), "Bu bir patlatıcı.")

    def test_kulak_kapaklarimi_still_fixed(self):
        self.assertEqual(
            _APPLY("Kulak kapaklarımı indireyim."),
            "Kulaklıklarımı indireyim.",
        )


# ── 5. Oddities intro title cleanup ───────────────────────────────────────

class OdditiesTitleCleanupTest(unittest.TestCase):
    def test_title_sira_disi_dunyaya_cleaned(self):
        result = _APPLY('SIRA DIŞI DÜNYAYA HOŞ GELDİNİZ\n"ODDITIES"\u2019İN')
        self.assertIn("ODDITIES", result)
        self.assertIn("sıra dışı dünyasına", result)
        self.assertNotIn("SIRA DIŞI DÜNYAYA", result)

    def test_title_tuhaf_dunyaya_cleaned(self):
        result = _APPLY('TUHAF DÜNYAYA HOŞ GELDİNİZ\n"ODDITIES"\u2019İN')
        self.assertIn("ODDITIES", result)
        self.assertIn("sıra dışı dünyasına", result)

    def test_title_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   'SIRA DIŞI DÜNYAYA HOŞ GELDİNİZ\n"ODDITIES"\u2019İN')]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.srt"
            __import__("subtitle_translator_gui", fromlist=["write_srt"]).write_srt(p, blocks)
            raw = p.read_text(encoding="utf-8")
        self.assertIn("ODDITIES", raw)
        self.assertIn("SIRA DIŞI DÜNYAYA", raw)


class OdditiesTitleVariantTest(unittest.TestCase):
    def test_title_sira_disi_dunyasi_cleaned(self):
        result = _APPLY('SIRA DIŞI DÜNYASI "ODDITIES"\u2019İN')
        self.assertIn("ODDITIES", result)
        self.assertNotIn("DÜNYASI", result)


# ── 6. Obscura grandma line ───────────────────────────────────────────────

class ObscuraGrandmaLineTest(unittest.TestCase):
    def test_obscura_grandma_line_fixed(self):
        result = _APPLY('OBSCURA annenizin antika dükkânı değil')
        self.assertEqual(result, 'Obscura, anneannenizin antikacısı değil')

    def test_obscura_grandma_is_not_rewritten_without_source(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   'OBSCURA annenizin antika dükkânı değil')]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.srt"
            __import__("subtitle_translator_gui", fromlist=["write_srt"]).write_srt(p, blocks)
            raw = p.read_text(encoding="utf-8")
        self.assertIn("OBSCURA", raw)
        self.assertIn("annenizin", raw)
        self.assertIn("antika dükkanı", raw)


class GrandmaToMotherRegressionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_anneanne_to_anne_in_antique_context(self):
        ok, reason = self._validate(
            "anneannenizin antikacısı değil",
            "annenizin antika dükkânı değil",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "grandma_to_mother_regression")

    def test_allows_anneanne_unchanged(self):
        ok, _ = self._validate(
            "anneannenizin antikacısı değil",
            "anneannenizin antikacısı değil",
        )
        self.assertTrue(ok)


# ── 7. Bilime döktük ──────────────────────────────────────────────────────

class BilimeDoktukTest(unittest.TestCase):
    def test_bilime_doktuk_fixed(self):
        result = _APPLY("bilime döktük")
        self.assertEqual(result, "bu işte iyice ustalaştık")

    def test_bilime_doktuk_in_sentence_fixed(self):
        result = _APPLY("bu işi bilime döktük")
        self.assertIn("ustalaştık", result)


class OdditiesIntroScienceLiteralRegressionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_bilime_doktuk_from_ustalastir(self):
        ok, reason = self._validate(
            "iyice ustalaştırmaya verdik",
            "bilime döktük",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_rejects_bilim_gibi_yaptik_from_ustalik(self):
        ok, reason = self._validate(
            "ustalık gerektiren bir iş",
            "bilim gibi yaptık",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_rejects_bilim_gibi_yapmaya_from_teknik(self):
        ok, reason = self._validate(
            "tekniğini oturttuk",
            "bilim gibi yapmaya verdik",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_original_guard_still_works(self):
        ok, reason = self._validate(
            "iyice ustalaştırmaya verdik",
            "bilim gibi yapmaya verdik",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_allows_bilime_doktuk_without_intro_hint(self):
        ok, _ = self._validate(
            "normal bir açıklama",
            "normal açıklama",
        )
        self.assertTrue(ok)

    def test_allows_unchanged_ustalastirma(self):
        ok, _ = self._validate(
            "iyice ustalaştırmaya verdik",
            "iyice ustalaştırmaya verdik",
        )
        self.assertTrue(ok)


# ── 8. Unnecessary "da" deletion ──────────────────────────────────────────

class UnnecessaryDaDeletionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_adi_da_to_adi(self):
        ok, reason = self._validate(
            "adı da Bob Marley",
            "adı Bob Marley",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "unnecessary_da_deletion")

    def test_allows_adi_da_unchanged(self):
        ok, _ = self._validate(
            "adı da Bob Marley",
            "adı da Bob Marley",
        )
        self.assertTrue(ok)

    def test_allows_adi_without_da_in_old(self):
        ok, _ = self._validate(
            "adı Bob Marley",
            "adı Bob Marley",
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
