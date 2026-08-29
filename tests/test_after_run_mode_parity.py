# -*- coding: utf-8 -*-
"""Kip seçici, metni yeniden yazan HER kutuyu kapatmalı.

`_apply_after_run_mode("llm")` kullanıcıya "teslim metni yeniden
yazılmayacak" sözü verir. Bir geçiş iki ayrı kutuyla açılabiliyorsa
(`if not (ai_on or fast_on): return blocks`) ikisi de listede olmalı;
yoksa kip yalnız yarısını kapatır ve söz tutulmaz.

Gerçek örnek: `merge_cues_var` listedeydi, `ai_segment_var` değildi.
AI segmentasyonu açık olan kullanıcı "llm" kipinde de cue birleştirmesi
alıyordu — hem metin dağılımı hem zaman damgaları değişiyordu.
"""
import ast
import io
import os
import re
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import subtitle_translator_gui as g

KAYNAK = os.path.join(KOK, "subtitle_translator_gui.py")


def _fonksiyon_govdesi(ad):
    metin = io.open(KAYNAK, encoding="utf-8-sig").read()
    satirlar = metin.split("\n")
    for node in ast.walk(ast.parse(metin)):
        if isinstance(node, ast.FunctionDef) and node.name == ad:
            return "\n".join(satirlar[node.lineno - 1:node.end_lineno])
    raise AssertionError("fonksiyon bulunamadı: %s" % ad)


class AfterRunModeParityTest(unittest.TestCase):
    def test_ai_segment_yeniden_yazma_sayilir(self):
        self.assertIn("ai_segment_var", g.App._TEXT_REWRITING_TOGGLES)

    def test_merge_cues_kapisinin_iki_yarisi_da_listede(self):
        """`_maybe_merge_cues` erken dönüşünü hangi kutular açıyorsa hepsi."""
        govde = _fonksiyon_govdesi("_maybe_merge_cues")
        kutular = set(re.findall(r"self\.([a-z0-9_]+_var)\.get", govde))
        self.assertIn("merge_cues_var", kutular, "test eskimiş olabilir")
        self.assertIn("ai_segment_var", kutular, "test eskimiş olabilir")
        for kutu in kutular:
            self.assertIn(
                kutu, g.App._TEXT_REWRITING_TOGGLES,
                "%s geçişi açabiliyor ama kip onu kapatmıyor" % kutu)

    def test_liste_gercek_kutu_adlari(self):
        """Listedeki her ad gerçekten bir `*_var` olmalı (yazım hatası tuzağı).

        Olmayan bir ada yazılırsa `getattr(...) is None` sessizce atlanır ve
        kip o kutuyu hiç kapatmaz — hata vermeden.
        """
        with io.open(KAYNAK, encoding="utf-8-sig") as fh:
            metin = fh.read()
        for kutu in g.App._TEXT_REWRITING_TOGGLES:
            self.assertTrue(
                re.search(r"self\.%s\s*=\s*ctk\." % re.escape(kutu), metin),
                "%s hiçbir yerde tanımlanmıyor" % kutu)

    def test_llm_kipinde_acik_kalmasi_gerekenler_cakismaz(self):
        ortak = (set(g.App._TEXT_REWRITING_TOGGLES)
                 & set(g.App._LLM_MODE_REQUIRED_ON))
        self.assertEqual(ortak, set(),
                         "aynı kutu hem kapatılıp hem açılamaz: %s" % ortak)


if __name__ == "__main__":
    unittest.main()
