# -*- coding: utf-8 -*-
"""Yardimci roller, kendi ayari yoksa ana cevirinin anahtarini devralir.

Eskiden ana hat ile yardimci farkli servise bakiyorsa anahtar bos donuyor
(fail-closed) ve kullanici her rol icin ayri profil girmek zorunda kaliyordu.
Artik anahtar VE adres birlikte devralindigi icin bir anahtar yine yalnizca
kendi servisine gonderiliyor.
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value


def _stub(*, helper_url="https://api.shuaiapi.com/v1",
          main_url="https://api.openai.com/v1", main_key="ana-anahtar",
          assignment=None, profiles=None, model_label="GPT-5.4 (Reseller)",
          role_key="", provider="openai"):
    app = types.SimpleNamespace()
    app._api_key_assignments = {"analysis": assignment} if assignment else {}
    app._api_key_profiles = profiles if profiles is not None else {}
    app.helper_model_vars = {"analysis": _Var(model_label)}
    app.helper_role_key_vars = {"analysis": _Var(role_key)}
    app._is_custom_helper_label = lambda label: label == "Özel (Custom)"
    app._get_current_helper_provider = lambda role: provider
    app._helper_model_config = lambda role: types.SimpleNamespace(
        base_url=helper_url, provider=provider)
    app._main_api_base_url = lambda: main_url
    app._main_api_key = lambda: main_key
    return app


class HelperFallsBackToMainTest(unittest.TestCase):
    def test_different_service_inherits_main(self):
        self.assertTrue(gui.App._helper_falls_back_to_main(_stub(), "analysis"))

    def test_same_host_keeps_existing_path(self):
        app = _stub(helper_url="https://api.shuaiapi.com/v1",
                    main_url="https://api.shuaiapi.com/v1")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_two_shuai_routes_count_as_one_service(self):
        app = _stub(helper_url="https://api.shuaiapi.com/v1",
                    main_url="https://oai.sb/v1")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_official_openai_helper_uses_its_own_key(self):
        app = _stub(helper_url="https://api.openai.com/v1",
                    main_url="https://api.shuaiapi.com/v1")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_explicit_profile_wins(self):
        app = _stub(assignment="p1", profiles={"p1": {}})
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_explicit_role_key_wins(self):
        app = _stub(role_key="kendi-anahtari")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_custom_helper_wins(self):
        app = _stub(model_label="Özel (Custom)")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_anthropic_helper_is_untouched(self):
        app = _stub(provider="anthropic")
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))

    def test_without_a_main_key_there_is_nothing_to_inherit(self):
        self.assertFalse(
            gui.App._helper_falls_back_to_main(_stub(main_key=""), "analysis"))

    def test_broken_resolvers_do_not_crash(self):
        app = _stub()

        def boom(*args, **kwargs):
            raise RuntimeError("patladi")
        app._main_api_base_url = boom
        self.assertFalse(gui.App._helper_falls_back_to_main(app, "analysis"))


class HelperBaseUrlTest(unittest.TestCase):
    def test_inherited_role_uses_the_main_endpoint(self):
        app = _stub()
        app._active_snapshot = {}
        url = gui.App._helper_api_base_url(app, "analysis")
        self.assertEqual(url, "https://api.openai.com/v1")

    def test_snapshot_value_still_wins_on_worker_threads(self):
        import threading
        app = _stub()
        app._active_snapshot = {"helper_urls": {"analysis": "https://kayitli/v1"}}
        seen = {}

        def _worker():
            seen["url"] = gui.App._helper_api_base_url(app, "analysis")
        thread = threading.Thread(target=_worker)
        thread.start()
        thread.join()
        self.assertEqual(seen["url"], "https://kayitli/v1")


if __name__ == "__main__":
    unittest.main()
