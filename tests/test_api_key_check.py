# -*- coding: utf-8 -*-
"""'Anahtarları Dene' düğmesinin arkasındaki sınama.

Amaç: kullanıcı koşuyu başlatmadan önce hangi anahtarın o modele erişimi
olduğunu görsün. Rota testi (/api/ping) yalnız YOLU ölçer; bu sınama
anahtarı ve grubu ölçer — 404 gibi grup sorunları ancak burada görünür.
"""
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr


class PayloadTest(unittest.TestCase):
    def test_gpt5_uses_max_completion_tokens_and_no_temperature(self):
        payload = pr._api_key_check_payload("gpt-5.4")
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("max_tokens", payload)
        self.assertNotIn("temperature", payload)

    def test_reasoning_family_is_covered(self):
        for model in ("o1-mini", "o3", "o4-mini", "codex-mini"):
            self.assertIn("max_completion_tokens",
                          pr._api_key_check_payload(model), model)

    def test_classic_models_keep_max_tokens(self):
        payload = pr._api_key_check_payload("gpt-4o-mini")
        self.assertIn("max_tokens", payload)
        self.assertNotIn("max_completion_tokens", payload)

    def test_request_stays_tiny(self):
        payload = pr._api_key_check_payload("gpt-5.4")
        self.assertEqual(len(payload["messages"]), 1)
        self.assertLessEqual(payload["max_completion_tokens"], 32)


class ReasonTest(unittest.TestCase):
    def test_known_codes_get_plain_turkish(self):
        self.assertIn("gecersiz", pr._api_key_check_reason(401, ""))
        self.assertIn("izni yok", pr._api_key_check_reason(403, ""))
        self.assertIn("grupta yok", pr._api_key_check_reason(404, ""))

    def test_provider_message_is_appended(self):
        body = '{"error": {"message": "model gpt-5.4 not found"}}'
        self.assertIn("model gpt-5.4 not found",
                      pr._api_key_check_reason(404, body))

    def test_quota_text_beats_the_status_label(self):
        body = '{"error": {"message": "insufficient_quota"}}'
        self.assertTrue(pr._api_key_check_reason(429, body).startswith("kota bitti"))

    def test_unknown_status_still_reads(self):
        self.assertIn("HTTP 418", pr._api_key_check_reason(418, ""))


class ProbeTest(unittest.TestCase):
    def _patch(self, responses):
        """responses: url -> (status, body, transport)."""
        calls = []

        def _fake(url, api_key, timeout, payload=None):
            calls.append(url)
            return responses.get(url, (None, "", "ConnectionError"))
        return calls, mock.patch.object(pr, "_api_key_check_request", _fake)

    def test_success_on_the_first_route(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        calls, patch = self._patch({url: (200, '{"choices": []}', "")})
        with patch:
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertTrue(result["ok"])
        self.assertEqual(calls, [url])

    def test_transport_failure_moves_to_the_next_route(self):
        good = "https://oai.sb/v1/chat/completions"
        calls, patch = self._patch({good: (200, "{}", "")})
        with patch:
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertTrue(result["ok"])
        self.assertEqual(result["route"], "https://oai.sb/v1")
        self.assertEqual(len(calls), 2)

    def test_server_error_is_not_blamed_on_the_key(self):
        first = "https://api.shuaiapi.com/v1/chat/completions"
        good = "https://oai.sb/v1/chat/completions"
        calls, patch = self._patch({first: (502, "", ""), good: (200, "{}", "")})
        with patch:
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertTrue(result["ok"])

    def test_401_stops_immediately(self):
        # Anahtar gecersizse diger rotalari denemek bos yere gecikme olur.
        url = "https://api.shuaiapi.com/v1/chat/completions"
        calls, patch = self._patch({url: (401, '{"error": "bad key"}', "")})
        with patch:
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], 401)
        self.assertEqual(calls, [url])

    def test_404_asks_the_group_which_models_it_has(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        calls, patch = self._patch({url: (404, "", "")})
        with patch, mock.patch.object(
                pr, "list_models_for_key",
                return_value=["gpt-5.4-mini", "gpt-4o"]):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertEqual(result["status"], 404)
        self.assertIn("gpt-5.4-mini", result["hint"])

    def test_404_with_the_model_listed_says_so(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        _calls, patch = self._patch({url: (404, "", "")})
        with patch, mock.patch.object(
                pr, "list_models_for_key", return_value=["gpt-5.4"]):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertIn("listesinde", result["hint"])

    def test_non_shuai_url_is_tried_once(self):
        url = "https://api.openai.com/v1/chat/completions"
        calls, patch = self._patch({url: (200, "{}", "")})
        with patch:
            pr.probe_api_key("anahtar", "https://api.openai.com/v1", "gpt-4o")
        self.assertEqual(calls, [url])

    def test_every_route_dead_reports_the_last_failure(self):
        _calls, patch = self._patch({})
        with patch, mock.patch.object(pr.time, "sleep", lambda _s: None):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertFalse(result["ok"])
        self.assertIsNone(result["status"])
        self.assertNotIn("flaky", result)

    def test_missing_key_never_hits_the_network(self):
        calls, patch = self._patch({})
        with patch:
            result = pr.probe_api_key("", "https://api.shuaiapi.com/v1", "gpt-5.4")
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])

    def test_missing_model_never_hits_the_network(self):
        calls, patch = self._patch({})
        with patch:
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1", "")
        self.assertFalse(result["ok"])
        self.assertEqual(calls, [])


class ModelListTest(unittest.TestCase):
    def test_ids_are_extracted_and_sorted(self):
        body = '{"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}]}'
        with mock.patch.object(pr, "_api_key_check_request",
                               return_value=(200, body, "")):
            self.assertEqual(
                pr.list_models_for_key("anahtar", "https://api.shuaiapi.com/v1"),
                ["a", "b"])

    def test_non_200_returns_empty(self):
        with mock.patch.object(pr, "_api_key_check_request",
                               return_value=(401, "", "")):
            self.assertEqual(
                pr.list_models_for_key("anahtar", "https://api.shuaiapi.com/v1"),
                [])

    def test_broken_json_returns_empty(self):
        with mock.patch.object(pr, "_api_key_check_request",
                               return_value=(200, "<html>", "")):
            self.assertEqual(
                pr.list_models_for_key("anahtar", "https://api.shuaiapi.com/v1"),
                [])


_CHANNEL_DOWN = ('{"error": {"message": "The channel is temporarily '
                 'unavailable. Please contact the administrator."}}')


class FlakyChannelTest(unittest.TestCase):
    """2026-08-23: aynı anahtar 16:49'da 404, 16:51'de çalışıyordu.

    new-api üst kaynak kanalı düştüğünde de 404 döner. Bunu "model bu
    grupta yok" diye okumak yanlış; sağlam bir anahtarı kırmızı yakar ve
    tek atışlık yedek geçişini boşa harcar.
    """

    def test_channel_text_is_not_read_as_a_missing_model(self):
        reason = pr._api_key_check_reason(404, _CHANNEL_DOWN)
        self.assertIn("kanali gecici", reason)
        self.assertNotIn("grupta yok", reason)

    def test_real_404_still_says_the_model_is_missing(self):
        reason = pr._api_key_check_reason(404, '{"error": "model not found"}')
        self.assertIn("grupta yok", reason)

    def test_flaky_classification(self):
        self.assertTrue(pr._api_key_check_is_flaky(None, ""))
        self.assertTrue(pr._api_key_check_is_flaky(502, ""))
        self.assertTrue(pr._api_key_check_is_flaky(404, _CHANNEL_DOWN))
        self.assertTrue(pr._api_key_check_is_flaky(429, "rate limit"))
        self.assertFalse(pr._api_key_check_is_flaky(404, "model not found"))
        self.assertFalse(pr._api_key_check_is_flaky(401, ""))
        self.assertFalse(pr._api_key_check_is_flaky(429, "insufficient_quota"))

    def test_a_recovering_channel_ends_up_green(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        seen = []

        def _fake(request_url, api_key, timeout, payload=None):
            seen.append(request_url)
            if request_url != url:
                return (None, "", "ConnectionError")
            return (200, "{}", "") if len(seen) > 4 else (404, _CHANNEL_DOWN, "")
        with mock.patch.object(pr, "_api_key_check_request", _fake),                 mock.patch.object(pr.time, "sleep", lambda _s: None):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertTrue(result["ok"])

    def test_a_dead_key_is_not_retried(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        calls = []

        def _fake(request_url, api_key, timeout, payload=None):
            calls.append(request_url)
            return (401, "", "")
        with mock.patch.object(pr, "_api_key_check_request", _fake),                 mock.patch.object(pr.time, "sleep", lambda _s: None):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertEqual(calls, [url])
        self.assertEqual(result["status"], 401)

    def test_a_missing_model_is_not_retried(self):
        calls = []

        def _fake(request_url, api_key, timeout, payload=None):
            calls.append(request_url)
            return (404, '{"error": "model not found"}', "")
        with mock.patch.object(pr, "_api_key_check_request", _fake),                 mock.patch.object(pr, "list_models_for_key", return_value=[]),                 mock.patch.object(pr.time, "sleep", lambda _s: None):
            pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1", "gpt-5.4")
        self.assertEqual(len(calls), 1)


class PostRoutePredicateTest(unittest.TestCase):
    class _Err(Exception):
        def __init__(self, status, message=""):
            super().__init__(message or f"HTTP {status}")
            self.status_code = status

    def test_transient_channel_404_keeps_the_backup_key_in_reserve(self):
        exc = self._Err(404, "The channel is temporarily unavailable.")
        self.assertFalse(pr._is_post_route_key_error(exc))

    def test_a_genuinely_missing_model_still_switches(self):
        self.assertTrue(pr._is_post_route_key_error(
            self._Err(404, "model gpt-5.4 not found")))

    def test_auth_errors_are_unaffected(self):
        self.assertTrue(pr._is_post_route_key_error(self._Err(401)))
        self.assertFalse(pr._is_post_route_key_error(self._Err(502)))


class StabilityReportingTest(unittest.TestCase):
    """Yeşil ışık "anahtar doğru" demek, "sağlayıcı sağlıklı" DEMEK değil.

    2026-08-23: anahtar testi 18:43'te "calisiyor" dedi, 18:44'teki koşu
    dört rotadan da 502 aldı. Test yalan söylemiyordu — kaç denemede
    başardığını söylemiyordu.
    """

    def test_a_clean_first_try_has_no_note(self):
        url = "https://api.shuaiapi.com/v1/chat/completions"
        with mock.patch.object(pr, "_api_key_check_request",
                               lambda u, k, t, payload=None: (200, "{}", "")):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(pr.api_key_check_stability_note(result), "")

    def test_success_after_failures_is_reported_as_unstable(self):
        seen = []

        def _fake(url, api_key, timeout, payload=None):
            seen.append(url)
            return (200, "{}", "") if len(seen) > 3 else (502, "bad gateway", "")
        with mock.patch.object(pr, "_api_key_check_request", _fake),                 mock.patch.object(pr.time, "sleep", lambda _s: None):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertTrue(result["ok"])
        self.assertEqual(result["failures"], 3)
        note = pr.api_key_check_stability_note(result)
        self.assertIn("kararsiz", note)
        self.assertIn("3", note)

    def test_a_failed_check_has_no_stability_note(self):
        result = {"ok": False, "attempts": 8, "failures": 8}
        self.assertEqual(pr.api_key_check_stability_note(result), "")

    def test_counters_survive_a_hard_failure(self):
        with mock.patch.object(pr, "_api_key_check_request",
                               lambda u, k, t, payload=None: (401, "", "")):
            result = pr.probe_api_key("anahtar", "https://api.shuaiapi.com/v1",
                                      "gpt-5.4")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(result["failures"], 1)


import subtitle_translator_gui as gui


def _app(*, main_key="ana", backup_key="", backup_profile=None):
    app = types.SimpleNamespace()
    app._api_profile_name = lambda pid: (
        (app._api_key_profiles.get(pid) or {}).get("name") or "Atanmadı")
    app._main_api_key = lambda: main_key
    app._main_api_key_backup = lambda: backup_key
    app._main_api_base_url = lambda: "https://api.shuaiapi.com/v1"
    app._main_model_name = lambda: "gpt-5.4"
    app._api_key_assignments = (
        {"main": "p1", "main_backup": "p2"} if backup_key else {"main": "p1"})
    app._api_key_profiles = {"p1": {"name": "ana api"}}
    if backup_profile:
        app._api_key_profiles["p2"] = backup_profile
    app._api_profile_endpoint = lambda pid: gui.App._api_profile_endpoint(app, pid)
    return app


class TargetsTest(unittest.TestCase):
    def test_without_a_backup_only_the_main_key_is_tried(self):
        targets = gui.App._api_key_check_targets(_app())
        self.assertEqual([t["label"] for t in targets], ["Ana anahtar"])

    def test_backup_profile_endpoint_wins(self):
        app = _app(backup_key="yedek", backup_profile={
            "provider": "openai_compatible",
            "base_url": "https://oai.sb/v1", "model": "gpt-5.4-mini"})
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[1]["base_url"], "https://oai.sb/v1")
        self.assertEqual(targets[1]["model"], "gpt-5.4-mini")

    def test_backup_falls_back_to_the_main_endpoint(self):
        app = _app(backup_key="yedek", backup_profile={
            "provider": "openai_compatible", "base_url": "", "model": ""})
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(targets[1]["base_url"], "https://api.shuaiapi.com/v1")
        self.assertEqual(targets[1]["model"], "gpt-5.4")

    def test_official_profile_uses_the_openai_endpoint(self):
        app = _app(backup_key="yedek", backup_profile={
            "provider": "openai_official", "base_url": "", "model": "gpt-4o"})
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(targets[1]["base_url"], "https://api.openai.com/v1")

    def test_main_is_always_first(self):
        app = _app(backup_key="yedek", backup_profile={
            "provider": "openai_compatible",
            "base_url": "https://oai.sb/v1", "model": "m"})
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(targets[0]["key"], "ana")
        self.assertEqual(targets[1]["key"], "yedek")


class ProfileVisibilityTest(unittest.TestCase):
    """'Doğru API'yi mi deniyor?' — hedefler profil adını taşımalı."""

    def test_main_target_carries_its_profile_name(self):
        targets = gui.App._api_key_check_targets(_app())
        self.assertEqual(targets[0]["profile"], "ana api")

    def test_backup_target_carries_its_own_profile_name(self):
        app = _app(backup_key="yedek", backup_profile={
            "name": "alternatif api", "provider": "openai_compatible",
            "base_url": "https://oai.sb/v1", "model": "gpt-5.4"})
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(targets[1]["profile"], "alternatif api")

    def test_an_unassigned_slot_reads_as_unassigned(self):
        app = _app()
        app._api_key_assignments = {}
        targets = gui.App._api_key_check_targets(app)
        self.assertEqual(targets[0]["profile"], "Atanmadı")


if __name__ == "__main__":
    unittest.main()
