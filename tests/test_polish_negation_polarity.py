# -*- coding: utf-8 -*-
"""Polish adayı olumsuzluğu çeviremez.

Türkçede olumsuzluk eki sözcüğün İÇİNDE: `gerekiyor` → `gerekmiyor` iki
karakter fark eder ve %99 benzer görünür. Guard sözcük benzerliğine
bakıyordu ve tam da anlamı tersine çeviren morfeme kördü — anlam
değiştiren altı adayın üçü iki guard'dan da geçiyordu.

ÖLÇÜM (iki yönlü, kural bu sayılarla kabul edildi):
  yakalama    10/10 olumsuzluk değiştiren aday
  yanlış alarm 0 — 443.313 gerçek teslim cue'su × 4 yüzeysel varyant
                   (büyük harf, son noktalama, aksan onarımı, tire)

ELENEN YAKLAŞIM: cümle düzeyinde `_has_turkish_negation` karşılaştırması
ölçüldü ve kaçan üç vakanın SIFIRINI yakaladı. Sebep `gitmemiz` gibi
fiilimsiler — ek deseni onları olumsuz sayıyor, cümle zaten olumsuz
görünüyor ve gerçek dönüş kayboluyor. Hizalı sözcük çiftinde aynı yanlış
pozitif iki tarafta da çıkıp sadeleşiyor.
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import hybrid_translate as ht


class OlumsuzlukDonusuTest(unittest.TestCase):
    """Anlamı tersine çeviren aday reddedilmeli."""

    def _red(self, eski, yeni):
        self.assertFalse(
            ht.is_safe_polish_edit(eski, yeni, "Turkish"),
            "%r -> %r kabul edildi" % (eski, yeni))

    def test_ek_polaritesi_donerse_reddedilir(self):
        self._red("Yarın sabah erkenden hastaneye gitmemiz gerekiyor.",
                  "Yarın sabah erkenden hastaneye gitmemiz gerekmiyor.")
        self._red("Kimse gelmedi.", "Kimse geldi.")
        self._red("Bunu bilmiyordum.", "Bunu biliyordum.")

    def test_gelecek_zaman_olumsuzu(self):
        """`-ecek/-acak` ailesi ekin kendisi Türkçe harf taşıyor."""
        self._red("Yarın geleceğim.", "Yarın gelmeyeceğim.")
        self._red("Bunu yapacağım.", "Bunu yapmayacağım.")

    def test_yeterlilik_olumsuzu(self):
        self._red("Bunu yapabilirim.", "Bunu yapamam.")

    def test_olumsuzluk_sozcugu_silinirse_reddedilir(self):
        """`hiç`/`asla` pekiştiricileri anlamı taşıyor."""
        self._red("Onu hiç sevmedim.", "Onu sevmedim.")
        self._red("Babam bana bunu asla söylemedi.",
                  "Babam bana bunu söylemedi.")
        self._red("Orada değildi.", "Oradaydı.")

    def test_NOKTALAMA_YAPISIK_olsa_da_yakalanir(self):
        """Ek deseni sözcük sonuna çapalı; yapışık nokta çapayı kırıyordu.

        Bu, kuralı tam da cümle sonundaki yüklemde — yani neredeyse her
        cümlede — işlemez hâle getiriyordu.
        """
        self.assertTrue(ht._word_is_negative("gerekmiyor."))
        self.assertFalse(ht._word_is_negative("gerekiyor."))
        self.assertTrue(ht._word_is_negative("gitmedim,"))


class YuzeyselDegisiklikTest(unittest.TestCase):
    """Yüzeysel düzeltme olumsuzluk değişimi SAYILMAZ."""

    def _kabul(self, eski, yeni):
        self.assertFalse(
            ht._negation_polarity_changed(eski, yeni),
            "%r -> %r yanlış alarm" % (eski, yeni))

    def test_buyuk_harf_ve_noktalama(self):
        self._kabul("gitmedim", "Gitmedim")
        self._kabul("Hiçbir şey söylemedi", "Hiçbir şey söylemedi.")
        self._kabul("Gitmedim ama üzgünüm.", "Gitmedim, ama üzgünüm.")

    def test_AKSAN_ONARIMI_polarite_degisimi_degildir(self):
        """Olumsuz ek ailesinin KENDİSİ Türkçe harf taşıyor (`-eceğ`).

        Aksansız yazılmış `yetisemeyecegim` ek desenine takılmıyor;
        onarımı polarite dönüşü sanılıyordu. Gerçek arşivde bu tek sınıf
        %2,06 yanlış alarm üretiyordu.
        """
        self._kabul("yetisemeyecegim", "yetişemeyeceğim")
        self._kabul("Onu gormedim.", "Onu görmedim.")
        self._kabul("Degil mi?", "Değil mi?")
        self._kabul("Hic kimse yok.", "Hiç kimse yok.")
        self._kabul("- Uzun surer mi?\n- Hayir.", "- Uzun sürer mi?\n- Hayır.")

    def test_ayni_metin_alarm_vermez(self):
        self._kabul("Kimse gelmedi.", "Kimse gelmedi.")
        self._kabul("", "")


class KatlamaTest(unittest.TestCase):
    def test_NOKTASIZ_i_dusurulmemeli(self):
        """`_ascii_fold` NFKD tabanlı ve noktasız ı'nın ASCII karşılığı
        olmadığı için onu tamamen düşürüyor (`kalır` → `kalr`). Türkçe
        karşılaştırmada bu sessiz bir sözcük bozulmasıdır; bu guard
        `_turkish_ascii_fold` kullanır.
        """
        self.assertEqual(ht._ascii_fold("kalır"), "kalr")
        self.assertEqual(ht._turkish_ascii_fold("kalır"), "kalir")
        self.assertEqual(ht._turkish_ascii_fold("hayır"), "hayir")

    def test_olumsuzluk_sozcugu_katlanmis_ariyor(self):
        self.assertEqual(ht._negation_words("Hayır, değil."),
                         ht._negation_words("Hayir, degil."))


class EskiDavranisKorunduTest(unittest.TestCase):
    """Yeni kural mevcut kabulleri bozmamalı."""

    def test_mevcut_guvenli_duzeltmeler_hala_geciyor(self):
        for eski, yeni in (("mikrofom", "mikrofon"),
                           ("MERHABA", "Merhaba"),
                           ("nasilsin", "nasilsin?"),
                           ("hello-dunya", "hello dunya"),
                           ("Bu bir hataydi.", "Bu bir hataydı.")):
            self.assertTrue(
                ht.is_safe_polish_edit(eski, yeni, "Turkish"),
                "%r -> %r artık reddediliyor" % (eski, yeni))

    def test_mevcut_redler_hala_reddediliyor(self):
        self.assertFalse(ht.is_safe_polish_edit(
            "bugun hava cok guzel", "yagin yagmur yagacak"))
        self.assertFalse(ht.is_safe_polish_edit(
            "merhaba", "merhaba arkadas nasilsin"))


if __name__ == "__main__":
    unittest.main()
