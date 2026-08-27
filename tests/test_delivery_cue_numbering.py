# -*- coding: utf-8 -*-
"""Teslim dosyasının diskteki cue numaralandırması.

Arşivde 167 teslim dosyası `584 -> [1192] -> 585` şeklinde monoton olmayan
numarayla duruyordu ve teslim denetimi tek alarm üretmemişti: ham baytta
YİNELEME ve NUMARASIZ SATIR bakılıyor, SIRA bakılmıyordu.

Kusurun kaynağı program değil — koşudan hemen sonraki 47 dosya temizdi ve
bozuk dosyaların hiçbiri raporda kayıtlı `output_sha256` ile eşleşmiyordu.
Dosyalar yazıldıktan SONRA yeniden numaralanmış: gövde cue'ları 1..N'e
çekilmiş, imza cue'ları eski yüksek numaralarıyla kalmış. Program bunu
üretmediği için doğru çözüm engelleme değil TESPİT.

Ölçüm (2026-08-27): bilinen 123 bozuk dosyada %100 yakalama, onarılmış
542 gerçek teslimde 0 yanlış pozitif.
"""
import os
import tempfile
import unittest

import subtitle_translator_gui as gui

SIGN = "discord: ceviri2"


def _srt(cues):
    """cues: [(id, "metin"), ...] -> geçerli SRT metni."""
    parts = []
    for position, (cue_id, text) in enumerate(cues):
        start = 10 + position
        parts.append(
            "%s\n00:00:%02d,000 --> 00:00:%02d,500\n%s\n"
            % (cue_id, start, start, text))
    return "\n".join(parts)


class _Yazili:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".srt", encoding="utf-8", delete=False)
        handle.write(self.text)
        handle.close()
        self.path = handle.name
        return self.path

    def __exit__(self, *exc):
        try:
            os.unlink(self.path)
        except OSError:
            pass


class DeliveryCueNumberingTest(unittest.TestCase):
    def _tara(self, cues):
        with _Yazili(_srt(cues)) as path:
            return gui._srt_raw_cue_id_issues(path)

    def test_temiz_teslim_alarm_uretmez(self):
        _dup, _un, geri, imza = self._tara([
            (0, SIGN), (1, "Merhaba."), (2, "Nasılsın?"),
            (3, SIGN),
        ])
        self.assertEqual(geri, [])
        self.assertEqual(imza, [])

    def test_ortadaki_imza_bayat_numara_tasiyor(self):
        """Ölçülen asıl şekil: 369 -> [711] -> 371."""
        _dup, _un, geri, imza = self._tara([
            (0, SIGN), (368, "Bir."), (369, "İki."),
            (711, SIGN), (371, "Üç."),
        ])
        self.assertIn("711", imza)      # 370 olmalıydı
        self.assertIn("371", geri)      # 711'den sonra geri gidiyor

    def test_son_imza_ileri_sapmasi_da_yakalanir(self):
        """İleri sapma monotondur; genel kural görmez, imza kuralı görür."""
        _dup, _un, geri, imza = self._tara([
            (0, SIGN), (1, "Bir."), (2, "İki."), (9, SIGN),
        ])
        self.assertEqual(geri, [])
        self.assertIn("9", imza)

    def test_bas_imza_sifir_olmali(self):
        """Teslim bütünlük işareti baş imzanın 0 olmasına dayanır."""
        _dup, _un, _geri, imza = self._tara([
            (1, SIGN), (2, "Bir."), (3, "İki."),
        ])
        self.assertIn("1", imza)

    def test_normal_cue_boslugu_alarm_uretmez(self):
        """`_normalize_delivery_ids` normal cue'da boşluğu KORUR - gürültü yok."""
        _dup, _un, geri, imza = self._tara([
            (0, SIGN), (1, "Bir."), (2, "İki."), (7, "Yedi."),
        ])
        self.assertEqual(geri, [])
        self.assertEqual(imza, [])

    def test_imza_olmayan_kaynak_dosya_ellenmez(self):
        """Kaynak dosyada numara tutarsizligi kaynagin kendi ozelligi."""
        _dup, _un, _geri, imza = self._tara([
            (1, "Bir."), (2, "İki."), (9, "Dokuz."),
        ])
        self.assertEqual(imza, [])

    def test_okunamayan_dosya_dort_liste_dondurur(self):
        self.assertEqual(
            gui._srt_raw_cue_id_issues("yok-boyle-bir-dosya.srt"),
            ([], [], [], []))

    def test_bulgu_siniflari_kayitli(self):
        for key in ("non_monotonic_cue_ids", "signature_cue_id_ids"):
            with self.subTest(key=key):
                self.assertIn(key, gui._FINDING_CLASSES)
                self.assertEqual(gui._FINDING_CLASSES[key][0], "kesin")

    def test_sert_hata_kapisina_bagli(self):
        for key in ("non_monotonic_cue_ids", "signature_cue_id_ids"):
            with self.subTest(key=key):
                self.assertTrue(
                    gui._delivery_audit_has_hard_error({key: ["5"]}))
        self.assertFalse(gui._delivery_audit_has_hard_error(
            {"non_monotonic_cue_ids": [], "signature_cue_id_ids": []}))


if __name__ == "__main__":
    unittest.main()
