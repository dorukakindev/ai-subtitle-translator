# -*- coding: utf-8 -*-
"""Ön analizden önce sağlayıcı canlılık kapısı.

2026-08-23 loglarının gösterdiği iki katmanlı yanılma:
  - /api/ping üç kez 3/3 canlı ölçtü, istekler yine 502 aldı: rota ölçümü
    YOLU görüyor, model kanalını değil.
  - 16 jetonluk "ping" isteği de üç kez yeşil dedi: kısa istek anında
    dönüyor, uzun üretimde ağ geçidi zaman aşımına düşüyor.
Kapı bu yüzden koşunun göndereceğine BENZER boyutta gerçek bir istek atar
ve geçemezse çeviriyi hiç başlatmaz (11x60 sn merdiven işletilmez).
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr
import subtitle_translator_gui as gui


class RealisticPayloadTest(unittest.TestCase):
    def test_realistic_request_is_much_bigger_than_the_ping(self):
        tiny = pr._api_key_check_payload("gpt-5.4")
        real = pr._api_key_check_payload("gpt-5.4", realistic=True)
        self.assertGreater(
            len(real["messages"][0]["content"]),
            10 * len(tiny["messages"][0]["content"]))
        self.assertGreater(real["max_completion_tokens"],
                           tiny["max_completion_tokens"])

    def test_realistic_request_asks_for_a_real_translation(self):
        content = pr._api_key_check_payload("gpt-5.4", realistic=True)
        self.assertIn("Translate", content["messages"][0]["content"])

    def test_classic_models_still_get_max_tokens(self):
        payload = pr._api_key_check_payload("gpt-4o", realistic=True)
        self.assertIn("max_tokens", payload)
        self.assertNotIn("max_completion_tokens", payload)

    def test_probe_passes_the_flag_through(self):
        seen = {}

        def _fake(url, api_key, timeout, payload=None):
            seen["payload"] = payload
            return (200, "{}", "")
        with mock.patch.object(pr, "_api_key_check_request", _fake):
            pr.probe_api_key("k", "https://api.shuaiapi.com/v1", "gpt-5.4",
                             realistic=True)
        self.assertIn("Translate", seen["payload"]["messages"][0]["content"])


def _app(*, base_url="https://api.shuaiapi.com/v1", key="anahtar",
         model="gpt-5.4"):
    app = types.SimpleNamespace()
    app._main_api_base_url = lambda: base_url
    app._main_api_key = lambda: key
    app._main_model_name = lambda: model
    app.logs = []
    app._log = lambda message, level="info": app.logs.append((level, message))
    app._set_status = lambda *_a, **_k: None
    return app


class LiveCheckTest(unittest.TestCase):
    def _run(self, app, outcome):
        with mock.patch.object(pr, "probe_api_key", return_value=outcome):
            return gui.App._provider_live_check(app, "Çeviri")

    def test_a_working_provider_opens_the_gate(self):
        app = _app()
        self.assertTrue(self._run(app, {"ok": True, "attempts": 1,
                                        "failures": 0}))

    def test_a_dead_provider_stops_the_run(self):
        app = _app()
        self.assertFalse(self._run(app, {
            "ok": False, "detail": "bayinin kanali gecici olarak kapali",
            "attempts": 8, "failures": 8}))
        self.assertTrue(any(level == "err" for level, _msg in app.logs))

    def test_an_unstable_pass_is_warned_about_but_allowed(self):
        app = _app()
        self.assertTrue(self._run(app, {"ok": True, "attempts": 6,
                                        "failures": 4}))
        self.assertTrue(any(level == "warn" for level, _msg in app.logs))

    def test_official_openai_is_not_charged_for_a_check(self):
        app = _app(base_url="https://api.openai.com/v1")
        called = []
        with mock.patch.object(pr, "probe_api_key",
                               side_effect=lambda *a, **k: called.append(1)):
            self.assertTrue(gui.App._provider_live_check(app, "Çeviri"))
        self.assertEqual(called, [])

    def test_a_recent_pass_is_not_repeated(self):
        app = _app()
        calls = []

        def _fake(*_args, **_kwargs):
            calls.append(1)
            return {"ok": True, "attempts": 1, "failures": 0}
        with mock.patch.object(pr, "probe_api_key", _fake):
            gui.App._provider_live_check(app, "Kaynak dil ön analizi")
            gui.App._provider_live_check(app, "İçerik türü ön analizi")
            gui.App._provider_live_check(app, "Çeviri")
        self.assertEqual(len(calls), 1)

    def test_a_missing_key_does_not_block_the_run(self):
        # Kapı bir güvenlik kontrolü değil; anahtar yoksa asıl doğrulama
        # zaten başka yerde hata verir, burada takılıp kalmayız.
        self.assertTrue(self._run(_app(key=""), {"ok": False}))

    def test_every_outcome_leaves_a_trace_in_the_log(self):
        """Ücretli bir kontrolün çalıştığı log'dan görülebilmeli.

        Sessiz geçen kapı, olmayan kapıdan kötüdür: koruma var sanılır ve
        gerçekten çalışıp çalışmadığı denetlenemez (2026-08-22 21:19 koşusu:
        rota testi ile ön kontrol arasında 1 sn vardı, kapının çalışıp
        çalışmadığı log'dan anlaşılamıyordu).
        """
        app = _app()
        self._run(app, {"ok": True, "attempts": 1, "failures": 0,
                        "route": "https://api.shuaiapi.com/v1"})
        self.assertTrue(app.logs, "başarı sessiz kalmamalı")
        self.assertIn("Canlılık kontrolü geçti", app.logs[0][1])

    def test_a_skipped_check_says_why(self):
        app = _app(key="")
        self._run(app, {"ok": False})
        self.assertTrue(any("atlandı" in msg for _lvl, msg in app.logs))

    def test_the_cached_skip_is_visible_too(self):
        app = _app()
        calls = []

        def _fake(*_a, **_k):
            calls.append(1)
            return {"ok": True, "attempts": 1, "failures": 0}
        with mock.patch.object(pr, "probe_api_key", _fake):
            gui.App._provider_live_check(app, "Çeviri")
            app.logs.clear()
            gui.App._provider_live_check(app, "Çeviri")
        self.assertEqual(len(calls), 1)
        self.assertTrue(any("tekrar sorulmadı" in msg for _lvl, msg in app.logs))

    def test_a_fresh_boot_is_not_a_recent_pass(self):
        # time.monotonic() önyüklemeden beri sayar: uptime < TTL iken
        # 0.0 varsayılanı geçilmiş bir kontrol gibi görünürdü ve kapı
        # ölü sağlayıcıyı bile sorgusuz geçerdi.
        app = _app()
        calls = []

        def _fake(*_a, **_k):
            calls.append(1)
            return {"ok": False, "detail": "ölü", "attempts": 4, "failures": 4}
        with mock.patch.object(pr, "probe_api_key", _fake), \
                mock.patch.object(gui.time, "monotonic", return_value=60.0):
            self.assertFalse(gui.App._provider_live_check(app, "Çeviri"))
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(level == "err" for level, _msg in app.logs))

    def test_a_broken_probe_does_not_block_the_run(self):
        app = _app()
        with mock.patch.object(pr, "probe_api_key",
                               side_effect=RuntimeError("patladı")):
            self.assertTrue(gui.App._provider_live_check(app, "Çeviri"))


if __name__ == "__main__":
    unittest.main()
