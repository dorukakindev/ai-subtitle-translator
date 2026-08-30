# -*- coding: utf-8 -*-
"""Chunk adli günlüğü — bir kusur hangi isteğe aitti.

Teslimde bozuk bir cue bulunduğunda cevaplanamayan soru şuydu: bu cue
hangi chunk'ta gitti, o istekte hangi bağlam vardı, model ne döndü.
Rapor cue'yu gösteriyordu, isteği göstermiyordu.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import chunk_gunlugu as cg

NL = chr(10)

GOVDE = {
    "model": "gpt-5.4-mini",
    "max_completion_tokens": 4000,
    "messages": [
        {"role": "system", "content": "Sen bir altyazı çevirmenisin."},
        {"role": "user", "content": json.dumps(
            {"items": [{"i": 12, "t": "Hello."}],
             "ctx": [{"i": 11, "t": "Wait."}],
             "prev_tr": [], "glossary": {"Troy": "Truva"}},
            ensure_ascii=False)},
    ],
}

SENKRON_INFO = [(12, "00:01:00,000 --> 00:01:02,000", "C:/x/ornek.srt"),
                (13, "00:01:02,000 --> 00:01:04,000", "C:/x/ornek.srt")]
HIBRIT_INFO = [(12, "00:01:00,000", "00:01:02,000"),
               (13, "00:01:02,000", "00:01:04,000")]


class KayitTest(unittest.TestCase):
    def _kayit(self, info=None):
        return cg.kayit_olustur("ornek.srt__3", info or SENKRON_INFO, GOVDE,
                                akis="sync", dosya="C:/x/ornek.srt",
                                ham_yanit='[{"i":12,"t":"Merhaba."}]',
                                zaman=1.0)

    def test_cue_kimlikleri_ve_zamanlari_kayitli(self):
        k = self._kayit()
        self.assertEqual(k["cue_sayisi"], 2)
        self.assertEqual(k["cue_zamanlari"][0],
                         ["12", "00:01:00,000 --> 00:01:02,000"])

    def test_HIBRIT_file_map_SEKLI_de_dogru_okunur(self):
        """İki akış iki ayrı üçlü şekli yazıyor.

        Senkron `(id, "a --> b", yol)`, hibrit `(id, baslangic, bitis)`.
        Yalnız birini varsaymak, ikinci akışta zaman damgası yerine yarım
        bir değer kaydeder — ve günlüğün tek güvenilir anahtarı zaman
        damgasıdır.
        """
        k = self._kayit(HIBRIT_INFO)
        self.assertEqual(k["cue_zamanlari"][0],
                         ["12", "00:01:00,000 --> 00:01:02,000"])

    def test_yuk_anahtarlari_AYARDAN_degil_govdeden_okunur(self):
        """"Zincirleme bağlam açıktı" ile "bu isteğe prev_tr kondu" ayrı
        şeylerdir; boş prev_tr listelenmemeli."""
        k = self._kayit()
        self.assertIn("ctx", k["yuk_anahtarlari"])
        self.assertIn("glossary", k["yuk_anahtarlari"])
        self.assertNotIn("prev_tr", k["yuk_anahtarlari"])

    def test_MALIYET_ALANI_YOK(self):
        """Ana rota dinamik faturalı; yerelde hesaplanan kuruş rakamı
        yanlış olur ve doğru sanılır. Token ölçülür, para ölçülmez."""
        k = self._kayit()
        for yasak in ("maliyet", "ucret", "usd", "dolar", "fiyat", "cost"):
            self.assertFalse([a for a in k if yasak in a.lower()], yasak)
        self.assertIn("giris_token", k)

    def test_model_govdeden_gelir(self):
        k = self._kayit()
        self.assertEqual(k["model"], "gpt-5.4-mini")

    def test_sistem_istemi_chunk_satirinda_TEKRARLANMAZ(self):
        k = self._kayit()
        self.assertNotIn("Sen bir altyazı çevirmenisin", json.dumps(k))
        self.assertTrue(k["istem_sha"])


class YazOkuTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()
        self.yol = os.path.join(self.dizin, "kosu.jsonl")

    def tearDown(self):
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _doldur(self):
        cg.yaz(self.yol, [
            cg.istem_basligi("Sen bir altyazı çevirmenisin."),
            cg.kayit_olustur("a__1", SENKRON_INFO, GOVDE, zaman=1.0,
                             ham_yanit='[{"i":12,"t":"Merhaba."}]'),
        ])

    def test_yaz_oku_gidis_donus(self):
        self._doldur()
        kayitlar = cg.oku(self.yol)
        self.assertEqual(len(cg.chunklar(kayitlar)), 1)
        istemler = cg.istemleri_topla(kayitlar)
        self.assertEqual(list(istemler.values())[0],
                         "Sen bir altyazı çevirmenisin.")

    def test_YARIM_SATIR_butun_gunlugu_kaybettirmez(self):
        """Koşu ortasında çöken bir yazımın yarım bıraktığı son satır
        yüzünden bütün günlük okunamaz olursa günlük işe yaramaz."""
        self._doldur()
        with io.open(self.yol, "a", encoding="utf-8") as fh:
            fh.write('{"tip": "chunk", "yarim')
        self.assertEqual(len(cg.chunklar(cg.oku(self.yol))), 1)

    def test_olmayan_dosya_patlamaz(self):
        self.assertEqual(cg.oku(os.path.join(self.dizin, "yok.jsonl")), [])

    def test_bos_liste_dosya_acmaz(self):
        cg.yaz(self.yol, [])
        self.assertFalse(os.path.exists(self.yol))


class AramaTest(unittest.TestCase):
    def setUp(self):
        self.kayitlar = [
            cg.kayit_olustur("a__1", SENKRON_INFO, GOVDE, zaman=1.0),
            cg.kayit_olustur(
                "a__2",
                [(20, "00:02:00,000 --> 00:02:02,000", "C:/x/ornek.srt")],
                GOVDE, zaman=2.0),
        ]

    def test_cue_numarasiyla_bulunur(self):
        bulunan = cg.cue_ara(self.kayitlar, cue_id=13)
        self.assertEqual([k["custom_id"] for k in bulunan], ["a__1"])

    def test_zaman_damgasiyla_bulunur(self):
        bulunan = cg.cue_ara(
            self.kayitlar, zaman_damgasi="00:02:00,000 --> 00:02:02,000")
        self.assertEqual([k["custom_id"] for k in bulunan], ["a__2"])

    def test_zaman_verilince_numara_YANILTMAZ(self):
        """Teslim yeniden numaralanmışsa numara yanlış chunk'a götürür;
        zaman damgası verildiğinde numara hiç dikkate alınmamalı."""
        bulunan = cg.cue_ara(self.kayitlar, cue_id=13,
                             zaman_damgasi="00:02:00,000 --> 00:02:02,000")
        self.assertEqual([k["custom_id"] for k in bulunan], ["a__2"])

    def test_bulunamayan_bos_doner(self):
        self.assertEqual(cg.cue_ara(self.kayitlar, cue_id=999), [])


class ReplayTest(unittest.TestCase):
    def test_govde_orijinalin_AYNISI(self):
        kayit = cg.kayit_olustur("a__1", SENKRON_INFO, GOVDE, zaman=1.0)
        govde = cg.replay_govdesi(kayit, "Sen bir altyazı çevirmenisin.")
        self.assertEqual(govde["model"], "gpt-5.4-mini")
        self.assertEqual(govde["max_completion_tokens"], 4000)
        self.assertEqual(govde["messages"][1]["content"],
                         GOVDE["messages"][1]["content"])

    def test_gpt5_ailesinde_rol_developer(self):
        """gpt-5/o-serisi `system` rolünü kabul etmiyor; yeniden gönderim
        orijinalin kabul edildiği biçimi kurmalı."""
        kayit = cg.kayit_olustur("a__1", SENKRON_INFO, GOVDE, zaman=1.0)
        self.assertEqual(
            cg.replay_govdesi(kayit, "x")["messages"][0]["role"], "developer")

    def test_klasik_modelde_rol_system(self):
        govde = dict(GOVDE, model="gpt-4o-mini")
        kayit = cg.kayit_olustur("a__1", SENKRON_INFO, govde, zaman=1.0)
        self.assertEqual(
            cg.replay_govdesi(kayit, "x")["messages"][0]["role"], "system")


class KarsilastirTest(unittest.TestCase):
    def setUp(self):
        self.kayit = cg.kayit_olustur("a__1", SENKRON_INFO, GOVDE, zaman=1.0)

    def test_ZAMAN_DAMGASIYLA_anahtarlanir(self):
        """Ölçülen vaka: numaraya göre karşılaştırma 5.901 fark gösterdi,
        gerçek fark 1.309'du. Anahtar zaman damgası olmalı."""
        satirlar = cg.karsilastir(
            self.kayit, {"12": "Merhaba.", "13": "İkinci."},
            {"12": "Selam.", "13": "İkinci."})
        self.assertEqual(satirlar[0]["zaman"],
                         "00:01:00,000 --> 00:01:02,000")
        self.assertTrue(satirlar[0]["degisti"])
        self.assertFalse(satirlar[1]["degisti"])

    def test_eksik_yeni_ceviri_bos_gosterilir(self):
        satirlar = cg.karsilastir(self.kayit, {"12": "Merhaba."}, {})
        self.assertEqual(satirlar[0]["yeni"], "")
        self.assertTrue(satirlar[0]["degisti"])

    def test_yalniz_bosluk_farki_DEGISIKLIK_sayilmaz(self):
        satirlar = cg.karsilastir(self.kayit, {"12": "Merhaba."},
                                  {"12": "  Merhaba. "})
        self.assertFalse(satirlar[0]["degisti"])


class BudamaTest(unittest.TestCase):
    def test_en_yeniler_kalir(self):
        dizin = tempfile.mkdtemp()
        try:
            for i in range(6):
                yol = os.path.join(dizin, "k%d.jsonl" % i)
                with io.open(yol, "w", encoding="utf-8") as fh:
                    fh.write("{}" + NL)
                os.utime(yol, (1000 + i, 1000 + i))
            cg.budan(dizin, sinir=3)
            kalan = sorted(os.listdir(dizin))
            self.assertEqual(kalan, ["k3.jsonl", "k4.jsonl", "k5.jsonl"])
        finally:
            shutil.rmtree(dizin, ignore_errors=True)

    def test_olmayan_dizin_patlamaz(self):
        self.assertEqual(cg.budan(os.path.join(tempfile.gettempdir(), "yok_")), [])


class AkisBaglantisiTest(unittest.TestCase):
    """Dört akışın dördü de günlüğe yazmalı.

    Bu depoda tekrarlayan hata sınıfı: özellik akışlardan yalnız birine
    bağlanıyor ve öbür akışta sessizce yok oluyor.
    """
    def setUp(self):
        with io.open(os.path.join(KOK, "subtitle_translator_gui.py"),
                     encoding="utf-8") as fh:
            self.gui = fh.read()
        with io.open(os.path.join(KOK, "hybrid_translate.py"),
                     encoding="utf-8") as fh:
            self.ht = fh.read()

    def test_write_results_yaziyor(self):
        """Senkron, batch ve batch kurtarma buradan geçiyor."""
        self.assertIn("for _req in (translation_requests or ()):", self.gui)
        self.assertEqual(
            self.gui.count("_chunk_gunluge_yaz(" + chr(10)), 2)

    def test_sync_hybrid_yaziyor(self):
        self.assertIn('akis="sync_hybrid"', self.gui)

    def test_hibrit_batch_yaziyor(self):
        self.assertEqual(
            self.gui.count("journal_fn=_chunk_gunluk_geri_cagrisi"), 4)
        self.assertIn("journal_fn=None", self.ht)

    def test_gunluk_cagrisi_EKSIK_METOTTA_bile_cevriyi_dusurmez(self):
        """Yazımın yutulması yetmiyor; geri çağrının KURULMASI da
        yutulmalı. Bu ayrımı bir test yakaladı: eksik nitelikli bir
        örnekte çağrı, çevirinin ortasında AttributeError veriyordu."""
        import types
        import subtitle_translator_gui as g
        bos = types.SimpleNamespace()
        g._chunk_gunluge_yaz(bos, "a__1", [], {}, "")
        self.assertIsNone(g._chunk_gunluk_geri_cagrisi(bos))

    def test_BASARISIZ_chunklar_da_gunluge_giriyor(self):
        """Adli açıdan en değerli kayıtlar başarısız olanlar; yalnız
        başarılıları yazmak aranan vakayı dışarıda bırakır."""
        self.assertIn('_gunluge_yaz(cid, info, hata="malformed_response")',
                      self.ht)
        self.assertIn('hata="content_filter"', self.ht)

    def test_gunluk_yazimi_cevriyi_dusurmez(self):
        i = self.gui.index("def _chunk_gunluk_kaydet")
        govde = self.gui[i:i + 2600]
        self.assertIn("except Exception:", govde)


class BoyutSiniriTest(unittest.TestCase):
    """Sayi sinirı tek basına diskte ne olacagını söylemiyor.

    Ölçülen gerçek boyut: dosya basına 312 KB, chunk basına 7,6 KB.
    Otuz dosyalık bir kosu 9,1 MB eder; yirmi böyle kosu 183 MB.
    """
    def _dizin(self, boyutlar):
        dizin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dizin, True)
        for i, boyut in enumerate(boyutlar):
            yol = os.path.join(dizin, "k%d.jsonl" % i)
            with io.open(yol, "w", encoding="utf-8") as fh:
                fh.write("x" * boyut)
            os.utime(yol, (1000 + i, 1000 + i))
        return dizin

    def test_bayt_siniri_sayidan_once_baglar(self):
        dizin = self._dizin([400, 400, 400, 400])
        cg.budan(dizin, sinir=10, bayt_siniri=1000)
        self.assertEqual(sorted(os.listdir(dizin)), ["k2.jsonl", "k3.jsonl"])

    def test_EN_YENI_gunluk_tek_basina_siniri_assa_bile_silinmez(self):
        """Silinirse teşhis edilecek şey kalmaz."""
        dizin = self._dizin([50, 5000])
        cg.budan(dizin, sinir=10, bayt_siniri=100)
        self.assertEqual(os.listdir(dizin), ["k1.jsonl"])

    def test_sinir_altinda_hicbir_sey_silinmez(self):
        dizin = self._dizin([10, 10])
        self.assertEqual(cg.budan(dizin, sinir=10, bayt_siniri=10 ** 9), [])
        self.assertEqual(len(os.listdir(dizin)), 2)


if __name__ == "__main__":
    unittest.main()
