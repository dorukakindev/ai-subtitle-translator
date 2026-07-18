"""
Oddities S05E15 "Instant Chimera" verified residue fixes:

1. Turkic residue: vaxt/vaqt mashinasi → zaman makinesi; portlatgich qurilma → patlatma düzeneği
2. Detonator/detonatör → patlatıcı
3. Polish semantic regression: araştırıp→avlanıp seçerek reject
4. Polish intro regression: ustalaştır→bilim gibi yapmaya reject
5. Ear protection: kulak kapaklarımı → kulaklıklarımı
"""

import unittest

_APPLY = lambda t: __import__("hybrid_translate")._apply_local_fixes(t)[0]


class TurkicResidueTest(unittest.TestCase):
    def test_vaxt_mashinasi_fixed(self):
        self.assertEqual(_APPLY("Bu bir vaxt mashinasi."), "Bu bir zaman makinesi.")

    def test_vaqt_mashinasi_fixed(self):
        self.assertEqual(_APPLY("Bu bir vaqt mashinasi."), "Bu bir zaman makinesi.")

    def test_mashinasi_standalone_fixed(self):
        self.assertEqual(_APPLY("mashinasi"), "makinesi")

    def test_portlatgich_qurilma_fixed(self):
        result = _APPLY("iki numaralı portlatgich qurilma")
        self.assertIn("patlatma düzeneği", result)

    def test_portlatgich_standalone_fixed(self):
        self.assertEqual(_APPLY("portlatgich"), "patlatıcı")

    def test_qurilma_standalone_fixed(self):
        self.assertEqual(_APPLY("qurilma"), "düzenek")

    def test_turkic_drift_re_matches_vaxt(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("vaxt"))

    def test_turkic_drift_re_matches_vaqt(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("vaqt"))

    def test_turkic_drift_re_matches_mashinasi(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("mashinasi"))

    def test_turkic_drift_re_matches_portlatgich(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("portlatgich"))

    def test_turkic_drift_re_matches_qurilma(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("qurilma"))

    def test_source_lang_leftover_matches_vaxt(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("vaxt"))

    def test_source_lang_leftover_matches_portlatgich(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("portlatgich"))


class DetonatorResidueTest(unittest.TestCase):
    def test_detonator_fixed(self):
        self.assertEqual(_APPLY("Bu bir detonator."), "Bu bir patlatıcı.")

    def test_detonator_sentence_fixed(self):
        self.assertEqual(_APPLY("Bir detonator."), "Bir patlatıcı.")

    def test_detonatoer_fixed(self):
        self.assertEqual(_APPLY("Bu bir detonatör."), "Bu bir patlatıcı.")

    def test_en_leftover_matches_detonator(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._EN_LEFTOVER.search("detonator"))

    def test_source_lang_leftover_matches_detonator(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("detonator"))

    def test_source_lang_leftover_matches_detonatoer(self):
        import hybrid_translate as ht
        self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search("detonatör"))


class ResearchToHuntingRegressionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_avlanip_secerek(self):
        ok, reason = self._validate("araştırıp seçerek...", "avlanıp seçerek...")
        self.assertFalse(ok)
        self.assertEqual(reason, "research_to_hunting_regression")

    def test_allows_unchanged(self):
        ok, _ = self._validate("araştırıp seçerek...", "araştırıp seçerek...")
        self.assertTrue(ok)

    def test_allows_unrelated_change(self):
        ok, _ = self._validate("bir şey araştırıyor", "bir şey arıyor")
        self.assertTrue(ok)

    def test_allows_avlanmak_in_other_context(self):
        ok, _ = self._validate("balık tutuyor", "avlanıyor")
        self.assertTrue(ok)


class OdditiesIntroRegressionTest(unittest.TestCase):
    def _validate(self, old, new):
        return __import__("hybrid_translate").validate_polish_candidate(old, new)

    def test_rejects_bilim_gibi_yapmaya(self):
        ok, reason = self._validate(
            "bu işi iyice ustalaştırmaya verdik",
            "bu işi bilim gibi yapmaya verdik",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "oddities_intro_regression")

    def test_allows_unchanged(self):
        ok, _ = self._validate(
            "bu işi iyice ustalaştırmaya verdik",
            "bu işi iyice ustalaştırmaya verdik",
        )
        self.assertTrue(ok)

    def test_allows_unrelated_change(self):
        ok, _ = self._validate("ustalaşmak zaman alır", "ustalaşmak zaman alır")
        self.assertTrue(ok)

    def test_local_fix_cleans_bilim_gibi(self):
        self.assertEqual(
            _APPLY("bilim gibi yapmaya verdik"),
            "iyice ustalaştırdık",
        )


class EarProtectionTest(unittest.TestCase):
    def test_kulak_kapaklarimi_fixed(self):
        self.assertEqual(
            _APPLY("Kulak kapaklarımı indireyim."),
            "Kulaklıklarımı indireyim.",
        )

    def test_kulak_kapaklarimi_lowercase_fixed(self):
        self.assertEqual(
            _APPLY("kulak kapaklarımı taktım"),
            "kulaklıklarımı taktım",
        )

    def test_kulak_kapaklarini_fixed(self):
        self.assertEqual(
            _APPLY("kulak kapaklarını indir"),
            "kulaklıklarını indir",
        )

    def test_ordinary_kapak_not_touched(self):
        self.assertEqual(_APPLY("kapağı aç"), "kapağı aç")
        self.assertEqual(_APPLY("kapak"), "kapak")
        self.assertEqual(_APPLY("kulaklık"), "kulaklık")


if __name__ == "__main__":
    unittest.main()
