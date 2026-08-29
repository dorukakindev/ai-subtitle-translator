# -*- coding: utf-8 -*-
"""`Downloaded From <site>` tek satırda da reklam sayılmalı.

Desen iki satırlık biçimi (`downloaded from` + `YTS.MX`) ve tek başına
duran url'yi tanıyordu; etiketi ve siteyi AYNI satırda taşıyan biçim
kaçıyordu. Sonuç: model onu normal replik sanıp çeviriyordu —
`Downloaded From www.AllSubs.org` → `www.AllSubs.org'dan indirildi`
(st.michael.had.a.rooster, #0 ve #699; teslimin ilk ve son cue'suydu).

Ölçüm: 78.195 kaynak cue'da reklam/künye satırı 10 tane (%0,013), yani
brief'in "para yakıyor" gerekçesi ölçekte doğru DEĞİL — sorun maliyet
değil, yabancı reklamın teslime sızması. Tanınan oran 2/5 → 8/10.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)


class ReleaseAdSingleLineTest(unittest.TestCase):
    def _reklam(self, metin):
        return bool(g._DELIVERY_RELEASE_AD_RE.match(metin))

    def test_tek_satirda_etiket_ve_site(self):
        self.assertTrue(self._reklam("Downloaded From www.AllSubs.org"))
        self.assertTrue(self._reklam("downloaded from https://opensubs.org"))
        self.assertTrue(self._reklam("Downloaded From AllSubs.org"))

    def test_eski_biciler_hala_taniniyor(self):
        self.assertTrue(self._reklam("Downloaded From" + NL + "YTS.MX"))
        self.assertTrue(self._reklam("www.AllSubs.org"))
        self.assertTrue(self._reklam("https://yts.mx"))

    def test_normal_replik_reklam_sayilmaz(self):
        """`downloaded from` geçen GERÇEK cümle işaretlenmemeli."""
        for metin in ("Downloaded from the shelf carefully",
                      "Bugün eve indirildi.",
                      "Dosyayı indirdim ve izledim.",
                      "Normal replik."):
            self.assertFalse(self._reklam(metin), metin)

    def test_kaynak_cue_atilabilir_sayilir(self):
        """Uçtan uca: reklam cue'su çeviriye girmeden düşer."""
        kaynak = [
            ("0", "00:00:00,000 --> 00:00:02,000",
             "Downloaded From www.AllSubs.org"),
            ("1", "00:00:03,000 --> 00:00:05,000", "Gerçek replik."),
        ]
        atilabilir = {str(v)
                      for v in g._delivery_removable_source_ids(kaynak)}
        self.assertIn("0", atilabilir)
        self.assertNotIn("1", atilabilir)


if __name__ == "__main__":
    unittest.main()
