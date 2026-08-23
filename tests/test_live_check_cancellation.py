# -*- coding: utf-8 -*-
"""Durdur, canlılık kontrolünü de kesebilmeli."""
import inspect
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr
import subtitle_translator_gui as g

URL = "https://api.shuaiapi.com/v1"


class ProbeStopsWhenCancelledTest(unittest.TestCase):
    """Sonda 20 sn x 4 rota x 2 tur yürüyor: sağlayıcı asılıyken ~163 sn.

    2026-08-24 koşusunda Durdur'a 02:00:37'de basıldı, etkisi 02:01:35'te
    görüldü — 58 saniye. `probe_api_key` iptal bağlamı almadığı için
    kalan rotalar ve tur sonuna kadar denendi.
    """

    def test_an_already_cancelled_probe_makes_no_request(self):
        started = time.monotonic()
        result = pr.probe_api_key("sk-x", URL, "gpt-5.4", realistic=True,
                                  should_cancel=lambda: True)
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertEqual(result["attempts"], 0)

    def test_cancelling_is_not_reported_as_a_provider_failure(self):
        result = pr.probe_api_key("sk-x", URL, "gpt-5.4", realistic=True,
                                  should_cancel=lambda: True)
        self.assertFalse(result["ok"])
        self.assertTrue(result["cancelled"])
        self.assertIn("durdurdu", result["detail"])

    def test_the_sweep_stops_at_the_route_where_cancel_appears(self):
        calls = []
        state = {"cancel": False}

        def fake_request(url, key, timeout, payload):
            calls.append(url)
            state["cancel"] = True          # ilk rotadan sonra Durdur
            return None, None, "zaman aşımı"

        original = pr._api_key_check_request
        pr._api_key_check_request = fake_request
        try:
            pr.probe_api_key(
                "sk-x", URL, "gpt-5.4", realistic=True, attempts=2,
                retry_delay=0.0,
                route_urls=[URL, "https://b/v1", "https://c/v1"],
                should_cancel=lambda: state["cancel"])
        finally:
            pr._api_key_check_request = original
        self.assertEqual(len(calls), 1)

    def test_without_a_canceller_nothing_changes(self):
        calls = []

        def fake_request(url, key, timeout, payload):
            calls.append(url)
            return None, None, "zaman aşımı"

        original = pr._api_key_check_request
        pr._api_key_check_request = fake_request
        try:
            pr.probe_api_key("sk-x", URL, "gpt-5.4", attempts=1,
                             route_urls=[URL, "https://b/v1"])
        finally:
            pr._api_key_check_request = original
        self.assertEqual(len(calls), 2)

    def test_the_run_preflight_passes_the_stop_flag(self):
        source = inspect.getsource(g.App._provider_live_check)
        self.assertIn("should_cancel", source)
        self.assertIn("_stop_flag", source)

    def test_the_manual_key_test_is_left_alone(self):
        # Elle "API Anahtarları" sınaması koşu çalışmazken kullanılıyor;
        # koşunun Durdur bayrağı oraya uymaz.
        source = inspect.getsource(g.App._start_api_key_check)
        self.assertNotIn("_stop_flag", source)

    def test_the_gui_does_not_blame_the_provider_for_a_stop(self):
        source = inspect.getsource(g.App._provider_live_check)
        blame = source.index("gerçek bir isteği")
        self.assertIn('outcome.get("cancelled")', source[:blame])


class StartupAnnouncementIsNotRepeatedTest(unittest.TestCase):
    """`_set_running(True)` her onay penceresinden sonra çağrılıyor.

    2026-08-24 oturumunda aynı üç satırlık blok 7 kez yazıldı.
    """

    def test_the_announcement_is_guarded_by_a_signature(self):
        source = inspect.getsource(g.App._set_running)
        self.assertIn("_run_pipeline_announced", source)
        self.assertIn("_sleep_prevention_announced", source)

    def test_the_guard_is_cleared_when_the_run_ends(self):
        source = inspect.getsource(g.App._set_running)
        end = source.index("elif not running:")
        self.assertIn("_run_pipeline_announced = None", source[end:end + 400])

    def test_the_missing_backup_key_warning_is_still_reachable(self):
        source = inspect.getsource(g.App._set_running)
        self.assertIn("Yedek anahtar YOK", source)


if __name__ == "__main__":
    unittest.main()
