"""_json_repair_pass id doğrulaması (plans/s04e14-json-repair-shift-brief.md,
Görev 1) — JSON onarım yanıtı kaynağı görmeden üretildiği için id-kayması
riski taşır; onarım kabul edilmeden önce id kümesi doğrulanmalı.
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui
from tests._gui_app import make_app


def _req(cid, ids):
    """Beklenen id kümesi `ids` olan sahte bir istek — _expected_ids_from_req'in
    okuduğu gerçek payload biçimiyle (messages[1].content = {"tr":[{"i":..}]}) aynı."""
    payload = {"tr": [{"i": i, "t": f"src{i}"} for i in ids]}
    return {"custom_id": cid, "body": {"messages": [{}, {"content": json.dumps(payload)}]}}


class ExpectedIdsFromReqTest(unittest.TestCase):
    def test_extracts_ids_as_strings(self):
        req = _req("c1", [1, 2, 3])
        self.assertEqual(gui._expected_ids_from_req(req), {"1", "2", "3"})

    def test_malformed_req_returns_empty_set(self):
        self.assertEqual(gui._expected_ids_from_req({"body": {"messages": []}}), set())
        self.assertEqual(gui._expected_ids_from_req({}), set())


class ValidateRepairedChunkTest(unittest.TestCase):
    def test_matching_id_set_is_accepted(self):
        items = [{"i": 1, "t": "a"}, {"i": 2, "t": "b"}, {"i": 3, "t": "c"}]
        self.assertTrue(gui._validate_repaired_chunk(items, {"1", "2", "3"}))

    def test_foreign_id_outside_expected_set_is_rejected(self):
        # S04E14-tarzı kayma: onarım modeli beklenmeyen bir id uydurmuş.
        items = [{"i": 1, "t": "a"}, {"i": 2, "t": "b"}, {"i": 99, "t": "x"}]
        self.assertFalse(gui._validate_repaired_chunk(items, {"1", "2", "3"}))

    def test_duplicate_ids_rejected(self):
        # id sayımının şaştığının işareti — aynı id iki kez üretilmiş.
        items = [{"i": 1, "t": "a"}, {"i": 1, "t": "a-dup"}, {"i": 2, "t": "b"}]
        self.assertFalse(gui._validate_repaired_chunk(items, {"1", "2", "3"}))

    def test_low_coverage_rejected(self):
        # 40 id bekleniyor, yalnızca 3'ü var — anlamsız/boş onarım.
        expected = {str(i) for i in range(1, 41)}
        items = [{"i": 1, "t": "a"}, {"i": 2, "t": "b"}, {"i": 3, "t": "c"}]
        self.assertFalse(gui._validate_repaired_chunk(items, expected))

    def test_partial_but_reasonable_coverage_accepted(self):
        # Bazı id'lerin yanıtta hiç olmaması normal olabilir (kısmi kurtarma) —
        # kapsam oranı makulse (>=%50) kabul edilmeli, TAM eşleşme şartı yok.
        expected = {"1", "2", "3", "4"}
        items = [{"i": 1, "t": "a"}, {"i": 2, "t": "b"}]
        self.assertTrue(gui._validate_repaired_chunk(items, expected))

    def test_empty_expected_ids_rejected(self):
        # id çıkarılamadıysa doğrulama yapılamaz — güvenli tarafta kal.
        items = [{"i": 1, "t": "a"}]
        self.assertFalse(gui._validate_repaired_chunk(items, set()))

    def test_no_valid_id_fields_rejected(self):
        items = [{"t": "a"}, {"t": "b"}]
        self.assertFalse(gui._validate_repaired_chunk(items, {"1", "2"}))


class JsonRepairPassIntegrationTest(unittest.TestCase):
    """_json_repair_pass'i sahte bir OpenAI client ile uçtan uca test eder:
    onarım yanıtı id doğrulamasından geçmezse raw_map DEĞİŞMEMELİ."""

    def _fake_client(self, repair_content: str):
        class FakeMessage:
            def __init__(self, content):
                self.content = content

        class FakeChoice:
            def __init__(self, content):
                self.message = FakeMessage(content)

        class FakeResp:
            def __init__(self, content):
                self.choices = [FakeChoice(content)]
                self.usage = None

        class FakeCompletions:
            def create(_self, **kwargs):
                return FakeResp(repair_content)

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        return FakeClient()

    def setUp(self):
        self.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        self.app.update_idletasks()
        # Gerçek bir çeviri koşusunda _start() bunu sıfırlar; burada _json_repair_pass
        # doğrudan çağrıldığından (tam bir _start() akışı olmadan) elle eşdeğerini
        # kur — aksi hâlde tam test paketinde önceki bir CTk kök penceresinin kalıntı
        # durumu yüzünden getattr(self, "_cost_total", 0.0) varsayılana düşemeyebiliyor.
        self.app._cost_total = 0.0

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_repair_with_foreign_id_not_accepted(self):
        req = _req("c1", [1, 2, 3])
        raw_map = {"c1": "not valid json {{{"}
        client = self._fake_client('[{"i":1,"t":"a"},{"i":99,"t":"x"}]')
        self.app._json_repair_pass(client, raw_map, [req])
        self.assertEqual(raw_map["c1"], "not valid json {{{",
                         "id doğrulaması başarısız olan onarım raw_map'i değiştirmemeli")

    def test_repair_with_matching_ids_accepted(self):
        req = _req("c1", [1, 2, 3])
        raw_map = {"c1": "not valid json {{{"}
        fixed = '[{"i":1,"t":"a"},{"i":2,"t":"b"},{"i":3,"t":"c"}]'
        client = self._fake_client(fixed)
        self.app._json_repair_pass(client, raw_map, [req])
        self.assertEqual(raw_map["c1"], fixed)


class JsonRepairSourceContextTest(unittest.TestCase):
    def test_missing_source_items_are_sent_to_repair_model(self):
        req = _req("c1", [1, 2])
        raw_map = {"c1": '[{"i":1,"t":"bir"}' }
        app = SimpleNamespace(
            _main_model_name=lambda: "gpt-5.4-mini",
            _update_tokens=lambda *args, **kwargs: None,
            _log=lambda *args, **kwargs: None,
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":2,"t":"iki"}]'))], usage=None)
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            gui.App._json_repair_pass(app, object(), raw_map, [req])
        sent = json.loads(create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(
            sent["missing_source_items"], [{"i": 2, "t": "src2"}])


if __name__ == "__main__":
    unittest.main()
