# -*- coding: utf-8 -*-
"""Eksik yardimci anahtar mesaji asil sebebi soylemeli.

Eski mesaj ('Analiz / kalite veya OpenAI API key girin veya Hybrid modu
kapatin') en sik sebebi hic gostermiyordu: ana hat ile yardimci farkli
servise bakiyorsa anahtar bilerek devredilmiyor.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


class MissingHelperKeyMessageTest(unittest.TestCase):
    def test_host_mismatch_is_named(self):
        message = gui.App._describe_missing_helper_key(
            "https://api.shuaiapi.com/v1", "https://api.openai.com/v1",
            "Yardimci analiz")
        self.assertIn("api.shuaiapi.com", message)
        self.assertIn("api.openai.com", message)
        self.assertIn("Base URL", message)

    def test_same_host_falls_back_to_generic_advice(self):
        message = gui.App._describe_missing_helper_key(
            "https://api.shuaiapi.com/v1", "https://api.shuaiapi.com/v1",
            "Yardimci analiz")
        self.assertNotIn("İki farklı servis", message)
        self.assertIn("API profili", message)

    def test_unknown_urls_do_not_crash(self):
        message = gui.App._describe_missing_helper_key("", None, "QC")
        self.assertIn("QC", message)

    def test_role_label_is_included(self):
        message = gui.App._describe_missing_helper_key(
            "https://a.example/v1", "https://b.example/v1", "Polish")
        self.assertTrue(message.startswith("Polish"))

    def test_reason_resolver_uses_app_urls(self):
        stub = type("Stub", (), {})()
        stub._helper_api_base_url = lambda role: "https://api.shuaiapi.com/v1"
        stub._main_api_base_url = lambda: "https://api.openai.com/v1"
        message = gui.App._missing_helper_key_reason(stub, "analysis")
        self.assertIn("api.shuaiapi.com", message)

    def test_resolver_survives_broken_resolvers(self):
        def boom(*args, **kwargs):
            raise RuntimeError("patladi")
        stub = type("Stub", (), {})()
        stub._helper_api_base_url = boom
        stub._main_api_base_url = boom
        message = gui.App._missing_helper_key_reason(stub, "analysis")
        self.assertIn("API profili", message)


if __name__ == "__main__":
    unittest.main()
