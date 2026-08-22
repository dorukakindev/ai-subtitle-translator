# -*- coding: utf-8 -*-
"""Ikinci gruba ait yedek API anahtari.

Rota failover'i base_url'i degistirir, anahtari degistirmez. Sorun new-api
GRUBUNDA ise (kota bitti, model gruba kapali, anahtar askida) dort rota da
ayni hatayi verir. Bu katman yedek anahtara gecer ve gecisi kosu boyunca
yapisik tutar.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr


class _FakeClient:
    def __init__(self, api_key, base_url="https://api.shuaiapi.com/v1"):
        self.api_key = api_key
        self.base_url = base_url

    def with_options(self, **kwargs):
        return _FakeClient(
            kwargs.get("api_key", self.api_key),
            kwargs.get("base_url", self.base_url),
        )


class _StatusError(Exception):
    def __init__(self, status, message=""):
        super().__init__(message or f"HTTP {status}")
        self.status_code = status


class ConfigureTest(unittest.TestCase):
    def tearDown(self):
        pr.reset_api_key_fallback()

    def test_backup_is_registered(self):
        self.assertTrue(pr.configure_api_key_fallback(
            "main", primary_key="birincil", backup_key="yedek"))
        self.assertEqual(pr.api_key_fallback_state("main"),
                         {"active": "primary", "switched": False})

    def test_missing_backup_is_ignored(self):
        self.assertFalse(pr.configure_api_key_fallback(
            "main", primary_key="birincil", backup_key=""))
        self.assertEqual(pr.api_key_fallback_state("main"), {})

    def test_identical_keys_are_ignored(self):
        self.assertFalse(pr.configure_api_key_fallback(
            "main", primary_key="ayni", backup_key="ayni"))
        self.assertEqual(pr.api_key_fallback_state("main"), {})

    def test_reconfigure_returns_to_primary(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")
        pr._API_KEY_FALLBACKS["main"]["active"] = "backup"
        pr.configure_api_key_fallback("main", "birincil", "yedek")
        self.assertEqual(pr.api_key_fallback_state("main")["active"], "primary")


class KeyErrorClassificationTest(unittest.TestCase):
    def test_auth_and_permission_errors_switch(self):
        self.assertTrue(pr._is_api_key_or_group_error(_StatusError(401)))
        self.assertTrue(pr._is_api_key_or_group_error(_StatusError(403)))

    def test_quota_text_switches(self):
        self.assertTrue(pr._is_api_key_or_group_error(
            _StatusError(429, "insufficient_quota for this token")))
        self.assertTrue(pr._is_api_key_or_group_error(
            Exception("pre_consume_token_quota_failed")))

    def test_group_channel_text_switches(self):
        self.assertTrue(pr._is_api_key_or_group_error(
            Exception("no available channel for the current group")))

    def test_route_shaped_errors_do_not_switch(self):
        # 404 rota failover'inin isi; anahtar degistirmek yanlis olurdu.
        self.assertFalse(pr._is_api_key_or_group_error(_StatusError(404)))
        self.assertFalse(pr._is_api_key_or_group_error(_StatusError(502)))
        self.assertFalse(pr._is_api_key_or_group_error(
            _StatusError(429, "rate limit reached")))


class FailoverTest(unittest.TestCase):
    def setUp(self):
        pr.reset_api_key_fallback()
        self.calls = []

    def tearDown(self):
        pr.reset_api_key_fallback()

    def _route_stub(self, behaviour):
        def _call(client, model, kwargs, requested_format=None,
                  checkpoint_label="", cancel_context=None):
            self.calls.append(client.api_key)
            outcome = behaviour(client.api_key)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return _call

    def _run(self, behaviour, label="main_translation"):
        with mock.patch.object(pr, "_chat_create_with_route_failover",
                               self._route_stub(behaviour)):
            return pr.chat_create_with_shuai_failover(
                _FakeClient("birincil"), "gpt-5.4", {},
                checkpoint_label=label)

    def test_group_error_switches_to_backup(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")

        def behaviour(key):
            if key == "birincil":
                return _StatusError(403, "group has no access to this model")
            return "ok"
        self.assertEqual(self._run(behaviour), "ok")
        self.assertEqual(self.calls, ["birincil", "yedek"])
        self.assertTrue(pr.api_key_fallback_state("main")["switched"])

    def test_switch_is_sticky_for_later_calls(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")

        def behaviour(key):
            if key == "birincil":
                return _StatusError(401)
            return "ok"
        self._run(behaviour)
        self.calls.clear()
        self.assertEqual(self._run(behaviour), "ok")
        # Ikinci istek dogrudan yedekle gider; olu anahtar bir daha denenmez.
        self.assertEqual(self.calls, ["yedek"])

    def test_non_key_error_is_raised_unchanged(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")
        with self.assertRaises(_StatusError):
            self._run(lambda key: _StatusError(500, "server error"))
        self.assertEqual(self.calls, ["birincil"])
        self.assertEqual(pr.api_key_fallback_state("main")["active"], "primary")

    def test_without_backup_behaviour_is_unchanged(self):
        with self.assertRaises(_StatusError):
            self._run(lambda key: _StatusError(403))
        self.assertEqual(self.calls, ["birincil"])

    def test_backup_failure_is_not_retried_forever(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")
        with self.assertRaises(_StatusError):
            self._run(lambda key: _StatusError(403))
        self.assertEqual(self.calls, ["birincil", "yedek"])

    def test_helper_scope_has_no_backup_by_default(self):
        pr.configure_api_key_fallback("main", "birincil", "yedek")
        with self.assertRaises(_StatusError):
            self._run(lambda key: _StatusError(403), label="critic_pass")
        self.assertEqual(self.calls, ["birincil"])

    def test_switch_is_logged_once(self):
        logs = []
        pr.configure_api_key_fallback(
            "main", "birincil", "yedek",
            log_fn=lambda msg, level="info": logs.append((level, msg)))

        def behaviour(key):
            if key == "birincil":
                return _StatusError(403)
            return "ok"
        self._run(behaviour)
        self._run(behaviour)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0][0], "warn")


if __name__ == "__main__":
    unittest.main()
