# -*- coding: utf-8 -*-
"""Sonrası kipi: 35 kutuyu tek kararla ayarla.

Kullanıcı düzeltmeyi programa değil, sonradan okuyan bir LLM'e (Codex /
Claude) yaptırıyor. O zaman programın metni kendi yeniden yazması hem
gereksiz hem riskli — otomatik düzeltmenin yanlış-alarm oranı bu projede
defalarca ölçüldü ve yüksek çıktı.

Kullanıcı bu düzeni 34 kutuyu elle ayarlayarak zaten bulmuştu; bu kip
aynı düzeni tek tıkla ve nedeni yazılı hâle getiriyor.
"""
import unittest

import subtitle_translator_gui as gui

from tests._gui_app import make_app


class AfterRunModeTest(unittest.TestCase):
    def setUp(self):
        self.app = make_app(gui)
        self.app._log = lambda text, level="info": None
        self.app._save_settings = lambda *a, **k: None

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def _values(self, names):
        return {name: bool(getattr(self.app, name).get())
                for name in names if hasattr(self.app, name)}

    def test_every_listed_toggle_exists(self):
        # Liste ile arayüz ayrışırsa kip sessizce yarım çalışır.
        for name in (gui.App._TEXT_REWRITING_TOGGLES
                     + gui.App._LLM_MODE_REQUIRED_ON):
            with self.subTest(name=name):
                self.assertTrue(hasattr(self.app, name), name)

    def test_llm_mode_turns_off_every_rewriting_pass(self):
        gui.App._apply_after_run_mode(self.app, "llm")
        values = self._values(gui.App._TEXT_REWRITING_TOGGLES)
        self.assertTrue(values)
        self.assertFalse(any(values.values()), values)

    def test_llm_mode_keeps_report_and_backup_on(self):
        # Ham yedek şart: ham↔teslim içerik koruma kontrolü ona dayanıyor.
        for name in gui.App._LLM_MODE_REQUIRED_ON:
            getattr(self.app, name).set(False)
        gui.App._apply_after_run_mode(self.app, "llm")
        values = self._values(gui.App._LLM_MODE_REQUIRED_ON)
        self.assertTrue(all(values.values()), values)

    def test_direct_mode_turns_them_back_on(self):
        gui.App._apply_after_run_mode(self.app, "llm")
        gui.App._apply_after_run_mode(self.app, "dogrudan")
        values = self._values(gui.App._TEXT_REWRITING_TOGGLES)
        self.assertTrue(all(values.values()), values)

    def test_mode_does_not_touch_flow_toggles(self):
        # Kip yalnız YENİDEN YAZMAYI kapatır; batch stratejisi, çıktı yeri,
        # bildirim gibi kutulara karışmaz.
        untouched = ("twowave_var", "same_folder_var", "notify_var",
                     "hybrid_var", "chain_ctx_var", "clean_sdh_var")
        before = self._values(untouched)
        gui.App._apply_after_run_mode(self.app, "llm")
        self.assertEqual(before, self._values(untouched))

    def test_applying_twice_reports_no_change(self):
        gui.App._apply_after_run_mode(self.app, "llm")
        second = gui.App._apply_after_run_mode(self.app, "llm")
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
