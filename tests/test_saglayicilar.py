# -*- coding: utf-8 -*-
"""Hazır sağlayıcı ön ayarları.

Program her OpenAI uyumlu adrese bağlanabiliyordu; eksik olan kullanıcının
adresi ezbere bilmek zorunda olmasıydı. Bu testler ön ayarların programın
KENDİ doğrulamalarıyla çelişmediğini kilitler — yanlış bir ön ayar, kullanıcı
hiçbir şey yanlış yapmadan 401 almasına yol açar.

Adresler 2026-08-29'da anahtarsız `/models` isteğiyle ölçüldü; hepsi yetki
hatası döndü, yani uç noktalar var (ayrıntı `saglayicilar.py` başında).
"""
import os
import sys
import unittest
from urllib.parse import urlparse

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import saglayicilar
import subtitle_translator_gui as gui


class OnAyarTutarliligiTest(unittest.TestCase):
    def test_saglayici_turleri_gercek(self):
        """`tur` alanı programın tanıdığı türlerden biri olmalı."""
        for ad, sg in saglayicilar.SAGLAYICILAR.items():
            self.assertIn(sg.tur, gui.API_PROFILE_PROVIDERS, ad)

    def test_adres_ile_tur_celismiyor(self):
        """Programın kendi uyuşmazlık kontrolüne hiçbir ön ayar takılmamalı.

        Bu kontrol gerçek bir olaydan doğdu: yeni profil varsayılanı
        'Reseller' + api.openai.com idi ve kullanıcı her istekte 401
        alıyordu. Ön ayarların aynı tuzağı kurmadığını burada doğruluyoruz.
        """
        takilan = []
        for ad, sg in saglayicilar.SAGLAYICILAR.items():
            uyari = gui._api_profile_provider_url_mismatch(sg.tur, sg.base_url)
            if uyari:
                takilan.append("%s: %s" % (ad, uyari))
        self.assertEqual(takilan, [], "; ".join(takilan))

    def test_adresler_bicimsel_olarak_gecerli(self):
        for ad, sg in saglayicilar.SAGLAYICILAR.items():
            parca = urlparse(sg.base_url)
            self.assertIn(parca.scheme, ("http", "https"), ad)
            self.assertTrue(parca.hostname, ad)
            if not sg.yerel:
                self.assertEqual(parca.scheme, "https",
                                 "%s: uzak sağlayıcı https olmalı" % ad)

    def test_yerel_saglayici_localhost(self):
        for ad, sg in saglayicilar.SAGLAYICILAR.items():
            self.assertEqual(sg.yerel, saglayicilar.yerel_mi(sg.base_url), ad)

    def test_yerel_saglayici_anahtar_adresi_istemez(self):
        for ad, sg in saglayicilar.SAGLAYICILAR.items():
            if sg.yerel:
                self.assertEqual(sg.anahtar_adresi, "", ad)

    def test_url_ile_bulma(self):
        self.assertIsNotNone(
            saglayicilar.url_ile_bul("https://openrouter.ai/api/v1/"))
        self.assertEqual(
            saglayicilar.url_ile_bul("https://openrouter.ai/api/v1").etiket,
            "OpenRouter")
        self.assertIsNone(saglayicilar.url_ile_bul("https://ornek.gecersiz/v1"))
        self.assertIsNone(saglayicilar.url_ile_bul(""))

    def test_yerel_mi(self):
        for adres in ("http://localhost:11434/v1", "http://127.0.0.1:1234/v1"):
            self.assertTrue(saglayicilar.yerel_mi(adres), adres)
        for adres in ("https://api.openai.com/v1", "", "eksik"):
            self.assertFalse(saglayicilar.yerel_mi(adres), adres)

    def test_kullanicinin_istedikleri_var(self):
        """Gemini ve Gemma seçilebilir olmalı — bu turun asıl isteği."""
        etiketler = " ".join(saglayicilar.SAGLAYICILAR).casefold()
        self.assertIn("gemini", etiketler)
        self.assertIn("gemma", etiketler)
        google = saglayicilar.SAGLAYICILAR["Google AI Studio (Gemini · Gemma)"]
        self.assertIn("generativelanguage.googleapis.com", google.base_url)

    def test_ozel_secenek_saglayici_adi_degil(self):
        self.assertNotIn(saglayicilar.OZEL, saglayicilar.SAGLAYICILAR)


class YardimciKatalogTest(unittest.TestCase):
    def test_gemma_ve_yeni_gemini_secilebilir(self):
        import helper_models as hm
        for ad in ("Gemma 4 31B", "Gemma 3 27B", "Gemini 3.7 Flash"):
            self.assertIn(ad, hm.HELPER_MODEL_OPTIONS, ad)
            self.assertIn(ad, hm._CONFIGS, ad)

    def test_her_secenegin_yapilandirmasi_var(self):
        """Listede olup kataloğu olmayan seçenek sessizce yedeğe düşer."""
        import helper_models as hm
        eksik = [o for o in hm.HELPER_MODEL_OPTIONS
                 if o not in hm._CONFIGS and "Özel" not in o]
        self.assertEqual(eksik, [], "kataloğu olmayan seçenek: %s" % eksik)

    def test_google_modelleri_on_ek_almaz(self):
        """Google'ın kendi ucunda `google/` ön eki KULLANILMAZ.

        OpenRouter'da `google/gemma-4-31b-it`, Google AI Studio'da
        `gemma-4-31b-it`. Karıştırmak 404 verir.
        """
        import helper_models as hm
        for ad, cfg in hm._CONFIGS.items():
            if "generativelanguage.googleapis.com" in cfg.base_url:
                self.assertNotIn("/", cfg.model,
                                 "%s: Google ucunda ön ek olmamalı" % ad)

    def test_takma_adlar_cozuluyor(self):
        import helper_models as hm
        self.assertEqual(
            hm.resolve_helper_model("gemma").label, "Gemma 4 31B")
        self.assertEqual(
            hm.resolve_helper_model("gemini-3.7-flash").label,
            "Gemini 3.7 Flash")


if __name__ == "__main__":
    unittest.main()
