# -*- coding: utf-8 -*-
"""Çevirmen glossu ve alıntı zinciri dedektörleri.

İkisi de YALNIZ RAPOR eder; hiçbir cue'yu değiştirmez. Gerekçe: parantezi
silmek anlamı değiştirebilir, alıntı tırnağını ölçütsüz kırpmak ise ilahiyi
ve şiiri bozar (denetimde işaretlenen 7 bloğun 4'ü meşru çıkmıştı).

Ölçüm — 86 filmlik "Tekrar Geçilecek" koleksiyonu, programın YEDEK çıktısı:
  translator_gloss_ids  81 bulgu / 15 dosya
  quote_chain_ids       43 zincir / 12 dosya  (eşik 3 cue; eşiksiz 72)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

Q = chr(34)
NL = chr(10)


def _cue(idx, text):
    return (str(idx), "00:00:%02d,000 --> 00:00:%02d,000" % (idx, idx + 1),
            text)


class TranslatorGlossTest(unittest.TestCase):
    def test_kaynakta_olmayan_parantez_bulunur(self):
        bloklar = [_cue(1, "Schwabing'de" + NL + "(Münih semti).")]
        src = {"1": "In Schwabing."}
        self.assertEqual(g._translator_gloss_ids(bloklar, src), ["1"])

    def test_kaynakta_da_parantez_varsa_bulgu_degil(self):
        bloklar = [_cue(1, "Bu (böyle) oldu.")]
        src = {"1": "It happened (like this)."}
        self.assertEqual(g._translator_gloss_ids(bloklar, src), [])

    def test_sarki_sozune_konan_aciklama_da_yakalanir(self):
        bloklar = [_cue(1, "♫ Demokrat (Demokrat Parti), Cumhuriyetçi")]
        src = {"1": "♫ Democrat, Republican, yuppy"}
        self.assertEqual(g._translator_gloss_ids(bloklar, src), ["1"])

    def test_kaynak_yoksa_bulgu_uretilmez(self):
        """Kaynak eşleşmesi olmadan parantezin eklendiği kanıtlanamaz."""
        bloklar = [_cue(1, "Bir (açıklama) var.")]
        self.assertEqual(g._translator_gloss_ids(bloklar, None), [])
        self.assertEqual(g._translator_gloss_ids(bloklar, {"1": ""}), [])

    def test_bos_parantez_ve_tek_karakter_sayilmaz(self):
        bloklar = [_cue(1, "Bir () ve (x) var.")]
        self.assertEqual(g._translator_gloss_ids(bloklar, {"1": "One."}), [])


class QuoteChainTest(unittest.TestCase):
    def test_uc_cue_luk_zincir_ilk_kimlikle_bildirilir(self):
        bloklar = [_cue(i, Q + "satır %d" % i) for i in (1, 2, 3)]
        self.assertEqual(g._quote_chain_open_ids(bloklar), ["1"])

    def test_iki_cue_luk_zincir_ESIGIN_ALTINDA(self):
        """Ayrı ayrı kısa alıntılar da böyle görünür; eşik 3."""
        bloklar = [_cue(1, Q + "bir"), _cue(2, Q + "iki"), _cue(3, "normal")]
        self.assertEqual(g._quote_chain_open_ids(bloklar), [])

    def test_kendi_icinde_kapanan_alinti_zincir_degil(self):
        bloklar = [_cue(i, Q + "tam alıntı" + Q) for i in (1, 2, 3)]
        self.assertEqual(g._quote_chain_open_ids(bloklar), [])

    def test_egri_tirnak_da_sayilir(self):
        bloklar = [_cue(i, chr(8220) + "satır %d" % i) for i in (1, 2, 3)]
        self.assertEqual(g._quote_chain_open_ids(bloklar), ["1"])

    def test_iki_ayri_zincir_ayri_bildirilir(self):
        bloklar = ([_cue(i, Q + "a") for i in (1, 2, 3)]
                   + [_cue(4, "araya giren")]
                   + [_cue(i, Q + "b") for i in (5, 6, 7)])
        self.assertEqual(g._quote_chain_open_ids(bloklar), ["1", "5"])


class RegistrationTest(unittest.TestCase):
    def test_ikisi_de_kayitli(self):
        for key in ("translator_gloss_ids", "quote_chain_ids"):
            self.assertIn(key, g._FINDING_CLASSES, key)

    def test_hicbiri_teslim_kapisini_sertlestirmez(self):
        """Yalnız rapor: bu sınıflar dosyayı teslimden alıkoymamalı."""
        for key in ("translator_gloss_ids", "quote_chain_ids"):
            self.assertFalse(
                g._delivery_scan_has_hard_error({key: ["1", "2", "3"]}), key)

    def test_tarayici_kimlikleri_uretir(self):
        bloklar = ([_cue(1, "Schwabing'de (Münih semti).")]
                   + [_cue(i, Q + "satır") for i in (2, 3, 4)])
        kaynak = [(str(i), b[1], "In Schwabing." if i == 1 else "x")
                  for i, b in enumerate(bloklar, start=1)]
        stats = g._scan_delivery_blocks(bloklar, kaynak)
        self.assertIn("translator_gloss_ids", stats)
        self.assertIn("quote_chain_ids", stats)
        self.assertEqual(stats["quote_chain_ids"], ["2"])


if __name__ == "__main__":
    unittest.main()
