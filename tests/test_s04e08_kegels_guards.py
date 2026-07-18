"""S04E08 (Heads, Kegels, Knees and Toes) gerçek çıktısında görülen kalıntılar:
- Türkmence 'dyz' (=diz) ve 'ulus haryt bazarynda' (=bit pazarında) sızıntısı
- İngilizce kalmış 'MOTORCYCLE ACCIDENT'
- İntro varyantı 'TUHAFLIK DÜNYASINA HOŞ GELDİNİZ, "Oddities."'
- 'Tabii büyükanneniz biraz çatlak değilse' (virgülsüz) olumsuzluk tersinmesi
"""
import unittest

import hybrid_translate as ht


class KegelsTurkicResidueFixTest(unittest.TestCase):
    def test_dyz_suffixed_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("sağ dyzunu ve ayağını fena mahvetmişti.")[0],
            "sağ dizini ve ayağını fena mahvetmişti.",
        )

    def test_dyz_bare_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("paramparça bir dyz bulduk,")[0],
            "paramparça bir diz bulduk,",
        )

    def test_dyz_all_caps_cleanup(self):
        self.assertEqual(ht._apply_local_fixes("SAĞ DYZUNU KIRDI")[0], "SAĞ DİZİNİ KIRDI")
        self.assertEqual(ht._apply_local_fixes("DYZ")[0], "DİZ")

    def test_haryt_bazar_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Brimfield ulus haryt bazarynda paramparça bir dyz bulduk,")[0],
            "Brimfield bit pazarında paramparça bir diz bulduk,",
        )

    def test_bazarynda_standalone_cleanup(self):
        self.assertEqual(ht._apply_local_fixes("köy bazarynda")[0], "köy pazarında")

    def test_dyz_extra_suffix_forms(self):
        self.assertEqual(ht._apply_local_fixes("dyzümle oynama")[0], "dizimle oynama")
        self.assertEqual(ht._apply_local_fixes("sol dyzü ağrıyor")[0], "sol dizi ağrıyor")
        self.assertEqual(ht._apply_local_fixes("dyzunun bağları")[0], "dizinin bağları")
        self.assertEqual(ht._apply_local_fixes("dyzle vurdu")[0], "dizle vurdu")

    def test_haryt_bazar_dative_ablative(self):
        self.assertEqual(
            ht._apply_local_fixes("haryt bazaryna gittik")[0], "bit pazarına gittik")
        self.assertEqual(
            ht._apply_local_fixes("ulus haryt bazaryndan aldım")[0], "bit pazarından aldım")


class KegelsEnglishLeftoverFixTest(unittest.TestCase):
    def test_motorcycle_accident_all_caps(self):
        self.assertEqual(
            ht._apply_local_fixes("30 YIL ÖNCE BİR MOTORCYCLE ACCIDENT GEÇİRDİM.")[0],
            "30 YIL ÖNCE BİR MOTOSİKLET KAZASI GEÇİRDİM.",
        )

    def test_motorcycle_accident_lowercase(self):
        self.assertEqual(
            ht._apply_local_fixes("bir motorcycle accident geçirdim")[0],
            "bir motosiklet kazası geçirdim",
        )

    def test_motorcycle_accident_with_turkish_suffix(self):
        self.assertEqual(
            ht._apply_local_fixes("bir motorcycle accident'ta kaybettim")[0],
            "bir motosiklet kazasında kaybettim",
        )
        self.assertEqual(
            ht._apply_local_fixes("Eski bir motorcycle accident'ı anımsatıyor.")[0],
            "Eski bir motosiklet kazasını anımsatıyor.",
        )
        self.assertEqual(
            ht._apply_local_fixes("motorcycle accident'ının otuzuncu yılı")[0],
            "motosiklet kazasının otuzuncu yılı",
        )


class KegelsDetectionTest(unittest.TestCase):
    def test_source_lang_leftover_matches(self):
        for word in ("dyz", "dyzunu", "haryt", "bazarynda", "motorcycle", "accident"):
            self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search(word), word)

    def test_turkic_drift_matches(self):
        for word in ("dyz", "dyzunu", "dyzü", "dyzümle", "dyzle", "haryt",
                     "bazarynda", "bazaryna", "bazaryndan"):
            self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search(word), word)

    def test_leak_detector_fires_for_real_lines(self):
        self.assertTrue(ht.has_non_turkish_target_leak("sağ dyzunu ve ayağını fena mahvetmişti."))
        self.assertTrue(ht.has_non_turkish_target_leak("Brimfield ulus haryt bazarynda bir şey bulduk."))

    def test_no_false_positive_on_clean_turkish(self):
        self.assertFalse(ht.has_non_turkish_target_leak("Dizini incitti, pazarında yürüyordu."))
        self.assertFalse(ht.has_non_turkish_target_leak("Bu dizi çok güzel, pazar günü izledik."))
        self.assertEqual(
            ht._apply_local_fixes("Dizini incitti, pazar günü dinlendi.")[0],
            "Dizini incitti, pazar günü dinlendi.",
        )


class KegelsIntroAndNegationFixTest(unittest.TestCase):
    def test_intro_tuhaflik_variant(self):
        self.assertEqual(
            ht._apply_local_fixes('TUHAFLIK DÜNYASINA HOŞ GELDİNİZ, "Oddities."')[0],
            '"ODDITIES"in tuhaf dünyasına\nhoş geldiniz.',
        )

    def test_grandma_negation_without_comma(self):
        self.assertEqual(
            ht._apply_local_fixes("Tabii büyükanneniz biraz çatlak değilse.")[0],
            "Tabii anneanneniz biraz çatlaksa o ayrı.",
        )

    def test_grandma_negation_with_comma_still_works(self):
        self.assertEqual(
            ht._apply_local_fixes("Tabii, büyükanneniz biraz çatlak değilse.")[0],
            "Tabii anneanneniz biraz çatlaksa o ayrı.",
        )


if __name__ == "__main__":
    unittest.main()
