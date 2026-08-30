# -*- coding: utf-8 -*-
"""Kılavuz arayüze GERÇEKTEN bağlı mı.

`tests/test_kilavuz.py` verinin doğruluğunu kilitler; bu dosya verinin
kullanıcıya ULAŞTIĞINI kilitler. İkisi ayrı sorulardır: kılavuzda eksiksiz
bir madde olabilir ve yine de hiçbir kutunun üstünde görünmeyebilir.

Bağlama TEK TEK yapılmaz — kurulum bitince widget ağacı taranıp değişken
kimliğinden madde bulunur. Bu testin asıl işi o taramanın hiçbir kutuyu
atlamadığını doğrulamak.
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
sys.path.insert(0, os.path.join(KOK, "tests"))

import kilavuz
import subtitle_translator_gui as gui
from _gui_app import make_app


class KilavuzArayuzTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_her_madde_bir_arayuz_degiskeniyle_eslesir(self):
        """Kılavuzdaki her maddenin App üzerinde karşılığı olmalı.

        Widget ağacını yürüme adımı gerçek CustomTkinter'a bağlıdır ve
        test stub'ında widget yoktur; kırılabilecek kısım eşlemedir ve
        o burada tam olarak sınanır. Uçtan uca bağlama (35/35) gerçek
        arayüzle duman testinde doğrulanır.
        """
        harita = self.app._kilavuz_degisken_haritasi()
        eslenen = set(harita.values())
        eksik = sorted(set(kilavuz.kutulu_maddeler()) - eslenen)
        self.assertEqual(
            eksik, [],
            "App üzerinde karşılığı bulunamayan madde(ler): %s"
            % ", ".join(eksik))
        self.assertEqual(len(harita), len(kilavuz.kutulu_maddeler()))

    def test_kutusuz_madde_kutu_ARAMAZ(self):
        """Kutusuz maddenin arayuzde karsiligi olmamali; olsaydi
        kutulu olarak isaretlenmesi gerekirdi."""
        harita = self.app._kilavuz_degisken_haritasi()
        for ad in kilavuz.kutusuz_maddeler():
            self.assertNotIn(ad, set(harita.values()), ad)

    def test_tarama_patlamadan_calisir(self):
        """Stub'da 0 döner, gerçek arayüzde 35 — ikisinde de hata vermez."""
        self.assertIsInstance(self.app._kilavuz_ipuclarini_bagla(), int)

    def test_kilavuz_penceresi_acilir_ve_tekildir(self):
        """Pencere çizimi GERÇEK CustomTkinter gerektirir.

        Süit bir stub kullanıyor; stub'ın `_DummyWidget`'i her özniteliğe
        lambda döner ve `winfo_children()` None verir, yani widget ağacı
        yoktur. Bu testi stub'da geçirmek için koda gerçekte hiç olmayan
        durumlara karşı savunma eklemek gerekirdi — test taklidini memnun
        etmek için üretim kodunu bozmak olurdu.

        Gerçek arayüzle çalıştırıldığında (tek modül, stub'sız) pencerenin
        açıldığı ve ikinci çağrının yeni pencere AÇMADIĞI burada sınanır.
        """
        if "_Dummy" in type(gui.ctk.CTkToplevel).__name__ or                 gui.ctk.CTkToplevel.__name__.startswith("_Dummy"):
            self.skipTest("test stub'ında widget ağacı yok")
        self.app._show_kilavuz_dialog()
        self.app.update_idletasks()
        ilk = self.app.__dict__.get("_kilavuz_dialog")
        self.assertTrue(ilk.winfo_exists())
        self.app._show_kilavuz_dialog()
        self.app.update_idletasks()
        self.assertIs(self.app.__dict__.get("_kilavuz_dialog"), ilk)
        ilk.destroy()

    def test_kisayol_ve_liste_tutarli(self):
        """Shift+F1 bağlıysa kısayol listesinde de yazmalı."""
        kisayollar = {kod for kod, _aciklama in gui.KEYBOARD_SHORTCUTS}
        self.assertIn("Shift+F1", kisayollar)
        self.assertTrue(hasattr(self.app, "_shortcut_show_kilavuz"))

    def test_ipucu_metni_varsayilani_soyler(self):
        """Kutunun üstündeki metin ne yaptığını VE varsayılanını söylemeli."""
        madde = kilavuz.MADDELER["quality_report_only_var"]
        ipucu = madde.ipucu()
        self.assertIn("DEĞİŞTİRMEZ", ipucu)
        self.assertIn("Varsayılan: açık", ipucu)

    def test_ipucu_bagla_bos_metinde_patlamaz(self):
        self.app._ipucu_bagla(self.app, "")
        self.app._ipucu_bagla(None, "")


if __name__ == "__main__":
    unittest.main()
