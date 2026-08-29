# -*- coding: utf-8 -*-
"""`MISSING_REPLICA` — kaynaktaki repliğin teslimde düşmesi.

Brief: `plans/replik-kaybi-dogrulayici-brief.md`.

Bu sınıfı hiçbir mevcut doğrulayıcı görmüyordu: beş gerçek kayıpta
`LENGTH_RATIO_OUTLIER` beş kez False, `_numeric_token_mismatch` sessiz
(sayı yok). Yani tam bir replik düşse bile teslim sessizce geçiyordu.

Brief'in kuralı 23 dosyada 4/4 doğruydu; 372 dosyaya (310.378 cue)
uygulandığında üç yanlış alarm sınıfı çıktı ve kural daraltıldı:
100 → 15 bulgu / 10 dosya. Aşağıdaki "yakalamamalı" testleri o üç sınıfı
kilitler — biri geri gelirse bulgu sayısı yeniden şişer.
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import hybrid_translate as ht

NL = chr(10)


class MissingReplicaTest(unittest.TestCase):

    # ── Brief'in ZORUNLU yakalamalari (The Reckoning, elle dogrulanmis) ──
    def test_ilk_replik_dusmus(self):
        self.assertTrue(ht._missing_replica(
            "- They're after Hazlitt's guts." + NL
            + "- I didn't know he had any.",
            "Onda öyle bir şey olduğunu bilmiyordum."))

    def test_ikinci_replik_dusmus(self):
        self.assertTrue(ht._missing_replica(
            "- Mrs Marler phoned." + NL + "- Well, call her back, then.",
            "- Bayan Marler aradı."))
        self.assertTrue(ht._missing_replica(
            "- He'll not be long with us." + NL + "- Don't be ridiculous, Ma.",
            "- Bizimle uzun kalmayacak."))

    def test_ikisi_de_yerindeyse_bulgu_yok(self):
        self.assertFalse(ht._missing_replica(
            "- Mrs Marler phoned." + NL + "- Well, call her back, then.",
            "- Bayan Marler aradı." + NL + "- O zaman geri ara."))

    def test_tek_replikli_cue_kapsam_disi(self):
        self.assertFalse(ht._missing_replica("- Tek replik.", "Tek replik."))
        self.assertFalse(ht._missing_replica("Tiresiz metin.", "Metin."))

    # ── A: parantezsiz BUYUK HARFLI ses etiketi ─────────────────────────
    def test_parantezli_SDH_replik_sayilmaz(self):
        self.assertFalse(ht._missing_replica(
            "- (Gun pops, cat shrieks)" + NL + "- Death to Debussy!",
            "- Debussy'ye ölüm!"))
        self.assertFalse(ht._missing_replica(
            "-[laughs]" + NL + "- When you coming down?",
            "Ne zaman iniyorsun?"))

    def test_parantezsiz_caps_ses_etiketi_replik_sayilmaz(self):
        """`- CHEERING`, `- HE SNIFFS` — brief bunları görmüyordu."""
        for etiket in ("- CHEERING", "- HE SNIFFS", "- LOUD METALLIC BANGING",
                       "- SHOUTING AND CHEERING"):
            self.assertFalse(
                ht._missing_replica(etiket + NL + "- Yeah, come on!",
                                    "Evet, hadi!"), etiket)

    def test_bagirilan_GERCEK_replik_etiket_sayilmaz(self):
        """Noktalama taşıyan caps satır diyalogdur, ses etiketi değil."""
        self.assertTrue(ht._missing_replica(
            "- STOP!" + NL + "- I said stop.", "Dur dedim."))

    # ── B: kaynakta yinelenen satir ─────────────────────────────────────
    def test_kaynakta_yinelenen_satir_tek_sayilir(self):
        """Yayın altyazısı satırı tireyle tekrarlayabiliyor."""
        self.assertFalse(ht._missing_replica(
            "- to the 4 cardinal points." + NL + "- To the 4 cardinal points.",
            "Dört ana yöne."))

    def test_teslimdeki_tekrar_TOPLANMAZ(self):
        """İki farklı kaynak satırı aynı Türkçeye çevrilmişse bulgu ÜRETME.

        İlk denemede teslimde de toplama yapılmıştı ve bulgu 100'den
        131'e ÇIKMIŞTI — kural bulgu üretiyordu.
        """
        self.assertFalse(ht._missing_replica(
            "- We must play high." + NL + "- We'll play high.",
            "- Büyük oynayacağız." + NL + "- Büyük oynayacağız."))

    # ── C: teslim replikleri tek satirda birlestirmis ───────────────────
    def test_tek_satirda_birlesmis_replik_kayip_sayilmaz(self):
        self.assertFalse(ht._missing_replica(
            "- O que achas?" + NL + "- Cheira a ramen.",
            "- Ne diyorsun? - Tavuklu ramen gibi kokuyor."))

    def test_ayiricidan_sonra_bosluk_zorunlu_degil(self):
        self.assertFalse(ht._missing_replica(
            "-Yeah." + NL + "-Almost took my shit.",
            "-Evet. -Az kalsın beni alıyordu."))

    def test_bastaki_tirnak_tireyi_gizlemez(self):
        self.assertFalse(ht._missing_replica(
            "-Anything to eat?" + NL + "-Battenberg cake.",
            '"-Yiyecek bir şey var mı?' + NL + '-Battenberg keki."'))

    # ── Sayac ve kayit ──────────────────────────────────────────────────
    def test_replik_sayaci(self):
        self.assertEqual(ht._replica_count("- bir" + NL + "- iki"), 2)
        self.assertEqual(ht._replica_count("-[laughs]" + NL + "- iki"), 1)
        self.assertEqual(ht._replica_count("tiresiz"), 0)
        self.assertEqual(ht._replica_count(""), 0)

    def test_yeniden_yazma_kumesine_GIRMEZ(self):
        """Yalnız rapor: otomatik düzeltici bu sebebe dokunmamalı.

        `_SEMANTIC_RECONCILIATION_REASONS` Nihai Anlam Mutabakatı'nın hangi
        sebeplerde cue'yu YENİDEN YAZACAĞINI belirler. Brief bu
        doğrulayıcının yalnız rapor etmesini istiyor; düşen repliği
        yeniden yazmak model işidir ve karar insanda kalır.
        """
        self.assertNotIn("MISSING_REPLICA",
                         ht._SEMANTIC_RECONCILIATION_REASONS)
        self.assertFalse(
            ht._is_semantic_reconciliation_reason("MISSING_REPLICA"))

    def test_run_validators_sebebi_uretiyor(self):
        """Rapora girmesi için `run_validators` reason döndürmeli."""
        import io as _io
        with _io.open("hybrid_translate.py", encoding="utf-8") as fh:
            kaynak = fh.read()
        self.assertIn('reasons.append("MISSING_REPLICA")', kaynak)

    def test_bos_girdi_patlamaz(self):
        self.assertFalse(ht._missing_replica("", ""))
        self.assertFalse(ht._missing_replica(None, None))


if __name__ == "__main__":
    unittest.main()
