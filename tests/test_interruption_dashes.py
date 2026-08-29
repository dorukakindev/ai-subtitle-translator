# -*- coding: utf-8 -*-
"""İngilizce `--` kesinti gösterimi Türkçede `…` olmalı.

Ölçüm (86 filmlik "Tekrar Geçilecek" koleksiyonu, programın YEDEK çıktısı):
`--` içeren cue 135 / 10 dosya → 0.

Biçim dağılımı tek kuralın yetmediğini gösterdi:
  satır/cue sonunda 64 · sözcük arası 13 · `!--`/`?--` 3 · sözcük içi 2 ·
  `. --` 1.

SATIR GÜVENLİĞİ: denetimde aynı sınıf `--\\s+` ile düzeltilmiş ve `\\s`
satır sonunu da yediği için uygulandığı 43 cue'nun 4'ünde (%9) iki replikli
cue tek satıra düşmüştü. Buradaki testler satır sayısını ayrıca doğrular.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)
duzelt = g._normalize_delivery_interruption_dashes


class InterruptionDashTest(unittest.TestCase):
    def test_satir_sonunda_uc_nokta_olur(self):
        self.assertEqual(duzelt("Ha? Aa, evet--"), "Ha? Aa, evet...")

    def test_unlem_soru_isaretinden_sonra_UC_NOKTA_EKLENMEZ(self):
        """`!--` zaten kesintiyi gösterir; üstüne `…` koymak çift işaret."""
        self.assertEqual(duzelt("Sir Celine!--"), "Sir Celine!")
        self.assertEqual(duzelt("Ne dedin?--"), "Ne dedin?")

    def test_noktadan_sonra_tek_noktaya_iner(self):
        self.assertEqual(duzelt("Bitti. -- Sonra gitti."),
                         "Bitti. Sonra gitti.")

    def test_sozcuk_arasi_ve_ici(self):
        self.assertEqual(duzelt("çok-- çok sorun"), "çok... çok sorun")
        self.assertEqual(duzelt("değildim--daha çok"), "değildim...daha çok")

    def test_bastaki_tire_ciftinde(self):
        self.assertEqual(duzelt("--Melos dönmeyecek."), "...Melos dönmeyecek.")

    def test_SATIR_SAYISI_DEGISMEZ(self):
        """En önemli test: hiçbir desen satır sonu yemeyecek."""
        vakalar = [
            "- Bir dakika--" + NL + "- Dur bir saniye,",
            "Sonra halk--" + NL + "ordusu kurdu.",
            "üç--" + NL + "satır--" + NL + "hepsi--",
            "-- başta" + NL + "sonda --",
        ]
        for metin in vakalar:
            self.assertEqual(
                duzelt(metin).count(NL), metin.count(NL),
                "satır sayısı değişti: %r" % (metin,))

    def test_iki_replikli_cue_tek_satira_dusmez(self):
        metin = "- Şey, bir dakika--" + NL + "- Dur bir saniye,"
        sonuc = duzelt(metin)
        self.assertEqual(sonuc, "- Şey, bir dakika..." + NL + "- Dur bir saniye,")

    def test_dokunulmayan_metin_aynen_doner(self):
        for metin in ("normal metin", "tek - tire", "üç nokta... var", ""):
            self.assertEqual(duzelt(metin), metin)

    def test_uc_nokta_ustune_binmez(self):
        """ASCII bicim: koleksiyonda 7175 kez / 84 dosya."""
        self.assertEqual(duzelt("bekle...--"), "bekle...")
        self.assertEqual(duzelt("bekle--..."), "bekle...")

    def test_teslim_temizliginden_gecerken_uygulanir(self):
        bloklar = [
            ("1", "00:00:01,000 --> 00:00:03,000", "Ben de--"),
            ("2", "00:00:04,000 --> 00:00:06,000", "- Peki--" + NL + "- Tamam."),
        ]
        temiz = g._prepare_upload_ready_blocks(
            bloklar, target_language="Turkish")
        metinler = [str(t or "") for _i, _ts, t in temiz]
        self.assertFalse(any("--" in m for m in metinler), metinler)
        # satır yapısı korunur
        self.assertTrue(any(m.count(NL) == 1 for m in metinler), metinler)


if __name__ == "__main__":
    unittest.main()
