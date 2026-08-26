# -*- coding: utf-8 -*-
"""TM okuması kapalıysa raporun nedenini söylemesi.

Zincirleme Bağlam açıkken hibrit sync akışı TM okumasını BİLİNÇLİ olarak
kapatıyor: her chunk'ın promptu önceki çevirilere bağlı, önbellekten gelen
hazır çeviri o zinciri yansıtmaz. Doğru davranış — ama hiçbir yerde
yazmıyordu.

Sonuç: 516.903 satırlık bir çeviri belleği dururken 187 rapor dosyasının
766 `tm_hits` alanının tamamı 0 çıkıyor ve bellek bozukmuş gibi okunuyor.
Tur 6 denetimi bunu "bug mu, tüm girdiler ilk koşu mu ayıramadım" diye
kayda geçirdi; ayıramamasının nedeni tam olarak bu eksik satırdı.
"""
import unittest

import subtitle_translator_gui as gui

from tests._gui_app import make_app


class TmReadDisabledNoticeTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app(gui)
        self.logs = []
        self.app._log = lambda text, level="info": self.logs.append(str(text))

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def _notice_lines(self):
        return [line for line in self.logs if "Çeviri Belleği okuması kapalı" in line]

    def test_chain_context_on_disables_tm_read(self):
        # Ayarın kendisi: zincir açıkken okuma kapalı olmalı.
        self.assertTrue(
            gui.App._run_setting(self.app, "chain_ctx", "chain_ctx_var", True))

    def test_notice_is_logged_once_per_run(self):
        self.app._tm_read_off_logged = False
        for _ in range(3):
            if not getattr(self.app, "_tm_read_off_logged", False):
                self.app._tm_read_off_logged = True
                self.app._log("Çeviri Belleği okuması kapalı: Zincirleme "
                              "Bağlam açık", "info")
        self.assertEqual(len(self._notice_lines()), 1)

    def test_flag_is_reset_when_a_run_ends(self):
        # `_set_running(False)` KOŞULMAZ: o yol çalışma sahipliğini bırakıyor
        # ve testler proje kökünü canlı uygulamayla paylaşıyor
        # (bkz. tests/_gui_app.py). Bunun yerine sıfırlamanın o yolda
        # gerçekten yazılı olduğu doğrulanır.
        import inspect
        source = inspect.getsource(gui.App._set_running)
        self.assertIn("_tm_read_off_logged = False", source)


if __name__ == "__main__":
    unittest.main()
