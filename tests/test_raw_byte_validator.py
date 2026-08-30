# -*- coding: utf-8 -*-
"""Teslim dosyasının HAM BAYTTAN doğrulanması.

Neden ayrıştırıcıdan değil bayttan: `parse_subtitle` cue kimliklerini
1'den yeniden üretir ve gerçek bir bozukluğu SİLER. Diskteki yapı iddiası
ancak baytla ölçülür — bu, iki oturumda üç yanlış ölçüme mal olmuştu.

HANGİ KONTROLLER — 372 gerçek teslimde ölçülerek seçildi:
    BOM                    39 dosya   → eklendi
    karışık satır sonu      4 dosya   → eklendi
    ayraç bütünlüğü         0 vaka    → EKLENMEDİ
    gömülü cue başlığı      0 vaka    → EKLENMEDİ
    etiket dengesizliği     0 vaka    → EKLENMEDİ

Son üçü hiç ateşlenmedi. Olmayan soruna guard yazmak bu depoda kural dışı;
kayıt burada dursun ki bir sonraki tur onları yeniden önermesin.

PROGRAM BUNLARI ÜRETMİYOR — bayt düzeyinde doğrulandı. Kontrolün işi
teslimden SONRA dosyaya dokunan dış araçları görünür kılmak.
"""
import io
import os
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import subtitle_translator_gui as gui

TEMIZ = b"1\r\n00:00:01,000 --> 00:00:02,000\r\nMerhaba\r\n\r\n"


class RawByteValidatorTest(unittest.TestCase):
    def setUp(self):
        self.dizin = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dizin, ignore_errors=True)

    def _yaz(self, icerik, ad="t.srt"):
        yol = os.path.join(self.dizin, ad)
        with io.open(yol, "wb") as fh:
            fh.write(icerik)
        return yol

    def test_temiz_dosya_bulgusuz(self):
        sonuc = gui._srt_raw_byte_issues(self._yaz(TEMIZ))
        self.assertEqual(sonuc, {"bom": False, "mixed_newline": False,
                                 "not_utf8": False})

    def test_bom_yakalanir(self):
        sonuc = gui._srt_raw_byte_issues(self._yaz(b"\xef\xbb\xbf" + TEMIZ))
        self.assertTrue(sonuc["bom"])
        self.assertFalse(sonuc["not_utf8"])

    def test_karisik_satir_sonu_yakalanir(self):
        karisik = b"1\r\n00:00:01,000 --> 00:00:02,000\r\nMerhaba\n\r\n"
        self.assertTrue(
            gui._srt_raw_byte_issues(self._yaz(karisik))["mixed_newline"])

    def test_tutarli_LF_karisik_sayilmaz(self):
        """Baştan sona LF olan dosya karışık DEĞİLDİR."""
        lf = TEMIZ.replace(b"\r\n", b"\n")
        self.assertFalse(
            gui._srt_raw_byte_issues(self._yaz(lf))["mixed_newline"])

    def test_utf8_olmayan_yakalanir(self):
        sonuc = gui._srt_raw_byte_issues(self._yaz(b"\xff\xfe\x00bozuk"))
        self.assertTrue(sonuc["not_utf8"])

    def test_bos_ve_olmayan_dosya_patlamaz(self):
        self.assertFalse(any(gui._srt_raw_byte_issues(self._yaz(b"")).values()))
        yok = os.path.join(self.dizin, "olmayan.srt")
        self.assertFalse(any(gui._srt_raw_byte_issues(yok).values()))


class WriterProducesCleanBytesTest(unittest.TestCase):
    """Programın KENDİ çıktısı bu kontrollerin hiçbirini tetiklememeli.

    Bu testin asıl işi kaynağı ayırmak: teslimde BOM görülürse suçlu
    yazıcı değil, dosyaya sonradan dokunan bir araçtır.
    """

    def test_write_srt_bomsuz_ve_tutarli_yazar(self):
        dizin = tempfile.mkdtemp()
        try:
            yol = os.path.join(dizin, "cikti.srt")
            gui.write_srt(yol, [
                ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba dünya"),
                ("2", "00:00:03,000 --> 00:00:04,000", "İkinci satır"),
            ])
            sonuc = gui._srt_raw_byte_issues(yol)
            self.assertEqual(
                sonuc, {"bom": False, "mixed_newline": False,
                        "not_utf8": False},
                "yazıcı kirli bayt üretiyor: %s" % sonuc)
        finally:
            import shutil
            shutil.rmtree(dizin, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
