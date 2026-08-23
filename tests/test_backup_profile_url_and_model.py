# -*- coding: utf-8 -*-
"""Yedek profil yalnız anahtarını değil, adresini ve modelini de taşır."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr
import subtitle_translator_gui as g


class FakeClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url

    def with_options(self, **kwargs):
        return FakeClient(kwargs.get("api_key", self.api_key),
                          kwargs.get("base_url", self.base_url))


class BackupProfileCarriesItsOwnEndpointTest(unittest.TestCase):
    """Profil penceresi yedek için ayrı URL/model girdiriyor ve anahtar
    sınaması onları kullanıyordu; gerçek geçiş ise yalnız anahtarı
    değiştirip birincilin adresini koruyordu. Yedeği farklı bir bayiye
    bağlayan biri, yeni anahtarın eski adrese gittiğini ancak 401 alınca
    fark ederdi.
    """

    def setUp(self):
        pr.reset_api_key_fallback()
        self.addCleanup(pr.reset_api_key_fallback)

    def _switched(self, **kwargs):
        pr.configure_api_key_fallback("main", primary_key="K1",
                                      backup_key="K2", **kwargs)
        with pr._API_KEY_FALLBACK_LOCK:
            pr._API_KEY_FALLBACKS["main"]["active"] = "backup"

    def test_the_backup_address_is_used(self):
        self._switched(primary_base_url="https://a/v1",
                       backup_base_url="https://b/v1")
        client = pr._apply_active_api_key(FakeClient("K1", "https://a/v1"),
                                          "main")
        self.assertEqual(client.api_key, "K2")
        self.assertEqual(client.base_url, "https://b/v1")

    def test_the_backup_model_replaces_the_primary_model(self):
        self._switched(primary_model="gpt-5.4", backup_model="gpt-5.5")
        self.assertEqual(pr._fallback_model("main", "gpt-5.4"), "gpt-5.5")

    def test_a_helper_keeps_its_own_model(self):
        # 'main' yedeğini devralan yardımcı rol mini'yi kaybetmemeli.
        self._switched(primary_model="gpt-5.4", backup_model="gpt-5.5")
        self.assertEqual(pr._fallback_model("main", "gpt-5.4-mini"),
                         "gpt-5.4-mini")

    def test_identical_profiles_change_nothing_but_the_key(self):
        # Kullanıcının bugünkü ayarı: iki profil de aynı adres ve model.
        same = "https://api.shuaiapi.com/v1"
        self._switched(primary_base_url=same, backup_base_url=same,
                       primary_model="gpt-5.4", backup_model="gpt-5.4")
        client = pr._apply_active_api_key(FakeClient("K1", same), "main")
        self.assertEqual(client.api_key, "K2")
        self.assertEqual(client.base_url, same)
        self.assertEqual(pr._fallback_model("main", "gpt-5.4"), "gpt-5.4")

    def test_the_old_call_shape_still_works(self):
        # Adres/model verilmezse eski davranış: yalnız anahtar değişir.
        self._switched()
        client = pr._apply_active_api_key(FakeClient("K1", "https://eski/v1"),
                                          "main")
        self.assertEqual(client.api_key, "K2")
        self.assertEqual(client.base_url, "https://eski/v1")
        self.assertEqual(pr._fallback_model("main", "herhangi"), "herhangi")

    def test_nothing_is_swapped_before_the_switch(self):
        pr.configure_api_key_fallback(
            "main", primary_key="K1", backup_key="K2",
            primary_base_url="https://a/v1", backup_base_url="https://b/v1",
            primary_model="gpt-5.4", backup_model="gpt-5.5")
        client = pr._apply_active_api_key(FakeClient("K1", "https://a/v1"),
                                          "main")
        self.assertEqual(client.api_key, "K1")
        self.assertEqual(client.base_url, "https://a/v1")
        self.assertEqual(pr._fallback_model("main", "gpt-5.4"), "gpt-5.4")


class TheGuiSuppliesTheBackupProfileTest(unittest.TestCase):

    def test_the_resolvers_read_the_assigned_backup_profile(self):
        source = inspect.getsource(g.App._main_api_profile_field_backup)
        self.assertIn("main_backup", source)
        self.assertIn("_api_key_profiles", source)

    def test_the_snapshot_carries_them(self):
        source = inspect.getsource(g)
        self.assertIn('"main_base_url_backup"', source)
        self.assertIn('"main_model_backup"', source)

    def test_they_reach_the_fallback_registration(self):
        source = inspect.getsource(g)
        marker = source.index("configure_api_key_fallback(\n")
        window = source[marker:marker + 700]
        self.assertIn("backup_base_url=", window)
        self.assertIn("backup_model=", window)
        self.assertIn("primary_model=", window)


if __name__ == "__main__":
    unittest.main()
