# -*- coding: utf-8 -*-
"""`plans/canli-kosu-bug-avi-20260829.md` bulgularının düzeltmeleri.

Bu bulgular canlı bir çeviri koşusu sürerken salt-okunur olarak bulunmuş,
koda o sırada dokunulamamıştı.
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import hybrid_translate as ht
import subtitle_translator_gui as gui


class TurkceBuyukITest(unittest.TestCase):
    """Sözlük aksan onarımı `Isci`'yi `Işçi` yapıyordu; doğrusu `İşçi`.

    `"işçi"[:1].upper()` ASCII `I` verir. Hata sözlükten teslime geçer ve
    terim normalizasyonu yanlış biçimi "doğru" sayar. Arşivde hiç
    ateşlenmemişti (0 vaka), yani latent.
    """

    def _duzelt(self, terim):
        return ht.sanitize_glossary_for_turkish(
            {"w": terim}, target_language="Turkish").get("w")

    def test_bas_harf_turkce_I_olur(self):
        self.assertEqual(self._duzelt("Isci"), "İşçi")
        self.assertEqual(self._duzelt("Isciler"), "İşçiler")
        self.assertEqual(self._duzelt("Icin"), "İçin")

    def test_kucuk_harf_bozulmaz(self):
        self.assertEqual(self._duzelt("isci"), "işçi")

    def test_i_ile_baslamayanlar_etkilenmez(self):
        self.assertEqual(self._duzelt("Buyuk"), "Büyük")
        self.assertEqual(self._duzelt("Ozel"), "Özel")
        self.assertEqual(self._duzelt("Ates"), "Ateş")

    def test_yardimci_dogrudan(self):
        self.assertEqual(ht._tr_bas_harf_buyut("işçi"), "İşçi")
        self.assertEqual(ht._tr_bas_harf_buyut("özel"), "Özel")
        self.assertEqual(ht._tr_bas_harf_buyut(""), "")
        self.assertEqual(ht._tr_bas_harf_buyut("Abc"), "Abc")


class ParalelIsciOzetiTest(unittest.TestCase):
    """Zincirleme bağlam açıkken chunk'lar SIRALI işlenir.

    Paralel dal yalnız zincir kapalıyken çalışır, ama panel koşulsuz
    "4 paralel işçi" diyordu; kullanıcı `max_workers`ı büyütüp hiçbir şey
    değişmediğini görüyordu.
    """

    DEGERLER = {
        "_chunk_size": 25, "_context_lines": 25, "_lookahead_lines": 10,
        "_max_workers": 4, "_max_retry": 2, "_scene_gap_seconds": 2.0,
    }

    def test_zincir_acikken_paralel_demez(self):
        baslik, _ = gui._advanced_settings_summary(
            self.DEGERLER, chain_ctx=True)
        self.assertNotIn("paralel işçi", baslik)
        self.assertIn("sıralı", baslik)

    def test_zincir_kapaliyken_isci_sayisi_yazar(self):
        baslik, _ = gui._advanced_settings_summary(
            self.DEGERLER, chain_ctx=False)
        self.assertIn("4 paralel işçi", baslik)

    def test_belirtilmezse_eski_davranis(self):
        baslik, _ = gui._advanced_settings_summary(self.DEGERLER)
        self.assertIn("4 paralel işçi", baslik)

    def test_diger_alanlar_degismez(self):
        for zincir in (True, False):
            baslik, ayrinti = gui._advanced_settings_summary(
                self.DEGERLER, chain_ctx=zincir)
            self.assertIn("25 cue / istek", baslik)
            self.assertIn("25 önceki + 10 sonraki", baslik)
            self.assertIn("hedefli yanıt denemesi", ayrinti)


class DilGeriDususuTest(unittest.TestCase):
    """Tespit çökünce dosya adı etiketine düşülüyordu — sessizce.

    Ölçüldü (108 dosya): etiket %78 hiç yok, bulunduğunda 8'de 1'i AI ile
    çelişiyor. Sürüm adındaki `FRENCH` altyazının değil sesin dili.
    """

    def _kayit(self):
        satirlar = []
        return satirlar, lambda mesaj, tur="info": satirlar.append(mesaj)

    def test_etiket_varsa_tahmin_oldugu_soylenir(self):
        satirlar, log = self._kayit()
        sonuc = gui._dil_ad_etiketine_dus(
            "Le.Dossier.51.FRENCH.srt", log, "401")
        self.assertEqual(sonuc, "French")
        self.assertEqual(len(satirlar), 1)
        self.assertIn("TAHMİN", satirlar[0])
        self.assertIn("French", satirlar[0])

    def test_etiket_yoksa_otomatik_tahmin_diye_sunulmaz(self):
        """İpucu yokken fonksiyon 'Otomatik' döner; bu bir tahmin değildir."""
        satirlar, log = self._kayit()
        gui._dil_ad_etiketine_dus("film.srt", log, "timeout")
        self.assertEqual(len(satirlar), 1)
        self.assertIn("ipucu vermiyor", satirlar[0])
        self.assertNotIn("TAHMİN edildi", satirlar[0])

    def test_sebep_mesaja_giriyor(self):
        satirlar, log = self._kayit()
        gui._dil_ad_etiketine_dus("x.srt", log, "baglanti koptu")
        self.assertIn("baglanti koptu", satirlar[0])

    def test_log_yoksa_patlamaz(self):
        self.assertEqual(
            gui._dil_ad_etiketine_dus("Le.Dossier.51.FRENCH.srt"), "French")


if __name__ == "__main__":
    unittest.main()
