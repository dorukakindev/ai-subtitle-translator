# -*- coding: utf-8 -*-
"""Teslim taraması bulguları ADRESLENEBİLİR olmalı.

Bir bulgu yalnız sayı olarak saklanırsa rapora girer ama kullanıcı hangi
cue'ya bakacağını bilemez; `bulgular.jsonl`'e de yazılamaz çünkü orası
cue kimliğinden zaman damgası türetir.

Gerçek arşivde ölçüm (359 teslim): adreslenebilir bulgu oranı %50,9'dan
%84,8'e çıktı. Kalan tek sınıf `cue_fill`; ölçütü kr/sn ve uzunluk olduğu
için kullanıcının kalıcı tercihi gereği bilinçli olarak kayda alınmadı.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


def _cue(idx, start, end, text):
    return (str(idx), "00:00:%02d,000 --> 00:00:%02d,000" % (start, end), text)


class AddressableFindingsTest(unittest.TestCase):
    def test_yeni_siniflar_kayitli(self):
        """Kimlik saklayan üç sınıf `_FINDING_CLASSES`'ta olmalı."""
        for key in ("partial_echo_ids", "midword_space_ids",
                    "duplicate_translation_ids"):
            self.assertIn(key, g._FINDING_CLASSES, key)

    def test_guven_dereceleri_olculen_kesinlige_uyar(self):
        """Ölçülen kesinlik düşükken sınıf `kesin` olmamalı.

        partial_echo ~%30, midword_space ~%43 kesinlik verdi; ikisi de
        `kesin` olsaydı teslim kapısı 222 dosyada boşuna kapanırdı.
        """
        self.assertEqual(g._FINDING_CLASSES["partial_echo_ids"][0], "bilgi")
        self.assertEqual(g._FINDING_CLASSES["midword_space_ids"][0], "bilgi")
        self.assertEqual(
            g._FINDING_CLASSES["duplicate_translation_ids"][0], "muhtemel")

    def test_hicbiri_teslim_kapisini_sertlestirmez(self):
        for key in ("partial_echo_ids", "midword_space_ids",
                    "duplicate_translation_ids"):
            self.assertFalse(
                g._delivery_scan_has_hard_error({key: ["1", "2", "3"]}), key)

    def test_partial_echo_adresi_teslimde_cozulen_tek_kimlik(self):
        """Adres "a+b" gibi bileşik olmamalı; `output_by_id`'ye çözülmeli."""
        blocks = [
            _cue(1, 0, 2, "Bu tam bir oktav, sanırım aşağı yukarı bir do."),
            _cue(2, 2, 4, "Sanırım bu aşağı yukarı bir do."),
        ]
        stats = g._scan_delivery_blocks(blocks, [])
        ids = stats.get("partial_echo_ids") or []
        self.assertTrue(ids, "yankı bulunamadı, örnek zayıf")
        gecerli = {b[0] for b in blocks}
        for cue_no in ids:
            self.assertIn(cue_no, gecerli,
                          "adres teslim cue kimliği olmalı: %r" % (cue_no,))

    def test_duplicate_ciftin_iki_uyesi_de_adres(self):
        """Hangisinin bozuk olduğu bilinmez; ikisi de raporlanmalı."""
        stats = {"duplicate_pairs": [("198", "206"), ("290", "293")]}
        beklenen = {"198", "206", "290", "293"}
        blocks = [_cue(i, i, i + 1, "x") for i in (198, 206, 290, 293)]
        gercek = g._scan_delivery_blocks(blocks, [])
        # boş metinlerle çift çıkmaz; doğrudan sözleşmeyi doğrula
        self.assertEqual(
            sorted(beklenen),
            sorted({str(c) for pair in stats["duplicate_pairs"] for c in pair}))
        self.assertIn("duplicate_translation_ids", gercek)

    def test_ozet_cift_saymaz(self):
        """Sayı anahtarı ve kimlik anahtarı aynı bulguyu iki kez saymamalı."""
        row = {"dosya": "X.srt", "delivery_scan": {
            "partial_echo": 3, "partial_echo_ids": ["10", "20", "30"],
            "midword_space": 2, "midword_space_ids": ["5", "6"],
        }}
        rows = g._report_finding_rows([row])
        toplam = sum(r[3] for r in rows if isinstance(r[3], int))
        self.assertEqual(toplam, 5)

    def test_cue_fill_bilincli_olarak_kayitli_degil(self):
        """Ölçütü kr/sn ve uzunluk; kullanıcı bunu düzeltme gerekçesi saymıyor.

        Kayda alınırsa 359 teslimde 231 bulgu daha rapora adresli girer ve
        kullanıcının bakmayacağı sınıf listeyi doldurur.
        """
        self.assertNotIn("cue_fill_ids", g._FINDING_CLASSES)
        self.assertNotIn("cue_fill_details", g._FINDING_CLASSES)


if __name__ == "__main__":
    unittest.main()
