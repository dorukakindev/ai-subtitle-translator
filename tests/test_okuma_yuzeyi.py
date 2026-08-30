# -*- coding: utf-8 -*-
"""İkidilli okuma yüzeyi — kaynak ve teslim yan yana.

NEDEN BULGU PANELİ DEĞİL: bu projede ölçüldü, teslimdeki anlamsal
kusurların tarayıcıyla bulunma oranı %1; kalıntının neredeyse tamamı satır
satır okunarak bulundu. Yüzeyin işi okumayı kolaylaştırmak, bulguları
süzmek değil — bulgu kenarda küçük bir işaret olarak durur.

HİZALAMA ZAMAN DAMGASIYLA: cue numarası anahtar olamaz. Teslim yeniden
numaralandığında tek bir silinmiş cue sonraki her satırı "değişmiş"
gösterir — ölçülen vaka 5.901 sahte fark, gerçeği 1.309.
"""
import io
import os
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import okuma_yuzeyi as oy
import subtitle_translator_gui as gui

NL = chr(10)


def _cue(idx, saniye, metin):
    return (str(idx),
            "00:00:%02d,000 --> 00:00:%02d,000" % (saniye, saniye + 1),
            metin)


class EslemeTest(unittest.TestCase):
    def test_zaman_damgasi_numaradan_ustun(self):
        """Teslim yeniden numaralanmışsa eşleme yine doğru olmalı."""
        kaynak = [_cue(1, 1, "Hello."), _cue(2, 3, "Second.")]
        teslim = [_cue(1, 1, "Merhaba."), _cue(5, 3, "İkinci.")]
        eslesme = oy.satirlari_esle(kaynak, teslim)
        self.assertEqual(len(eslesme), 2)
        self.assertEqual(eslesme[1][0][0], "2")
        self.assertEqual(eslesme[1][1][0], "5")

    def test_zaman_yoksa_numaraya_duser(self):
        kaynak = [("7", "bozuk zaman", "Hello.")]
        teslim = [("7", "başka bozuk", "Merhaba.")]
        eslesme = oy.satirlari_esle(kaynak, teslim)
        self.assertEqual(eslesme[0][0][0], "7")

    def test_teslimde_olmayan_kaynak_cue_GORUNUR(self):
        """Sessizce atlamak, tam da aranan kaybı gizler."""
        kaynak = [_cue(1, 1, "Hello."), _cue(2, 3, "Dropped line.")]
        teslim = [_cue(1, 1, "Merhaba.")]
        eslesme = oy.satirlari_esle(kaynak, teslim)
        tek_tarafli = [(k, t) for k, t in eslesme if t is None]
        self.assertEqual(len(tek_tarafli), 1)
        self.assertEqual(tek_tarafli[0][0][2], "Dropped line.")

    def test_kaynakta_olmayan_teslim_cue_gorunur(self):
        kaynak = [_cue(1, 1, "Hello.")]
        teslim = [_cue(1, 1, "Merhaba."), _cue(2, 9, "discord: ceviri2")]
        eslesme = oy.satirlari_esle(kaynak, teslim)
        self.assertTrue(any(k is None for k, _t in eslesme))

    def test_ayni_zamanli_iki_cue_ayri_eslenir(self):
        """Bir kaynak cue'su iki teslim satırına eşlenmemeli."""
        kaynak = [_cue(1, 1, "A"), _cue(2, 1, "B")]
        teslim = [_cue(1, 1, "a"), _cue(2, 1, "b")]
        eslesme = oy.satirlari_esle(kaynak, teslim)
        kaynaklar = [k[0] for k, _t in eslesme if k]
        self.assertEqual(sorted(kaynaklar), ["1", "2"])

    def test_bos_girdi_patlamaz(self):
        self.assertEqual(oy.satirlari_esle([], []), [])
        self.assertEqual(len(oy.satirlari_esle([], [_cue(1, 1, "x")])), 1)


class HtmlTest(unittest.TestCase):
    KAYNAK = [_cue(1, 1, "- Mrs Marler phoned." + NL + "- Call her back."),
              _cue(2, 3, "Hello <i>there</i>.")]
    TESLIM = [_cue(1, 1, "- Bayan Marler aradı."),
              _cue(2, 3, "Merhaba <i>oradaki</i>.")]

    def _html(self, bulgular=None):
        return oy.html_uret("Test", self.KAYNAK, self.TESLIM, bulgular)

    def test_iki_taraf_da_sayfada(self):
        sayfa = self._html()
        self.assertIn("Mrs Marler phoned", sayfa)
        self.assertIn("Bayan Marler", sayfa)

    def test_html_kacisi_yapiliyor(self):
        """Altyazıdaki `<i>` etiket olarak DEĞİL metin olarak görünmeli."""
        sayfa = self._html()
        self.assertIn("&lt;i&gt;", sayfa)

    def test_satir_sonu_korunur(self):
        self.assertIn("<br>", self._html())

    def test_bulgu_kenarda_isaret_birakir(self):
        sayfa = self._html({"1": "MISSING_REPLICA — replik düştü"})
        self.assertIn("data-bulgu", sayfa)
        self.assertIn("MISSING_REPLICA", sayfa)

    def test_bulgusuz_sayfada_isaret_yok(self):
        """`data-bulgu` JS seçicisinde de geçiyor; SATIRDA aranmalı."""
        self.assertNotIn('data-bulgu="1"', self._html())
        self.assertIn('data-bulgu="1"', self._html({"1": "bir sebep"}))

    def test_dis_kaynak_yok(self):
        """Tek dosya: program açık olmadan, başka makinede de okunmalı."""
        sayfa = self._html()
        for yasak in ("http://", "https://", "<img", "<link"):
            self.assertNotIn(yasak, sayfa, yasak)

    def test_ayrik_numaralar_ikisi_de_yazilir(self):
        kaynak = [_cue(2, 1, "Hello.")]
        teslim = [_cue(9, 1, "Merhaba.")]
        sayfa = oy.html_uret("T", kaynak, teslim)
        self.assertIn("⇠2", sayfa)


class TeslimDenetimineBagliTest(unittest.TestCase):
    def test_denetim_okuma_yuzeyi_uretir(self):
        dizin = tempfile.mkdtemp()
        try:
            kaynak = os.path.join(dizin, "k.srt")
            teslim = os.path.join(dizin, "t.srt")
            with io.open(kaynak, "w", encoding="utf-8") as fh:
                fh.write("1" + NL + "00:00:01,000 --> 00:00:02,000" + NL
                         + "- Mrs Marler phoned." + NL + "- Call her back."
                         + NL + NL)
            with io.open(teslim, "w", encoding="utf-8") as fh:
                fh.write("1" + NL + "00:00:01,000 --> 00:00:02,000" + NL
                         + "- Bayan Marler aradı." + NL)
            audit = gui._subtitle_delivery_audit(kaynak, teslim)
            yol = audit.get("reading_surface_path")
            self.assertTrue(yol, audit.get("reading_surface_error"))
            self.assertTrue(os.path.exists(yol))
            self.assertEqual(os.path.basename(os.path.dirname(yol)),
                             "Raporlar")
            with io.open(yol, encoding="utf-8") as fh:
                sayfa = fh.read()
            self.assertIn("Mrs Marler phoned", sayfa)
            self.assertIn("Bayan Marler", sayfa)
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)

    def test_okunamayan_kaynak_teslimi_DURDURMAZ(self):
        """Okuma yüzeyi bir kolaylıktır, kalite kapısı değil."""
        dizin = tempfile.mkdtemp()
        try:
            teslim = os.path.join(dizin, "t.srt")
            with io.open(teslim, "w", encoding="utf-8") as fh:
                fh.write("1" + NL + "00:00:01,000 --> 00:00:02,000" + NL
                         + "Merhaba." + NL)
            audit = gui._subtitle_delivery_audit(
                os.path.join(dizin, "olmayan.srt"), teslim)
            # Kaynak okunamayınca denetim zaten erken döner; okuma yüzeyi
            # bunu bir istisnaya çevirmemeli.
            self.assertIsInstance(audit, dict)
            self.assertEqual(audit.get("status"), "unavailable")
            self.assertIn("error", audit)
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)

    def test_bulgu_sebepleri_kayitli_siniflardan_gelir(self):
        audit = {"missing_dialogue_ids": ["3"], "quote_chain_ids": ["7"]}
        bulgular = gui._reading_surface_findings(audit)
        self.assertIn("3", bulgular)
        self.assertIn("muhtemel", bulgular["3"])
        self.assertIn("7", bulgular)
        self.assertIn("bilgi", bulgular["7"])


if __name__ == "__main__":
    unittest.main()
