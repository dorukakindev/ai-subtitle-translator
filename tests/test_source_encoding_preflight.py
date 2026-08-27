# -*- coding: utf-8 -*-
"""Kaynak yanlış kod sayfasıyla okunmuşsa çeviriden ÖNCE uyar.

Gerçek olay: `Qu'est ce que l'acte de creation.srt` Rusça bir metin ama
yanlış kod sayfasıyla okunmuş; her satır `ЩРН АСДСР БНОПНЯШ` gibi.
Dosya bu hâliyle baştan sona çevrildi, API parası harcandı ve teslim
edildi; kusur ancak okunurken fark edildi.

Sinyal 'Latin dışı yazı' OLAMAZ — Yunanca/Arapça/Kiril kaynaklar meşru ve
onları engellemek zarar verir. Ölçüm (286 kaynak, 11 baskın Kiril dosyası)
iki sinyalde tam ayrım verdi:

           sesli harf     büyük harf
  mojibake     %28,7          %98,3
  gerçek   %41,9–42,8      %2,1–5,3

Tüm arşivde (289 kaynak) bu kural tam olarak 1 dosya işaretliyor.
"""
import unittest

import subtitle_translator_gui as g


def _cues(text, times=40):
    return [(str(i), "00:00:%02d,000 --> 00:00:%02d,500" % (i % 60, i % 60),
             text) for i in range(1, times + 1)]


class SourceEncodingScanTest(unittest.TestCase):
    MOJIBAKE = ("ЩРН АСДСР БНОПНЯШ РЮЙНЦН РХОЮ, "
                "ВРН МЮИРХ ХДЕЧ ЩРН ПЕДЙНЕ ЯНАШРХЕ")
    REAL_RUSSIAN = ("но время от времени некоторые из них "
                    "возвращались и рассказывали о том, что видели")
    REAL_GREEK = ("και τότε άρχισε να μιλάει για τα πράγματα "
                  "που είχε δει στο ταξίδι του")

    def test_mojibake_is_flagged(self):
        result = g.scan_source_encoding(_cues(self.MOJIBAKE))
        self.assertTrue(result["suspect"])
        self.assertEqual(result["script"], "Kiril")
        self.assertGreater(result["upper_ratio"], 0.9)
        self.assertLess(result["vowel_ratio"], 0.35)

    def test_real_cyrillic_is_not_flagged(self):
        result = g.scan_source_encoding(_cues(self.REAL_RUSSIAN))
        self.assertFalse(result["suspect"])
        self.assertGreater(result["vowel_ratio"], 0.35)

    def test_real_greek_is_not_flagged(self):
        result = g.scan_source_encoding(_cues(self.REAL_GREEK))
        self.assertFalse(result["suspect"])

    def test_all_caps_cyrillic_alone_is_not_enough(self):
        # Tamamı büyük harfle yazılmış MEŞRU bir Kiril kaynağı
        # engellenmemeli; sesli oranı doğal kaldığı için geçer.
        result = g.scan_source_encoding(_cues(self.REAL_RUSSIAN.upper()))
        self.assertFalse(result["suspect"])
        self.assertGreater(result["upper_ratio"], 0.9)

    def test_latin_source_is_ignored(self):
        result = g.scan_source_encoding(
            _cues("This is an ordinary English subtitle line."))
        self.assertFalse(result["suspect"])

    def test_short_sample_is_ignored(self):
        # Birkaç Kiril harfi geçen Latin dosyayı yargılamaz.
        result = g.scan_source_encoding([("1", "x", "ЩРН")])
        self.assertFalse(result["suspect"])

    def test_empty_input_is_safe(self):
        self.assertFalse(g.scan_source_encoding([])["suspect"])
        self.assertFalse(g.scan_source_encoding(None)["suspect"])


if __name__ == "__main__":
    unittest.main()
