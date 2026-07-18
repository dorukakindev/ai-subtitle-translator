"""S04E03 (Return to Holly-Odd) gerçek çıktısında görülen kalıntılar:
- Türkmence 'guş' (=kuş) sızıntısı — bölüm kuş taksidermisi hakkında, 14 cue'da sızdı
- '_TURKIC_DRIFT_RE' içindeki eski 'başy\\w*' deseninin yanlış alarmı: meşru Türkçe
  "başyapıt"/"başyazı" kelimelerini sızıntı sanıyordu — Türkmen 'başy(n)' formları
  yakalanmaya devam ederken bu daraltıldı.
- 'non_turkish_leak_token' — retry/log mesajlarına tetikleyen token'ı basan yeni
  teşhis yardımcı fonksiyonu (has_non_turkish_target_leak artık bunun üzerine kurulu).
"""
import unittest

import hybrid_translate as ht


class GusLocalFixTest(unittest.TestCase):
    def test_gus_plural_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Egzotik guşlar arayan bir müşterim var.")[0],
            "Egzotik kuşlar arayan bir müşterim var.",
        )

    def test_gus_possessive_suffix_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("guşlarının çoğundan biraz daha koyu ama,")[0],
            "kuşlarının çoğundan biraz daha koyu ama,",
        )

    def test_gus_bare_cleanup(self):
        self.assertEqual(
            ht._apply_local_fixes("Dünyadaki en büyük guş bunlar.")[0],
            "Dünyadaki en büyük kuş bunlar.",
        )

    def test_gus_all_caps_cleanup(self):
        self.assertEqual(ht._apply_local_fixes("GUŞLAR çok güzel")[0], "KUŞLAR çok güzel")

    def test_gus_title_case_cleanup(self):
        self.assertEqual(ht._apply_local_fixes("Guşları seviyorum.")[0], "Kuşları seviyorum.")


class GusDetectionTest(unittest.TestCase):
    def test_source_lang_leftover_matches(self):
        for word in ("guş", "guşlar", "guşları", "guşların"):
            self.assertIsNotNone(ht._SOURCE_LANG_LEFTOVER.search(word), word)

    def test_turkic_drift_matches(self):
        for word in ("guş", "guşlar", "guşları"):
            self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search(word), word)

    def test_leak_detector_fires_for_real_line(self):
        self.assertTrue(ht.has_non_turkish_target_leak("Ben guşları seviyorum."))


class BasyFalsePositiveRegressionTest(unittest.TestCase):
    """başy\\w* -> başyn\\w*|başy\\b daraltması: Türkçe bileşikler artık temiz."""

    def test_basyapit_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("Bu bir başyapıt."))

    def test_basyazi_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("başyazı yazdı"))

    def test_basyardimci_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("başyardımcı oldu"))

    def test_kusak_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("kuşak farkı"))
        self.assertEqual(ht._apply_local_fixes("kuşku duydum.")[0], "kuşku duydum.")

    def test_gundogusu_not_flagged(self):
        self.assertFalse(ht.has_non_turkish_target_leak("gündoğuşu"))

    def test_turkmen_basy_still_caught(self):
        # Bu daraltma Türkmen biçimlerini kaçırmamalı.
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("başy"))
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("başyna"))
        self.assertIsNotNone(ht._TURKIC_DRIFT_RE.search("başynda"))
        self.assertTrue(ht.has_non_turkish_target_leak("Bu başy çok önemli."))


class NonTurkishLeakTokenTest(unittest.TestCase):
    def test_returns_offending_token(self):
        self.assertEqual(ht.non_turkish_leak_token("Ben guşları seviyorum."), "guşları")

    def test_returns_none_for_clean_text(self):
        self.assertIsNone(ht.non_turkish_leak_token("Temiz bir cümle."))

    def test_returns_none_for_basyapit(self):
        self.assertIsNone(ht.non_turkish_leak_token("Bu bir başyapıt."))

    def test_has_leak_matches_token_presence(self):
        for text in ("Ben guşları seviyorum.", "Temiz bir cümle.", "Bu bir başyapıt.",
                     "başynda büyük bir tören vardı."):
            self.assertEqual(
                ht.has_non_turkish_target_leak(text),
                ht.non_turkish_leak_token(text) is not None,
            )


if __name__ == "__main__":
    unittest.main()
