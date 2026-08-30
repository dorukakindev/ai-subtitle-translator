# -*- coding: utf-8 -*-
"""Çeviriden ÖNCE kaynağı ölçen iki kontrol.

İkisi de dosya çapında felaketi önler ve ikisi de 386 gerçek kaynak
dosyasına karşı ölçülerek eklendi.

NOKTALAMA — ölçülen dağılım, ortanca %70,4:
    %20 altı  38 dosya (%9,8) · %30 altı 47 (%12,2) · %40 altı 68 (%17,6)
Eşik %30: uyarı oranı %12'de kalıyor, uçlar tartışmasız (on iki dosya TAM
%0,0 — kayan altyazılı belgeseller). Noktalamasız kaynakta model satır
satır çevirir ve çıktının yarısı İngilizce söz diziminde kalır; bu kusur
yamayla değil yeniden çeviriyle düzelir.

KODLAMA — 386 dosyada 1 vaka (69 imza). Nadir ama olduğunda dosyanın
tamamı yanlış çevrilir ve harcanan para geri gelmez.
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import kaynak_on_kontrol as kok


class NoktalamaTest(unittest.TestCase):
    def test_noktalamali_kaynak_uyarmaz(self):
        cues = ["Bir cümle.", "İkinci!", "Üçüncü?"] * 20
        self.assertEqual(kok.on_kontrol(cues, ""), [])

    def test_noktalamasiz_kaynak_uyarir(self):
        cues = ["noktalamasiz satir %d" % i for i in range(60)]
        uyarilar = kok.on_kontrol(cues, "")
        self.assertEqual(len(uyarilar), 1)
        self.assertEqual(uyarilar[0]["tur"], "noktalama")
        self.assertEqual(uyarilar[0]["seviye"], "uyari")

    def test_kisa_dosya_olculmez(self):
        """40 cue altında oran gürültülüdür; ölçüm yapılmaz."""
        self.assertEqual(kok.on_kontrol(["a", "b", "c"], ""), [])

    def test_kapanis_tirnagi_cumle_sonu_sayilir(self):
        cues = ['"Bekle."', "(gülüyor)", "Bitti…"] * 20
        self.assertEqual(kok.sentence_end_ratio(cues), 1.0)

    def test_esik_civari(self):
        biten = ["Bitti." for _ in range(29)]
        bitmeyen = ["bitmedi" for _ in range(71)]
        self.assertTrue(kok.on_kontrol(biten + bitmeyen, ""))
        biten = ["Bitti." for _ in range(31)]
        bitmeyen = ["bitmedi" for _ in range(69)]
        self.assertFalse(
            [u for u in kok.on_kontrol(biten + bitmeyen, "")
             if u["tur"] == "noktalama"])

    def test_bos_girdi_patlamaz(self):
        self.assertEqual(kok.on_kontrol([], ""), [])
        self.assertEqual(kok.on_kontrol(None, None), [])


class KodlamaTest(unittest.TestCase):
    def test_mojibake_yakalanir(self):
        bozuk = "KÃ¶szÃ¶nÃ¶m Ã¡Ã³Ã© " * 5
        uyarilar = kok.on_kontrol([], bozuk)
        self.assertEqual(len(uyarilar), 1)
        self.assertEqual(uyarilar[0]["tur"], "kodlama")
        self.assertEqual(uyarilar[0]["seviye"], "kritik")

    def test_MESRU_iskandinav_harfi_yanlis_alarm_vermez(self):
        """Çıplak `Å` İsveççede meşru bir harftir (`Åke`).

        İmza HER ZAMAN iki karakterliktir; tek harfe bakan bir kural
        İskandinav kaynağının tamamını yanlış işaretlerdi.
        """
        isvecce = "Åke bor i Åmål och äter kött på Öland. " * 10
        self.assertEqual(kok.mojibake_hits(isvecce), 0)
        self.assertEqual(kok.on_kontrol([], isvecce), [])

    def test_MESRU_diger_diller_temiz(self):
        for metin in ("Käse und Grüße für Ärzte. " * 10,
                      "À côté de ça, très bien. " * 10,
                      "Merhaba dünya, güzel şey. " * 10,
                      "Köszönöm szépen, jó napot. " * 10):
            self.assertEqual(kok.mojibake_hits(metin), 0, metin[:24])

    def test_esigin_altindaki_iz_uyarmaz(self):
        """Tek tük iz gürültüdür; eşik 10."""
        self.assertEqual(kok.on_kontrol([], "KÃ¶y"), [])

    def test_iki_uyari_birlikte_cikabilir(self):
        cues = ["noktalamasiz %d" % i for i in range(60)]
        uyarilar = kok.on_kontrol(cues, "KÃ¶szÃ¶nÃ¶m Ã¡Ã³Ã© " * 5)
        self.assertEqual({u["tur"] for u in uyarilar},
                         {"noktalama", "kodlama"})


class ArayuzeBagliTest(unittest.TestCase):
    def test_app_metodu_var_ve_uyari_dondurur(self):
        import subtitle_translator_gui as gui
        self.assertTrue(hasattr(gui.App, "_kaynak_on_kontrol_uyar"))

    def test_kaynak_yuklemesine_bagli(self):
        """Her iki kaynak-yükleme noktasından da çağrılmalı."""
        import io as _io
        with _io.open(os.path.join(KOK, "subtitle_translator_gui.py"),
                      encoding="utf-8") as fh:
            kaynak = fh.read()
        self.assertEqual(
            kaynak.count("self._kaynak_on_kontrol_uyar(fp, blocks)"), 2)


if __name__ == "__main__":
    unittest.main()
