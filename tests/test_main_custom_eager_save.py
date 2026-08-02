"""Ana Model — Özel Sağlayıcı alanları ANINDA kaydedilir (FocusOut / switch değişimi).

NEDEN (2026-07-18): kullanıcı switch'i açıp Model Adı/API URL/API Anahtarı'nı
doldurduktan sonra çeviri hiç BAŞLATMADAN veya uygulamayı düzgün KAPATMADAN ekranı
değiştirebilir — bu iki nokta (_start/_on_close) diğer TÜM ayarların kaydedildiği
YEGÂNE yerlerdi. "api url'yi de hatırlasın" geri bildirimi üzerine bu 3 alan için
kasıtlı bir istisna eklendi: switch tıklanınca VE alandan çıkınca da kaydeder."""
import json
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tests._gui_app import make_app
import subtitle_translator_gui as gui


class MainCustomCredentialSaveTest(unittest.TestCase):
    def test_ui_only_setting_saves_do_not_touch_credential_store(self):
        main_source = inspect.getsource(gui.App._build_main)
        advanced_source = inspect.getsource(gui.App._show_advanced_settings)
        self.assertIn(
            "self._save_settings(save_credentials=False)",
            main_source[main_source.index("def _grip_release"):],
        )
        self.assertIn(
            "self._save_settings(save_credentials=False)",
            advanced_source[advanced_source.index("def _save"):],
        )

    def test_focus_out_queues_only_custom_key_without_blocking_ui(self):
        queued = []
        app = SimpleNamespace(
            main_custom_key_entry=SimpleNamespace(
                get=lambda: "sk-HloolAPI-test"),
            _save_settings=mock.Mock(),
            _start_worker=lambda target: queued.append(target),
            _log=mock.Mock(),
        )

        with mock.patch.object(gui.credential_store, "save_key") as mock_save:
            gui.App._on_main_custom_key_focus_out(app)
            mock_save.assert_not_called()
            app._save_settings.assert_called_once_with(save_credentials=False)
            self.assertEqual(len(queued), 1)
            queued[0]()

        mock_save.assert_called_once_with("main_custom", "sk-HloolAPI-test")

    def test_newer_focus_out_supersedes_queued_stale_key(self):
        queued = []
        entry = SimpleNamespace(value="old")
        entry.get = lambda: entry.value
        app = SimpleNamespace(
            main_custom_key_entry=entry,
            _save_settings=mock.Mock(),
            _start_worker=lambda target: queued.append(target),
            _log=mock.Mock(),
        )
        gui.App._on_main_custom_key_focus_out(app)
        entry.value = "new"
        gui.App._on_main_custom_key_focus_out(app)

        with mock.patch.object(
                gui.credential_store, "save_key", return_value=True) as mock_save:
            queued[0]()
            queued[1]()

        mock_save.assert_called_once_with("main_custom", "new")


class MainCustomEagerSaveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Bu testler GERÇEK Tk odak-olayı/grid görünürlük davranışını doğrular —
        # `discover -s tests` çalışırken tests/customtkinter.py (saf-mantık testleri
        # için hafif stub) sys.path'te GERÇEK paketin ÖNÜNE geçip onu gölgeler; stub
        # altında bu davranışlar anlamsız (widget'lar `_DummyWidget`, `.grid_info()`
        # her zaman None döner). `find_spec("customtkinter") is None` KONTROLÜ BURADA
        # İŞE YARAMAZ (stub da geçerli bir spec döner) — doğrudan stub'a özgü bir
        # işaretçi ara.
        if hasattr(gui.ctk, "_DummyWidget"):
            raise unittest.SkipTest(
                "tests/customtkinter.py stub'ı devrede (discover -s tests) — "
                "gerçek Tk odak/görünürlük davranışı test edilemez, atlandı")
        cls.app = make_app(gui)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._settings_path = Path(self._td.name) / ".gui_settings.json"
        self._orig_settings_path = self.app._settings_path
        self.app._settings_path = lambda: self._settings_path
        # Testler arasında sızmasın diye baştan sıfırla
        self.app.main_custom_var.set(False)
        self.app.main_custom_model_var.set("gpt-5.5")
        self.app.main_custom_url_var.set("")
        self.app.main_custom_key_entry.delete(0, "end")

    def tearDown(self):
        self.app._settings_path = self._orig_settings_path
        self._td.cleanup()

    def _read_saved(self):
        return json.loads(self._settings_path.read_text(encoding="utf-8"))

    def test_toggling_switch_saves_immediately(self):
        self.assertFalse(self._settings_path.exists())
        self.app.main_custom_var.set(True)
        self.app._on_main_custom_changed()
        saved = self._read_saved()
        self.assertTrue(saved["main_custom"])

    def test_focus_out_on_url_entry_saves(self):
        # Alan yalnızca switch AÇIKKEN görünür/odaklanabilir — gerçek kullanım sırası.
        self.app.main_custom_var.set(True)
        self.app._sync_main_custom_visibility()
        self.app.update_idletasks()
        self.app.main_custom_url_var.set("https://api.shuaiapi.com/v1")
        self.app.update_idletasks()
        # CTkEntry kompozit — gerçek olay iç ._entry (ham tkinter.Entry) üzerinde
        # işlenir, dıştaki CTkEntry nesnesinde DEĞİL (bkz. üretim kodundaki not).
        self.app.main_custom_url_entry._entry.event_generate("<FocusOut>")
        self.app.update_idletasks()
        saved = self._read_saved()
        self.assertEqual(saved["main_custom_url"], "https://api.shuaiapi.com/v1")

    def test_focus_out_on_key_entry_saves(self):
        # Özel anahtar settings JSON'a DEĞİL, credential_store'a AYRI bir rol altında
        # ("main_custom") gider — gerçek "openai" slotu (varsa) YALNIZCA KENDİ o anki
        # değeriyle kaydedilir, özel anahtarla ASLA karışmaz/ezilmez.
        self.app.main_custom_var.set(True)
        self.app._sync_main_custom_visibility()
        self.app.update_idletasks()
        real_key_before = self.app.api_key_entry.get()
        self.app.main_custom_key_entry.insert(0, "sk-HloolAPI-test")
        self.app.update_idletasks()
        with mock.patch.object(gui.credential_store, "save_key", return_value=True) as mock_save:
            self.app.main_custom_key_entry._entry.event_generate("<FocusOut>")
            self.app.update_idletasks()
        calls = {c.args[:2] for c in mock_save.call_args_list}
        self.assertIn(("main_custom", "sk-HloolAPI-test"), calls)
        openai_calls = [c.args[1] for c in mock_save.call_args_list if c.args[0] == "openai"]
        for saved_openai_value in openai_calls:
            self.assertEqual(saved_openai_value, real_key_before,
                             "gerçek 'openai' anahtarı özel anahtarla EZİLMEMELİ")
            self.assertNotEqual(saved_openai_value, "sk-HloolAPI-test")

    def test_switch_visibility_still_syncs_on_toggle(self):
        self.app.main_custom_var.set(True)
        self.app._on_main_custom_changed()
        self.assertTrue(self.app.main_custom_frame.grid_info())
        self.app.main_custom_var.set(False)
        self.app._on_main_custom_changed()
        self.assertEqual(self.app.main_custom_frame.grid_info(), {})


class MainCustomDisablesBatchTest(unittest.TestCase):
    """Özel Sağlayıcı açıkken Batch modu seçilemez (2026-07-20): gerçek OpenAI
    Batch API'si resmi OpenAI dışında desteklenmiyor — kullanıcı yanlışlıkla
    batch+reseller kombinasyonuyla çeviri başlattı, aslında hiç batch
    çalışmamıştı (mode_var açılış logunda sadece eski kayıtlı ayarı gösteriyordu,
    gerçek çalışma zamanı sync+hybrid'e geçmişti)."""

    @classmethod
    def setUpClass(cls):
        if hasattr(gui.ctk, "_DummyWidget"):
            raise unittest.SkipTest(
                "tests/customtkinter.py stub'ı devrede — gerçek radio-button "
                "state/grid davranışı test edilemez, atlandı")
        cls.app = make_app(gui)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        self.app.main_custom_var.set(False)
        self.app.mode_var.set("batch")
        self.app._sync_main_custom_visibility()

    def test_enabling_custom_provider_while_batch_forces_sync_and_disables_batch(self):
        self.app.mode_var.set("batch")
        self.app.main_custom_var.set(True)
        self.app._sync_main_custom_visibility()
        self.assertEqual(self.app.mode_var.get(), "sync")
        self.assertEqual(self.app._mode_batch_radio.cget("state"), "disabled")

    def test_disabling_custom_provider_reenables_batch_radio(self):
        self.app.main_custom_var.set(True)
        self.app._sync_main_custom_visibility()
        self.app.main_custom_var.set(False)
        self.app._sync_main_custom_visibility()
        self.assertEqual(self.app._mode_batch_radio.cget("state"), "normal")

    def test_custom_provider_active_with_sync_already_selected_does_not_touch_mode(self):
        self.app.mode_var.set("sync")
        self.app.main_custom_var.set(True)
        self.app._sync_main_custom_visibility()
        self.assertEqual(self.app.mode_var.get(), "sync")
        self.assertEqual(self.app._mode_batch_radio.cget("state"), "disabled")

    def test_fresh_defaults_point_at_reseller_gpt54(self):
        # Yeni kurulumda (ayar dosyası yokken) Özel Sağlayıcı alanları boş/gpt-5.5
        # yerine doğrudan çalışan reseller ayarlarını göstermeli (2026-07-20:
        # kullanıcı yeniden açınca URL alanının boşaldığını fark etti — asıl
        # neden URL'nin hiç kalıcı bir varsayılanı olmamasıydı). Gerçek proje
        # .gui_settings.json'ı bu App örneğine karışmasın diye var-olmayan bir
        # yola yönlendiriyoruz (make_app tek başına bunu izole etmez).
        with tempfile.TemporaryDirectory() as td:
            fake_path = Path(td) / ".gui_settings.json"
            with mock.patch.object(gui.App, "_settings_path", lambda self: fake_path):
                fresh = make_app(gui)
                try:
                    fresh.update_idletasks()
                    self.assertEqual(fresh.main_custom_model_var.get(), "gpt-5.4")
                    self.assertEqual(fresh.main_custom_url_var.get(), "https://api.shuaiapi.com/v1")
                finally:
                    fresh.destroy()


if __name__ == "__main__":
    unittest.main()
