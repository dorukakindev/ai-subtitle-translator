# -*- coding: utf-8 -*-
"""Cue'da gerçek satır sonu varken kalan literal `\\n` kalıntısı.

`_restore_source_linebreaks` yalnız TEK SATIRLIK cue'ya bakıyordu
(`"\\n" not in value`). Cue zaten iki satırsa hiç çalışmıyor ve kalıntı
teslime çıkıyordu.

Gerçek vaka (s21.the.khmer.rouge, #779):
    teslim  `Güç olmadan⏎adalet\\nacizliktir.`
    kaynak  `Justice without strength⏎is inability.`  (İKİ satır)
Literal olanı da satıra çevirmek ÜÇ satır yapardı ve kaynağın satır
yapısını bozardı; kalıntı boşluğa iner.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

BS = chr(92)
NL = chr(10)
duzelt = g._restore_source_linebreaks


class LiteralNewlineResidueTest(unittest.TestCase):
    def test_tek_satirlik_cue_gercek_satira_cevrilir(self):
        self.assertEqual(duzelt("tek satır" + BS + "nikinci", "one line"),
                         "tek satır" + NL + "ikinci")

    def test_satir_varken_bosluga_iner_ucuncu_satir_ACILMAZ(self):
        metin = "Güç olmadan" + NL + "adalet" + BS + "nacizliktir."
        kaynak = "Justice without strength" + NL + "is inability."
        sonuc = duzelt(metin, kaynak)
        self.assertEqual(sonuc, "Güç olmadan" + NL + "adalet acizliktir.")
        self.assertEqual(sonuc.count(NL), kaynak.count(NL))

    def test_t_harfi_yenmez(self):
        """Karakter sınıfı {boşluk, tab} olmalı; `\\\\t` yazılırsa `t` de siliniyor."""
        metin = "bir t harfi" + NL + "ikinci" + BS + "nüçüncü"
        sonuc = duzelt(metin, "x" + NL + "y")
        self.assertIn("bir t harfi", sonuc)
        self.assertEqual(sonuc, "bir t harfi" + NL + "ikinci üçüncü")

    def test_kaynakta_da_literal_varsa_dokunulmaz(self):
        metin = "kaynakta da" + BS + "n var"
        self.assertEqual(duzelt(metin, "source has" + BS + "n too"), metin)

    def test_kalintisiz_metin_aynen_doner(self):
        for metin in ("normal" + NL + "metin", "tek satır", ""):
            self.assertEqual(duzelt(metin, "x"), metin)

    def test_bosluk_yigilmaz(self):
        metin = "bir" + NL + "iki " + BS + "n üç"
        self.assertEqual(duzelt(metin, "a" + NL + "b"), "bir" + NL + "iki üç")


if __name__ == "__main__":
    unittest.main()
