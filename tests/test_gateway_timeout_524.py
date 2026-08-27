# -*- coding: utf-8 -*-
"""HTTP 524 dört yeniden-deneme yolunda da aynı sınıflandırmayı alsın.

524 = Cloudflare origin timeout. Kullanılan ağ geçidinde gerçekten oluyor
(koşu logu `run_20260827-071256`: tek bir analiz çağrısında 3 dk 45 sn
kayıp, HTTP 524 ve ardından rota geçişi). Ama dört kümenin yalnız birinde
vardı:

    provider_retry `_is_transient_provider_error`   ✅
    provider_retry `_provider_error_context`        ❌  (neden etiketi)
    provider_retry `record_transient_failure`       ❌  (devre kesici)
    gui `_is_transient_retry_error`                 ❌

Neden etiketi 500/502 ile aynı kümede değil: 524 bir sunucu hatası değil,
zaman aşımıdır — yeri 408'in yanı.
"""
import unittest

import provider_retry as pr
import subtitle_translator_gui as gui


class _Status(Exception):
    """Gövde metninde 'timeout' GEÇMEYEN hata — yalnız durum kodu ölçülsün."""

    def __init__(self, status):
        super().__init__("upstream returned %s" % status)
        self.status_code = status


class GatewayTimeout524Test(unittest.TestCase):
    def test_classified_as_timeout_not_server_error(self):
        context = pr._provider_error_context(_Status(524))
        self.assertEqual(context.get("reason"),
                         pr._provider_error_context(_Status(408)).get("reason"))
        self.assertNotEqual(
            context.get("reason"),
            pr._provider_error_context(_Status(500)).get("reason"))

    def test_retryable_in_both_predicates(self):
        self.assertTrue(pr._is_transient_provider_error(_Status(524)))
        self.assertTrue(gui._is_transient_retry_error(_Status(524)))

    def test_circuit_reset_set_includes_it(self):
        import inspect
        source = inspect.getsource(
            pr.ProviderCooldownRegistry.record_transient_failure)
        self.assertIn("524", source)

    def test_permanent_codes_stay_permanent(self):
        for status in (400, 401, 403, 404, 422):
            with self.subTest(status=status):
                self.assertFalse(pr._is_transient_provider_error(_Status(status)))
                self.assertFalse(gui._is_transient_retry_error(_Status(status)))

    def test_other_transient_codes_unchanged(self):
        for status in (408, 429, 500, 502, 503, 504, 529):
            with self.subTest(status=status):
                self.assertTrue(pr._is_transient_provider_error(_Status(status)))
                self.assertTrue(gui._is_transient_retry_error(_Status(status)))


if __name__ == "__main__":
    unittest.main()
