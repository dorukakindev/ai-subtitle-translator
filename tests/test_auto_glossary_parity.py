# -*- coding: utf-8 -*-
"""Auto-Glossary, kalite/teslim denetimini geçemeyen dosyada çalışmamalı.

Akış paritesi: düz (`_write_results`) ve iki-dalgalı zincirli
(`_run_sync_hybrid`) yollar başarısız dosyada erken `continue` ile
Auto-Glossary'yi atlar. `_run_hybrid` (batch+hibrit) ise koşulsuz
çağırıyordu — doğrulanmamış çıktı için ücretli yardımcı istek harcanıyor
ve `_wait_for_dialog_event` işçiyi 5 dakikaya kadar bloklayabiliyordu.
"""
import ast
import os
import sys
import unittest
from pathlib import Path

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

KAYNAK = os.path.join(KOK, "subtitle_translator_gui.py")


def _fonksiyon_govdesi(ad):
    metin = Path(KAYNAK).read_text(encoding="utf-8-sig")
    satirlar = metin.split("\n")
    for node in ast.walk(ast.parse(metin)):
        if isinstance(node, ast.FunctionDef) and node.name == ad:
            return "\n".join(satirlar[node.lineno - 1:node.end_lineno])
    raise AssertionError("fonksiyon bulunamadı: %s" % ad)


class AutoGlossaryParityTest(unittest.TestCase):
    def test_run_hybrid_auto_glossary_kalite_kapili(self):
        """`_run_hybrid`'de Auto-Glossary `_hybrid_quality_failed`'a bağlı."""
        govde = _fonksiyon_govdesi("_run_hybrid")
        idx = govde.find("_run_auto_glossary")
        self.assertNotEqual(idx, -1, "test eskimiş olabilir")
        # Çağrıyı geriye doğru en yakın `auto_glossary_var` kapisina bağla.
        kapi = govde.rfind("auto_glossary_var", 0, idx)
        self.assertNotEqual(kapi, -1)
        aralik = govde[kapi:idx]
        self.assertIn("_hybrid_quality_failed", aralik,
                      "başarısız dosyada ücretli sözlük önerisi çalışıyor")

    def test_run_hybrid_basarisizda_atlama_nedeni_raporlanir(self):
        """Atlama sessiz değil: rapora 'quality_failed' nedeni yazılmalı."""
        govde = _fonksiyon_govdesi("_run_hybrid")
        idx = govde.find("_run_auto_glossary")
        kapi = govde.rfind("auto_glossary_var", 0, idx)
        aralik = govde[kapi:idx]
        self.assertIn('"quality_failed"', aralik)

    def test_duz_ve_iki_dalgali_da_basarisizda_atlar_ve_nedeni_kaydeder(self):
        """Kardeş akışların başarısız dosyada Auto-Glossary'ye hiç
        ulaşmadığını sabitle — referans davranış bu."""
        for ad in ("_write_results", "_run_sync_hybrid"):
            govde = _fonksiyon_govdesi(ad)
            idx = govde.find("_run_auto_glossary")
            self.assertNotEqual(idx, -1, "%s için test eskimiş" % ad)
            # Çağrıdan önce kalite-başarısızlık dalı `continue` ile çıkıyor ve
            # atlama kaydı paylaşılan yardımcıya bırakılıyor.
            oncesi = govde[:idx]
            self.assertIn("continue", oncesi,
                          "%s başarısız dalı artık continue ile çıkmıyor" % ad)
            self.assertIn("_record_file_status", oncesi)
            self.assertIn("_note_skipped_side_effects", oncesi)
        # Neden üçlüsü (unresolved_markers/delivery_failed/quality_failed)
        # yardımcının içinde yaşar.
        yardimci = _fonksiyon_govdesi("_note_skipped_side_effects")
        self.assertIn('setdefault("Auto-Glossary"', yardimci)
        self.assertIn('"quality_failed"', yardimci)


if __name__ == "__main__":
    unittest.main()
