# -*- coding: utf-8 -*-
"""Etiket geri yükleme anahtarı: önce ZAMAN DAMGASI, sonra cue numarası.

`_restore_tags_blocks` kaynağı önce numarayla arıyordu ve zaman damgasını
yalnız numara BOŞ dönerse deniyordu. Teslimde cue sayısı kaydığında numara
araması boş dönmez — BAŞKA bir cue'yu bulur. Dolu olduğu için zaman yedeğine
hiç düşülmez ve o yabancı cue'nun biçim etiketi buraya uygulanır.

Ölçüldü (86 filmlik koleksiyon):
  · tam-cue italik kaybı 7 → 0
  · iki anahtarın farklı kaynak seçtiği cue: 24.374
  · bunların 813'ünde numarayla seçilen kaynak biçim etiketi taşıyor,
    yani numara-önce davranışta yanlış etiket uygulanırdı.

Somut vaka (the.possessed, teslim 672 / kaynak 669 cue):
  teslim #459 `tek bağımdı.`
  numarayla  → `Mr. Bernard?`
  zamanla    → `<i>to the world outside my room.</i>`
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class TagRestoreKeyOrderTest(unittest.TestCase):
    def test_numara_kaydiginda_zaman_damgasi_kazanir(self):
        bloklar = [("459", "00:55:42,339 --> 00:55:45,628", "tek bağımdı.")]
        raw_map = {"459": "Mr. Bernard?"}
        kaynak = [("456", "00:55:42,339 --> 00:55:45,628",
                   "<i>to the world outside my room.</i>")]
        sonuc = g._restore_tags_blocks(bloklar, raw_map, kaynak)
        self.assertEqual(sonuc[0][2], "<i>tek bağımdı.</i>")

    def test_yabanci_cue_etiketi_uygulanmaz(self):
        """Numarayla bulunan cue italikse ama zamanla bulunan değilse."""
        bloklar = [("901", "00:10:00,000 --> 00:10:02,000",
                    "Nereden geldin?")]
        raw_map = {"901": "<i>♪ ...with another man ♪</i>"}
        kaynak = [("900", "00:10:00,000 --> 00:10:02,000",
                   "Where did you come from?")]
        sonuc = g._restore_tags_blocks(bloklar, raw_map, kaynak)
        self.assertNotIn("<i>", sonuc[0][2])

    def test_zaman_esleşmezse_numaraya_duser(self):
        """Cue birleştirilmişse teslim zamanı kaynakta olmayabilir."""
        bloklar = [("5", "00:01:00,000 --> 00:01:09,000", "Birleşmiş metin.")]
        raw_map = {"5": "<i>Merged source.</i>"}
        kaynak = [("5", "00:01:00,000 --> 00:01:02,000", "<i>Merged source.</i>")]
        sonuc = g._restore_tags_blocks(bloklar, raw_map, kaynak)
        self.assertEqual(sonuc[0][2], "<i>Birleşmiş metin.</i>")

    def test_kaynak_cue_verilmezse_numara_kullanilir(self):
        bloklar = [("3", "00:00:03,000 --> 00:00:05,000", "Metin.")]
        raw_map = {"3": "<i>Text.</i>"}
        sonuc = g._restore_tags_blocks(bloklar, raw_map)
        self.assertEqual(sonuc[0][2], "<i>Metin.</i>")

    def test_bos_harita_bloklari_aynen_dondurur(self):
        bloklar = [("1", "00:00:01,000 --> 00:00:02,000", "Metin.")]
        self.assertEqual(g._restore_tags_blocks(bloklar, {}), bloklar)

    def test_cue_sayisi_ve_zaman_degismez(self):
        bloklar = [("1", "00:00:01,000 --> 00:00:02,000", "bir"),
                   ("2", "00:00:03,000 --> 00:00:04,000", "iki")]
        kaynak = [("1", "00:00:01,000 --> 00:00:02,000", "<i>one</i>"),
                  ("2", "00:00:03,000 --> 00:00:04,000", "two")]
        sonuc = g._restore_tags_blocks(
            bloklar, {c[0]: c[2] for c in kaynak}, kaynak)
        self.assertEqual(len(sonuc), len(bloklar))
        self.assertEqual([r[1] for r in sonuc], [r[1] for r in bloklar])


if __name__ == "__main__":
    unittest.main()
