# -*- coding: utf-8 -*-
"""SHUAI rota olcumu: soguk baslangic siralamasi ve 'hepsi olu' tespiti.

2026-08-23: dort rota da HTTP 502 dondu, uygulama istek basina 11x60 sn
yeniden deneme merdivenine girdi ve on analiz 10 dakika bekledi. Olcum bunu
saniyelere indiriyor; ayrica soguk baslangicta sira artik liste sirasina
degil gercek gecikmeye dayaniyor.
"""
import io
import json
import os
import sys
import unittest
from unittest import mock
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import provider_retry as pr


ROUTES = [url for _label, url in pr.SHUAI_API_ROUTE_OPTIONS]


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def _ping_body(nonce, service="new-api", success=True):
    return json.dumps({
        "success": success,
        "data": {"service": service, "nonce": nonce, "timestamp": 1},
    }).encode("utf-8")


class ProbeUrlTest(unittest.TestCase):
    def test_derives_ping_endpoint(self):
        self.assertEqual(
            pr.shuai_route_probe_url("https://api.shuaiapi.com/v1"),
            "https://api.shuaiapi.com/api/ping")
        self.assertEqual(
            pr.shuai_route_probe_url("https://oai.sb/v1"),
            "https://oai.sb/api/ping")

    def test_foreign_host_is_rejected(self):
        self.assertEqual(pr.shuai_route_probe_url("https://api.openai.com/v1"), "")
        self.assertEqual(pr.shuai_route_probe_url(""), "")


class SingleRouteProbeTest(unittest.TestCase):
    def _run(self, opener, attempts=1):
        with mock.patch.object(pr.urllib.request, "urlopen", opener):
            return pr._probe_one_shuai_route(ROUTES[0], attempts, 1.0)

    def test_valid_ping_is_counted(self):
        def opener(request, timeout=None):
            nonce = urlparse(request.full_url).query.split("nonce=")[1]
            return _FakeResponse(_ping_body(nonce))
        result = self._run(opener, attempts=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["successes"], 3)
        self.assertIsNotNone(result["median_ms"])
        self.assertEqual(result["detail"], "")

    def test_nonce_mismatch_is_not_healthy(self):
        def opener(request, timeout=None):
            return _FakeResponse(_ping_body("baskanonce"))
        result = self._run(opener)
        self.assertFalse(result["ok"])
        self.assertEqual(result["detail"], "gecersiz yanit")

    def test_wrong_service_is_not_healthy(self):
        def opener(request, timeout=None):
            nonce = urlparse(request.full_url).query.split("nonce=")[1]
            return _FakeResponse(_ping_body(nonce, service="baska-servis"))
        self.assertFalse(self._run(opener)["ok"])

    def test_http_error_detail(self):
        def opener(request, timeout=None):
            raise pr.urllib.error.HTTPError(
                request.full_url, 502, "Bad Gateway", None, None)
        result = self._run(opener)
        self.assertFalse(result["ok"])
        self.assertEqual(result["detail"], "HTTP 502")

    def test_network_error_detail(self):
        def opener(request, timeout=None):
            raise TimeoutError("zaman asimi")
        result = self._run(opener)
        self.assertFalse(result["ok"])
        self.assertIn("TimeoutError", result["detail"])

    def test_no_api_key_is_sent(self):
        seen = {}

        def opener(request, timeout=None):
            seen.update({k.lower(): v for k, v in request.header_items()})
            nonce = urlparse(request.full_url).query.split("nonce=")[1]
            return _FakeResponse(_ping_body(nonce))
        self._run(opener)
        self.assertNotIn("authorization", seen)
        self.assertIn("accept", seen)


class ProbeStateTest(unittest.TestCase):
    def setUp(self):
        pr.reset_shuai_route_probe()

    def tearDown(self):
        pr.reset_shuai_route_probe()

    def _fake_probe(self, mapping):
        def _probe(route_url, attempts, timeout):
            return mapping[route_url]
        return _probe

    def test_results_land_in_route_states(self):
        mapping = {
            ROUTES[0]: {"ok": True, "successes": 2, "attempts": 2,
                        "median_ms": 900, "detail": ""},
            ROUTES[1]: {"ok": True, "successes": 2, "attempts": 2,
                        "median_ms": 120, "detail": ""},
            ROUTES[2]: {"ok": False, "successes": 0, "attempts": 2,
                        "median_ms": None, "detail": "HTTP 502"},
            ROUTES[3]: {"ok": False, "successes": 0, "attempts": 2,
                        "median_ms": None, "detail": "yanit yok"},
        }
        with mock.patch.object(pr, "_probe_one_shuai_route",
                               self._fake_probe(mapping)):
            results = pr.probe_shuai_routes(attempts=2)
        self.assertEqual(len(results), 4)
        self.assertTrue(pr.shuai_probe_ran())
        self.assertEqual(pr._SHUAI_ROUTE_STATES[ROUTES[1]]["probe_latency_ms"], 120)
        self.assertFalse(pr._SHUAI_ROUTE_STATES[ROUTES[2]]["probe_ok"])

    def test_report_is_sorted_fastest_first(self):
        mapping = {
            ROUTES[0]: {"ok": True, "successes": 1, "attempts": 1,
                        "median_ms": 900, "detail": ""},
            ROUTES[1]: {"ok": True, "successes": 1, "attempts": 1,
                        "median_ms": 120, "detail": ""},
            ROUTES[2]: {"ok": True, "successes": 1, "attempts": 1,
                        "median_ms": 400, "detail": ""},
            ROUTES[3]: {"ok": False, "successes": 0, "attempts": 1,
                        "median_ms": None, "detail": "HTTP 502"},
        }
        with mock.patch.object(pr, "_probe_one_shuai_route",
                               self._fake_probe(mapping)):
            pr.probe_shuai_routes(attempts=1)
        hosts = [row["host"] for row in pr.shuai_route_probe_report()]
        self.assertEqual(hosts[0], urlparse(ROUTES[1]).hostname)
        self.assertEqual(hosts[-1], urlparse(ROUTES[3]).hostname)

    def test_reset_clears_measurements(self):
        mapping = {url: {"ok": True, "successes": 1, "attempts": 1,
                         "median_ms": 100, "detail": ""} for url in ROUTES}
        with mock.patch.object(pr, "_probe_one_shuai_route",
                               self._fake_probe(mapping)):
            pr.probe_shuai_routes(attempts=1)
        pr.reset_shuai_route_probe()
        self.assertFalse(pr.shuai_probe_ran())
        self.assertIsNone(pr._SHUAI_ROUTE_STATES[ROUTES[0]]["probe_latency_ms"])


class RouteOrderingTest(unittest.TestCase):
    def setUp(self):
        pr.reset_shuai_route_probe()
        for state in pr._SHUAI_ROUTE_STATES.values():
            state.update({"cooldown_until": 0.0, "attempts": 0, "successes": 0,
                          "failures": 0, "rate_limits": 0,
                          "duration_seconds": 0.0, "health": "unknown"})
        pr.configure_shuai_route_failover(
            enabled=True, preferred_url=ROUTES[0], main_preferred_url=ROUTES[0])

    def tearDown(self):
        pr.reset_shuai_route_probe()
        pr.configure_shuai_route_failover(enabled=False)

    def _order(self):
        return [urlparse(url).hostname
                for url in pr._shuai_route_candidates(ROUTES[0], "main")]

    def _measure(self, url, latency, ok=True):
        pr._SHUAI_ROUTE_STATES[url]["probe_ok"] = ok
        pr._SHUAI_ROUTE_STATES[url]["probe_latency_ms"] = latency

    def test_without_probe_order_is_unchanged(self):
        self.assertEqual(
            self._order(), [urlparse(url).hostname for url in ROUTES])

    def test_probe_reorders_by_latency(self):
        pr._SHUAI_PROBE_DONE = True
        self._measure(ROUTES[0], 900)
        self._measure(ROUTES[1], 1500)
        self._measure(ROUTES[2], 1200)
        self._measure(ROUTES[3], 120)
        order = self._order()
        # Tercih edilen rota basta kalir; kalanlar olculen gecikmeye gore.
        self.assertEqual(order[0], urlparse(ROUTES[0]).hostname)
        self.assertEqual(order[1], urlparse(ROUTES[3]).hostname)
        self.assertEqual(order[-1], urlparse(ROUTES[1]).hostname)

    def test_dead_preferred_route_is_demoted(self):
        pr._SHUAI_PROBE_DONE = True
        self._measure(ROUTES[0], None, ok=False)
        self._measure(ROUTES[1], 1500)
        self._measure(ROUTES[2], 1200)
        self._measure(ROUTES[3], 120)
        order = self._order()
        self.assertEqual(order[0], urlparse(ROUTES[3]).hostname)
        self.assertEqual(order[-1], urlparse(ROUTES[0]).hostname)

    def test_live_success_rate_still_outranks_probe(self):
        pr._SHUAI_PROBE_DONE = True
        self._measure(ROUTES[1], 1500)
        self._measure(ROUTES[3], 120)
        # ROUTES[1] gercek isteklerde calisti, ROUTES[3] hep hata verdi.
        pr._SHUAI_ROUTE_STATES[ROUTES[1]].update(
            {"attempts": 4, "successes": 4, "failures": 0})
        pr._SHUAI_ROUTE_STATES[ROUTES[3]].update(
            {"attempts": 4, "successes": 0, "failures": 4})
        order = self._order()
        self.assertLess(order.index(urlparse(ROUTES[1]).hostname),
                        order.index(urlparse(ROUTES[3]).hostname))


class ProbeRankTest(unittest.TestCase):
    def setUp(self):
        pr.reset_shuai_route_probe()

    def tearDown(self):
        pr.reset_shuai_route_probe()

    def test_neutral_when_no_probe_ran(self):
        self.assertEqual(pr._shuai_probe_rank({"probe_ok": True,
                                               "probe_latency_ms": 10}), 0.0)

    def test_latency_when_probe_ran(self):
        pr._SHUAI_PROBE_DONE = True
        self.assertEqual(
            pr._shuai_probe_rank({"probe_ok": True, "probe_latency_ms": 250}),
            250.0)

    def test_unreachable_sorts_last(self):
        pr._SHUAI_PROBE_DONE = True
        self.assertEqual(
            pr._shuai_probe_rank({"probe_ok": False, "probe_latency_ms": None}),
            pr._SHUAI_PROBE_UNREACHABLE_RANK)


class RoutePreflightTest(unittest.TestCase):
    """Kosu oncesi kapi: dort rota da olu ise ceviri hic baslamamali."""

    def setUp(self):
        import subtitle_translator_gui as gui
        self.gui = gui
        pr.reset_shuai_route_probe()
        self.logs = []
        self.app = type("Stub", (), {})()
        self.app._log = lambda msg, level="info": self.logs.append((level, msg))
        self.app._set_phase = lambda *a, **k: None
        self.app._set_status = lambda *a, **k: None
        self.app._main_api_base_url = lambda: ROUTES[0]

    def tearDown(self):
        pr.reset_shuai_route_probe()

    def _patch(self, mapping):
        def _probe(route_url, attempts, timeout):
            return mapping[route_url]
        return mock.patch.object(pr, "_probe_one_shuai_route", _probe)

    def test_all_routes_down_blocks_the_run(self):
        mapping = {url: {"ok": False, "successes": 0, "attempts": 2,
                         "median_ms": None, "detail": "HTTP 502"}
                   for url in ROUTES}
        with self._patch(mapping):
            ok = self.gui.App._shuai_route_preflight(self.app)
        self.assertFalse(ok)
        self.assertTrue(any(level == "err" for level, _ in self.logs))

    def test_one_live_route_lets_the_run_start(self):
        mapping = {url: {"ok": False, "successes": 0, "attempts": 2,
                         "median_ms": None, "detail": "HTTP 502"}
                   for url in ROUTES}
        mapping[ROUTES[2]] = {"ok": True, "successes": 2, "attempts": 2,
                              "median_ms": 310, "detail": ""}
        with self._patch(mapping):
            ok = self.gui.App._shuai_route_preflight(self.app)
        self.assertTrue(ok)
        joined = " ".join(msg for _level, msg in self.logs)
        self.assertIn("1/4", joined)
        # Secili ana rota olu: kullanici uyarilmali.
        self.assertTrue(any(level == "warn" and "yanıt vermiyor" in msg
                            for level, msg in self.logs))

    def test_probe_failure_does_not_block_the_run(self):
        def _boom(route_url, attempts, timeout):
            raise RuntimeError("olcum patladi")
        with mock.patch.object(pr, "probe_shuai_routes",
                               mock.Mock(side_effect=RuntimeError("patladi"))):
            ok = self.gui.App._shuai_route_preflight(self.app)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
