"""
Aktif batch muhasebesi testleri — _register_batch / _unregister_batch / _cancel_active_batches.
Gerçek GUI/ağ kurulmadan App örneği headless açılır; cancel ağ çağrısı yapılmadan
(boş sözlük) sadece muhasebe doğrulanır.
"""
import unittest

import subtitle_translator_gui as gui
from tests._gui_app import make_app


class BatchAccountingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def setUp(self):
        with self.app._batch_lock:
            self.app._active_batches.clear()

    def test_register_and_unregister(self):
        self.app._register_batch("batch_a", "sk-1")
        self.app._register_batch("batch_b", "sk-2")
        self.assertEqual(set(self.app._active_batches), {"batch_a", "batch_b"})
        self.app._unregister_batch("batch_a")
        self.assertEqual(set(self.app._active_batches), {"batch_b"})

    def test_register_empty_id_ignored(self):
        self.app._register_batch("", "sk-1")
        self.app._register_batch(None, "sk-1")
        self.assertEqual(len(self.app._active_batches), 0)

    def test_unregister_missing_is_safe(self):
        self.app._unregister_batch("yok")  # patlamamalı
        self.assertEqual(len(self.app._active_batches), 0)

    def test_cancel_empty_does_nothing(self):
        # Boş listede cancel ağ çağrısı yapmaz, sözlüğü temiz bırakır
        self.app._cancel_active_batches()
        self.assertEqual(len(self.app._active_batches), 0)

    def test_cancel_clears_dict_even_if_api_fails(self):
        # Geçersiz key → batches.cancel hata verir ama sözlük yine temizlenmeli
        self.app._register_batch("batch_x", "sk-invalid-key-xxxxx")
        self.app._cancel_active_batches()
        self.assertEqual(len(self.app._active_batches), 0)


if __name__ == "__main__":
    unittest.main()
