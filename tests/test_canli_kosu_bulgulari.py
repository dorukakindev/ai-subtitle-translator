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


class TirnakGuardDaraltmasiTest(unittest.TestCase):
    """Tırnak içi ifade eser adı sayılıp sözlükten atılıyordu — fazla geniş.

    Guard'ın attığı terim kaynak dilde kalıyor: 36 dosyalık ölçümde
    atılanların %18'i kaynak biçiminde kalmışken sözlükte kalanların yalnız
    %0,3'ü. Atmak 60 kat daha riskli.

    Arşivde ölçüldü: düşen giriş 313 -> 277, kurtulan 36.
    """

    KAYNAK = ('He read "The Iliad". A "pyrrhic victory" is costly. '
              'We watched "the Lord of the Rings".')

    def _kalan(self, sozluk):
        return set(ht.drop_quoted_work_title_terms(sozluk, self.KAYNAK))

    def test_kucuk_harfle_baslayan_kavram_kalir(self):
        kalan = self._kalan({"pyrrhic victory": "Pirus zaferi"})
        self.assertIn("pyrrhic victory", kalan)

    def test_kucuk_harfle_baslayan_yerlesik_ad_kalir(self):
        """`the Lord of the Rings` -> `Yüzüklerin Efendisi` sözlükte kalmalı."""
        kalan = self._kalan({"the Lord of the Rings": "Yüzüklerin Efendisi"})
        self.assertIn("the Lord of the Rings", kalan)

    def test_buyuk_harfle_baslayan_eser_adi_hala_dusuyor(self):
        kalan = self._kalan({"The Iliad": "İlyada"})
        self.assertNotIn("The Iliad", kalan)

    def test_tirnakta_gecmeyen_terim_etkilenmez(self):
        kalan = self._kalan({"normal": "sıradan"})
        self.assertIn("normal", kalan)

    def test_tek_kucuk_sozcuk_kurali_korunuyor(self):
        """Önceki daraltma bozulmamalı: anılan tek sözcük düşmez."""
        kaynak = 'You know what "cathartic" means?'
        kalan = set(ht.drop_quoted_work_title_terms(
            {"cathartic": "katartik"}, kaynak))
        self.assertIn("cathartic", kalan)


class StandartAnalizOrneklemiTest(unittest.TestCase):
    """Standart derinlik chunk'ın yalnız İLK 250 cue'sunu okuyordu.

    2000'lik bir chunk'ın %87,5'i analize hiç girmiyordu: dosyanın
    sonundaki karakterler, terimler ve hitap kararları görülmüyordu.
    Aynı sayıda cue artık dosyaya YAYILARAK seçilir — maliyet değişmez.

    Kullanıcının koşularında hiç ateşlenmemişti (310 Gelişmiş /
    121 Maksimum / 0 Standart), yani latent bir tuzaktı.
    """

    class _Cue:
        def __init__(self, index):
            self.index = index
            self.start = "00:00:01,000"
            self.end = "00:00:02,000"
            self.text = "satır %d" % index

    def _kimlikler(self, adet, derinlik="standard"):
        cues = [self._Cue(i) for i in range(adet)]
        return [x["id"] for x in
                ht._analysis_sample_for_depth(cues, derinlik)]

    def test_orneklem_dosyanin_tamamina_yayilir(self):
        kimlik = self._kimlikler(2000)
        self.assertGreater(max(kimlik), 1900,
                           "örneklem dosyanın sonunu görmüyor")
        self.assertEqual(min(kimlik), 0)

    def test_ornek_sayisi_degismedi(self):
        self.assertEqual(len(self._kimlikler(2000)), 250)

    def test_kucuk_dosyada_hepsi_alinir(self):
        self.assertEqual(len(self._kimlikler(100)), 100)

    def test_derin_modlar_etkilenmedi(self):
        self.assertGreater(len(self._kimlikler(2000, "maximum")), 250)

    def test_kimlikler_artan_ve_tekil(self):
        kimlik = self._kimlikler(2000)
        self.assertEqual(kimlik, sorted(kimlik))
        self.assertEqual(len(kimlik), len(set(kimlik)))


class AsamaCheckpointBudamaTest(unittest.TestCase):
    """Aşama deposunda hiçbir sınır yoktu; kardeş depoda ikisi de var.

    Kayıt yalnız dosya BAŞARIYLA bitince siliniyordu: yarım kalan,
    karantinaya giden, vazgeçilen her dosya kalıcı kalıyordu.
    Gerçek depo ölçüldü: 82 kayıt / 4,82 MB, kayıt başına ~60 KB —
    kardeşin 3000 sınırı burada ~176 MB ederdi.
    """

    def test_yas_siniri_isliyor(self):
        import time
        simdi = time.time()
        kayitlar = {
            "yeni": {"updated_at": simdi},
            "eski": {"updated_at": simdi - 40 * 86400},
        }
        dusen = gui._prune_sync_stage_entries(kayitlar)
        self.assertEqual(dusen, 1)
        self.assertIn("yeni", kayitlar)
        self.assertNotIn("eski", kayitlar)

    def test_damgasiz_kayit_YAS_kuralindan_muaf(self):
        """`updated_at=0` taşıyan göç kaydı 'çok eski' sayılmamalı."""
        kayitlar = {"damgasiz": {"updated_at": 0}}
        self.assertEqual(gui._prune_sync_stage_entries(kayitlar), 0)
        self.assertIn("damgasiz", kayitlar)

    def test_sayi_siniri_en_yenileri_tutar(self):
        import time
        simdi = time.time()
        kayitlar = {"k%d" % i: {"updated_at": simdi - i}
                    for i in range(gui.SYNC_STAGE_CKPT_MAX_ENTRIES + 40)}
        gui._prune_sync_stage_entries(kayitlar)
        self.assertEqual(len(kayitlar), gui.SYNC_STAGE_CKPT_MAX_ENTRIES)
        self.assertIn("k0", kayitlar)

    def test_sinir_kardes_depodan_KUCUK(self):
        """Aşama kaydı ~60 KB; kardeşin sınırı burada ~176 MB ederdi."""
        self.assertLess(gui.SYNC_STAGE_CKPT_MAX_ENTRIES,
                        gui.SYNC_CKPT_MAX_ENTRIES)

    def test_bos_depo_patlamaz(self):
        self.assertEqual(gui._prune_sync_stage_entries({}), 0)


class KarakterSeciminiTekYereBaglaTest(unittest.TestCase):
    """Aynı "ana karakterler kimdir" kararı dört yerde farklı kırpılıyordu.

    Kırpma sınırları 6 / 6 / 5 ve log için 4'tü — bu depoda tekrar eden bug
    sınıfı tam olarak budur. Ayrıca listeye kişi olmayan girişler sızıyor ve
    prompt'ta bir slot yiyordu: 4.588 karakter adında 32'si böyleydi, 5'i
    ilk altı slotta.
    """

    class _Karakter:
        def __init__(self, name):
            self.name = name
            self.speaking_style = ""

    def _secim(self, adlar):
        return [c.name for c in ht.prompt_characters(
            [self._Karakter(a) for a in adlar])]

    def test_kisi_olmayanlar_elenir(self):
        for ad in ("Song lyrics", "Crowd", "CHORUS", "Koro", "Kalabalık",
                   "Congregation", "ALL", "BOTH", "NEWSREEL",
                   "HE SPEAKS IN GREEK", "[LAUGHS] / [SOBS]",
                   "Şarkı sözleri"):
            self.assertTrue(ht._is_not_a_person(ad), ad)

    def test_adsiz_ama_GERCEK_konusmacilar_korunur(self):
        """Raporun açık uyarısı: bunlar eleme listesine GİRMEMELİ."""
        for ad in ("Doctor", "Princess", "King", "Man", "Woman", "Narrator",
                   "German-speaking artist", "Alexander"):
            self.assertFalse(ht._is_not_a_person(ad), ad)

    def test_elenen_slot_gercek_karaktere_gider(self):
        """Ölçümdeki somut vaka: Alexander ve Neoptolemus kapsam dışıydı."""
        secim = self._secim([
            "Song lyrics", "Alexander", "Crowd", "Neoptolemus", "CHORUS",
            "Doctor", "King", "Narrator", "Rosie", "HE SPEAKS IN GREEK"])
        self.assertIn("Alexander", secim)
        self.assertIn("Neoptolemus", secim)
        self.assertNotIn("Song lyrics", secim)
        self.assertNotIn("CHORUS", secim)

    def test_sinir_tek_sabitten_gelir(self):
        secim = self._secim(["K%d" % i for i in range(20)])
        self.assertEqual(len(secim), ht._PROMPT_CHARACTER_LIMIT)

    def test_hepsi_elenirse_orijinal_kullanilir(self):
        """Boş karakter listesi prompt'u sessizce fakirleştirirdi."""
        secim = self._secim(["Crowd", "CHORUS"])
        self.assertEqual(secim, ["Crowd", "CHORUS"])

    def test_bos_liste_patlamaz(self):
        self.assertEqual(ht.prompt_characters([]), [])
        self.assertEqual(ht.prompt_characters(None), [])

    def test_ham_kirpma_kalmadi(self):
        """Dört ayrı `characters[:N]` yerine tek fonksiyon."""
        import io as _io
        with _io.open("hybrid_translate.py", encoding="utf-8") as fh:
            kaynak = fh.read()
        for desen in ("characters[:6]", "characters[:5]"):
            self.assertNotIn(desen, kaynak,
                             "ham kırpma geri geldi: %s" % desen)


if __name__ == "__main__":
    unittest.main()
