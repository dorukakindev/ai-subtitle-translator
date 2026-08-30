# -*- coding: utf-8 -*-
"""Kılavuz koddan SAPAMAZ.

Elle yazılan bir kullanım kılavuzu birkaç ay sonra yalan söyler: kutu
eklenir, varsayılan değişir, kılavuz eski kalır. Bu testler iki şeyi
kilitler:

  1. Arayüzdeki her aç/kapa kutusunun kılavuzda bir karşılığı VAR.
  2. Kılavuzun "varsayılan" iddiası koddaki gerçek varsayılana EŞİT.

Yeni bir kutu eklendiğinde bu testler kırılır — kılavuzsuz teslim
edilemez. Varsayılanı değiştirdiğinizde de kırılır; kılavuzu güncellemek
zorunda kalırsınız.
"""
import io
import os
import re
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)

import kilavuz

KAYNAK = os.path.join(KOK, "subtitle_translator_gui.py")


def _kod_varsayilanlari():
    """{var_adi: bool} — koddaki gerçek BooleanVar varsayılanları."""
    with io.open(KAYNAK, encoding="utf-8-sig") as fh:
        metin = fh.read()
    return {
        m.group(1): m.group(2) == "True"
        for m in re.finditer(
            r"self\.([a-z0-9_]+_var)\s*=\s*ctk\.BooleanVar\(value=(True|False)\)",
            metin)
    }


class KilavuzKapsamaTest(unittest.TestCase):
    def test_her_kutunun_kilavuz_maddesi_var(self):
        eksik = sorted(set(_kod_varsayilanlari()) - set(kilavuz.MADDELER))
        self.assertEqual(
            eksik, [],
            "kılavuzda karşılığı olmayan kutu(lar): %s" % ", ".join(eksik))

    def test_kilavuzda_olmayan_kutu_anlatilmamis(self):
        """Silinmiş bir kutu kılavuzda kalmasın.

        Kutusuz maddeler bunun dışında: hep açık davranışların
        kapatılacak bir seçeneği yok ama anlatılmaları gerekiyor.
        """
        fazla = sorted(set(kilavuz.kutulu_maddeler())
                       - set(_kod_varsayilanlari()))
        self.assertEqual(
            fazla, [],
            "kodda bulunmayan madde(ler): %s" % ", ".join(fazla))

    def test_kutusuz_madde_ACIKCA_isaretli(self):
        """Kutusuz olmak bir muafiyet; unutulup dagilmamali."""
        kutusuz = kilavuz.kutusuz_maddeler()
        self.assertTrue(kutusuz)
        for ad, madde in kutusuz.items():
            self.assertFalse(madde.arayuz_kutusu, ad)
            self.assertIsNone(
                madde.varsayilan,
                "%s kutusuz ama varsayilan degeri var" % ad)
            self.assertTrue(madde.uzun.strip(), ad)

    def test_kutulu_madde_sayisi_kutu_sayisiyla_ayni(self):
        self.assertEqual(
            len(kilavuz.kutulu_maddeler()), len(_kod_varsayilanlari()))

    def test_varsayilanlar_kodla_ayni(self):
        kod = _kod_varsayilanlari()
        sapan = []
        for ad, madde in kilavuz.MADDELER.items():
            if ad not in kod or madde.varsayilan is None:
                continue
            if madde.varsayilan != kod[ad]:
                sapan.append("%s: kılavuz=%s kod=%s"
                             % (ad, madde.varsayilan, kod[ad]))
        self.assertEqual(sapan, [], "; ".join(sapan))


class KilavuzIcerikTest(unittest.TestCase):
    def test_her_madde_dolu(self):
        for ad, madde in kilavuz.MADDELER.items():
            self.assertTrue(madde.baslik.strip(), ad)
            self.assertTrue(madde.kisa.strip(), ad)
            self.assertTrue(madde.uzun.strip(), ad)
            self.assertIn(madde.bolum, kilavuz.BOLUMLER, ad)

    def test_ipucu_tek_ekrana_sigar(self):
        """Tooltip kısa olmalı; uzun anlatım pencerede."""
        for ad, madde in kilavuz.MADDELER.items():
            self.assertLessEqual(
                len(madde.kisa), 160,
                "%s: ipucu çok uzun (%d)" % (ad, len(madde.kisa)))

    def test_iliskili_maddeler_gercek(self):
        for ad, madde in kilavuz.MADDELER.items():
            for baglanti in madde.iliskili:
                self.assertIn(
                    baglanti, kilavuz.MADDELER,
                    "%s -> %s: olmayan maddeye bağlantı" % (ad, baglanti))

    def test_ipucu_varsayilani_soyler(self):
        madde = kilavuz.MADDELER["critic_var"]
        self.assertIn("Varsayılan: açık", madde.ipucu())
        madde = kilavuz.MADDELER["polish_var"]
        self.assertIn("Varsayılan: kapalı", madde.ipucu())


class KilavuzAramaTest(unittest.TestCase):
    def test_baslikta_gecen_once_gelir(self):
        sonuc = kilavuz.ara("polish")
        self.assertTrue(sonuc)
        self.assertEqual(sonuc[0][0], "polish_var")

    def test_govdede_arar(self):
        adlar = [ad for ad, _m in kilavuz.ara("zaman damgalarına DOKUNMAZ")]
        self.assertIn("cue_fill_move_var", adlar)

    def test_bos_sorgu_bos_doner(self):
        self.assertEqual(kilavuz.ara(""), [])
        self.assertEqual(kilavuz.ara("   "), [])

    def test_bolume_gore_hepsini_kapsar(self):
        gruplar = kilavuz.bolume_gore()
        toplam = sum(len(v) for v in gruplar.values())
        self.assertEqual(toplam, len(kilavuz.MADDELER))


class UretilenBolumlerTest(unittest.TestCase):
    """İçerik türleri ve bulgu sınıfları ELLE yazılmaz, üretilir."""

    def test_bulgu_siniflari_gercek_kayittan_uretilir(self):
        import subtitle_translator_gui as g
        uretilen = kilavuz.bulgu_sinifi_maddeleri(g._FINDING_CLASSES)
        self.assertEqual(len(uretilen), len(g._FINDING_CLASSES))
        anahtarlar = {satir[0] for satir in uretilen}
        # bu oturumda eklenen sınıflar da kendiliğinden girmeli
        for yeni in ("translator_gloss_ids", "quote_chain_ids",
                     "partial_echo_ids"):
            self.assertIn(yeni, anahtarlar, yeni)

    def test_her_guven_derecesi_aciklanmis(self):
        import subtitle_translator_gui as g
        dereceler = {meta[0] for meta in g._FINDING_CLASSES.values()}
        for derece in dereceler:
            self.assertIn(derece, kilavuz.GUVEN_ACIKLAMASI, derece)

    def test_icerik_turleri_semadan_uretilir(self):
        import subtitle_translator_gui as g
        uretilen = kilavuz.icerik_turu_maddeleri(g.CONTENT_SCHEMAS)
        self.assertEqual(len(uretilen), len(g.CONTENT_SCHEMAS))


if __name__ == "__main__":
    unittest.main()
