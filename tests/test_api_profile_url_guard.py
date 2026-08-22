# -*- coding: utf-8 -*-
"""Saglayici turu ile API adresi celisirse profil kaydedilmemeli.

Yeni profil varsayilani 'OpenAI Uyumlu / Reseller' + api.openai.com idi.
Reseller anahtari bu adrese gidince her istek 401 doner ve hata mesaji
gercek OpenAI'yi gosterdigi icin sebep gorunmez (2026-08-23 kosu logu).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui

check = gui._api_profile_provider_url_mismatch


class ProviderUrlGuardTest(unittest.TestCase):
    def test_reseller_pointing_at_official_openai_is_blocked(self):
        message = check("openai_compatible", "https://api.openai.com/v1")
        self.assertIn("401", message)
        self.assertIn("api.openai.com", message)

    def test_bare_openai_domain_is_blocked_too(self):
        self.assertTrue(check("openai_compatible", "https://openai.com/v1"))

    def test_reseller_with_its_own_address_is_fine(self):
        self.assertEqual(check("openai_compatible", "https://api.shuaiapi.com/v1"), "")
        self.assertEqual(check("openai_compatible", "https://oai.sb/v1"), "")

    def test_official_provider_with_openai_address_is_fine(self):
        self.assertEqual(check("openai_official", "https://api.openai.com/v1"), "")

    def test_anthropic_pointing_at_openai_is_blocked(self):
        self.assertTrue(check("anthropic", "https://api.openai.com/v1"))

    def test_anthropic_with_its_own_address_is_fine(self):
        self.assertEqual(check("anthropic", "https://api.anthropic.com/v1"), "")

    def test_unparsable_address_is_left_to_other_checks(self):
        self.assertEqual(check("openai_compatible", ""), "")
        self.assertEqual(check("openai_compatible", "bozuk"), "")

    def test_host_case_is_ignored(self):
        self.assertTrue(check("openai_compatible", "https://API.OpenAI.COM/v1"))


if __name__ == "__main__":
    unittest.main()
