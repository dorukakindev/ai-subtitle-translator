# -*- coding: utf-8 -*-
"""Sağlayıcı sağlık testi, çevirinin denediği rotaların aynısını denemeli.

Çeviri isteği `chat_create_with_shuai_failover` üzerinden shuaiapi'nin dört
rotasını da deniyordu; sağlık testi yalnız ayarlardaki tek rotayı yokluyordu.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr
import subtitle_translator_gui as g


class _FakeClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.api_key = "sk-test"

    def with_options(self, **kwargs):
        return _FakeClient(kwargs.get("base_url", self.base_url))


class ProbeRouteSelectionTest(unittest.TestCase):
    def setUp(self):
        pr.reset_shuai_route_metrics()
        self.addCleanup(pr.reset_shuai_route_metrics)

    def test_official_openai_probes_a_single_endpoint(self):
        probes = g.provider_probe_routes(_FakeClient(""))
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0][0], "")

    def test_an_unrelated_custom_provider_is_never_widened(self):
        client = _FakeClient("https://my-own-proxy.example.com/v1")
        probes = g.provider_probe_routes(client)
        self.assertEqual(len(probes), 1)
        self.assertIs(probes[0][1], client)

    def test_shuai_route_probes_every_known_route(self):
        pr.configure_shuai_route_failover(
            enabled=True, preferred_url="https://api.shuaiapi.com/v1")
        self.addCleanup(pr.configure_shuai_route_failover, False, "")
        probes = g.provider_probe_routes(
            _FakeClient("https://api.shuaiapi.com/v1"))
        routes = [route for route, _client in probes]
        self.assertEqual(
            sorted(routes),
            sorted(url for _label, url in pr.SHUAI_API_ROUTE_OPTIONS))

    def test_the_configured_route_reuses_the_original_client(self):
        pr.configure_shuai_route_failover(
            enabled=True, preferred_url="https://api.shuaiapi.com/v1")
        self.addCleanup(pr.configure_shuai_route_failover, False, "")
        client = _FakeClient("https://api.shuaiapi.com/v1")
        probes = g.provider_probe_routes(client)
        original = [
            probe_client for route, probe_client in probes
            if route == "https://api.shuaiapi.com/v1"
        ]
        self.assertEqual(len(original), 1)
        self.assertIs(original[0], client)

    def test_failover_off_keeps_the_probe_on_one_route(self):
        pr.configure_shuai_route_failover(
            enabled=False, preferred_url="https://api.shuaiapi.com/v1")
        self.addCleanup(pr.configure_shuai_route_failover, False, "")
        probes = g.provider_probe_routes(
            _FakeClient("https://api.shuaiapi.com/v1"))
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0][0], "https://api.shuaiapi.com/v1")

    def test_all_routes_cooling_down_still_probes_the_configured_one(self):
        pr.configure_shuai_route_failover(
            enabled=True, preferred_url="https://api.shuaiapi.com/v1")
        self.addCleanup(pr.configure_shuai_route_failover, False, "")
        # GUI adı içe aktarım anında bağlandığı için GUI modülünde yamalanır.
        with patch.object(g, "_shuai_route_candidates", return_value=()):
            probes = g.provider_probe_routes(
                _FakeClient("https://api.shuaiapi.com/v1"))
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0][0], "https://api.shuaiapi.com/v1")


class ProbeOnlyReachesTheConfiguredProviderTest(unittest.TestCase):
    """Alternatif rotalar AYNI sağlayıcının kapılarıdır, başka servis değil."""

    def test_every_route_option_belongs_to_the_same_provider_family(self):
        hosts = {
            url.split("//", 1)[1].split("/", 1)[0]
            for _label, url in pr.SHUAI_API_ROUTE_OPTIONS
        }
        self.assertTrue(hosts)
        for host in hosts:
            with self.subTest(host=host):
                self.assertTrue(
                    host.endswith("shuaiapi.com") or host.endswith("oai.sb"),
                    host)

    def test_openai_is_not_a_failover_target(self):
        for _label, url in pr.SHUAI_API_ROUTE_OPTIONS:
            with self.subTest(url=url):
                self.assertNotIn("openai.com", url)


if __name__ == "__main__":
    unittest.main()
