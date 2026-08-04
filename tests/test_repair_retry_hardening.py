import ast
import inspect
import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


_TS = "00:00:01,000 --> 00:00:02,000"


def _response(items):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(items, ensure_ascii=False)))],
        usage=None,
    )


class LicensedIdentityRepairTest(unittest.TestCase):
    def test_locked_latin_identity_is_not_missing(self):
        locked = {"coitus interruptus": "coitus interruptus"}
        blocks = [("715", _TS, "Coitus interruptus.")]
        with patch("subtitle_translator_gui._safe_chat_create") as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, {"715": "Coitus interruptus."}, object(),
                "Portuguese", "Turkish", locked_terms=locked)

        self.assertEqual(result, blocks)
        self.assertEqual(repaired, 0)
        create.assert_not_called()
        self.assertEqual(gui._partial_missing_translation_ids(
            blocks, {"715": "Coitus interruptus."},
            [("715", _TS, "Coitus interruptus.")],
            locked_terms=locked, source_language="Portuguese"), [])

    def test_repeated_locked_latin_identity_is_not_missing(self):
        source = "Mea culpa, mea culpa, mea culpa!"
        locked = {"Mea culpa": "Mea culpa"}
        blocks = [("57", _TS, source)]
        with patch("subtitle_translator_gui._safe_chat_create") as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, {"57": source}, object(), "English", "Turkish",
                locked_terms=locked)

        self.assertEqual(result, blocks)
        self.assertEqual(repaired, 0)
        create.assert_not_called()
        self.assertEqual(gui._partial_missing_translation_ids(
            blocks, {"57": source}, [("57", _TS, source)],
            locked_terms=locked, source_language="English"), [])

    def test_magna_cum_laude_is_not_english_residue(self):
        source = (
            "Dr. Genoves has three international doctorates, "
            "two of them magna cum laude")
        candidate = (
            "Dr. Genoves'in üç uluslararası doktora derecesi var; "
            "ikisi magna cum laude")
        self.assertFalse(ht.has_source_english_overlap(source, candidate))
        self.assertFalse(gui._is_untranslated(
            source, candidate, source_language="English"))

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=_response([{"i": "306", "t": candidate}])):
            result, repaired = gui._repair_untranslated_sync(
                [("306", _TS, "[HATA]")], {"306": source}, object(),
                "English", "Turkish")
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], candidate)

    def test_real_english_residue_still_fails(self):
        self.assertTrue(gui._is_untranslated(
            "Use the public phone box outside.",
            "Dışarıdaki public phone box kullan.",
            source_language="English"))
        self.assertTrue(gui._is_untranslated(
            "Please come here.", "Please come here.",
            source_language="English"))

    def test_greetings_and_all_caps_dialogue_are_not_name_exempt(self):
        for source in (
                "Good Morning", "Happy Birthday", "Merry Christmas",
                "Sweet Dreams", "GET OUT OF HERE!",
                "WHAT A GREAT ROOM THIS IS. WOW!"):
            with self.subTest(source=source):
                self.assertTrue(gui._is_untranslated(
                    source, source, source_language="English"))
        self.assertFalse(gui._is_untranslated(
            "ODDITIES SEASON FOUR", "ODDITIES SEASON FOUR",
            source_language="English"))


class PersistentRepairRetryTest(unittest.TestCase):
    def test_retry_sends_only_still_missing_cues(self):
        blocks = [("1", _TS, "[HATA]"), ("2", _TS, "[HATA]")]
        source = {"1": "First source.", "2": "Second source."}
        responses = [
            _response([{"i": "1", "t": "Birinci kaynak."}]),
            _response([{"i": "2", "t": "İkinci kaynak."}]),
        ]
        waits = []

        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=responses) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True)

        self.assertEqual(repaired, 2)
        self.assertEqual([row[2] for row in result], [
            "Birinci kaynak.", "İkinci kaynak."])
        first_payload = json.loads(
            create.call_args_list[0].kwargs["messages"][1]["content"])
        second_payload = json.loads(
            create.call_args_list[1].kwargs["messages"][1]["content"])
        self.assertEqual([str(item["i"]) for item in first_payload["tr"]], ["1", "2"])
        self.assertEqual([str(item["i"]) for item in second_payload["tr"]], ["2"])
        self.assertEqual(waits, [30])

    def test_exhaustion_uses_30_60_120_and_logs_reasons(self):
        log = MagicMock()
        waits = []
        response = _response([{"i": "8", "t": "Please come here."}])
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                [("8", _TS, "[HATA]")], {"8": "Please come here."},
                object(), "English", "Turkish", log_fn=log,
                retry_wait_fn=lambda delay, _cancelled: waits.append(delay) or True)

        self.assertEqual(create.call_count, 4)
        self.assertEqual(waits, [30, 60, 120])
        self.assertEqual(repaired, 0)
        self.assertEqual(result[0][2], "[HATA]")
        log_text = " ".join(str(call.args[0]) for call in log.call_args_list)
        self.assertIn("Onarım reddi #8", log_text)
        self.assertIn("identical_source", log_text)
        self.assertIn("deneme 4/4", log_text)

    def test_cancel_during_retry_wait_prevents_next_request(self):
        waits = []

        def wait(delay, _cancelled):
            waits.append(delay)
            return delay < 60

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=SimpleNamespace(choices=[], usage=None)) as create:
            gui._repair_untranslated_sync(
                [("1", _TS, "[HATA]")], {"1": "Translate me."},
                object(), "English", "Turkish", retry_wait_fn=wait)

        self.assertEqual(create.call_count, 2)
        self.assertEqual(waits, [30, 60])

    def test_permanent_http_400_stops_all_batches(self):
        class BadRequest(RuntimeError):
            status_code = 400

        blocks = [
            (str(idx), _TS, "[HATA]") for idx in range(1, 31)
        ]
        source = {
            str(idx): f"Source dialogue {idx}." for idx in range(1, 31)
        }
        permanent = MagicMock()
        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=BadRequest("invalid request")) as create:
            gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                permanent_failure_cb=permanent,
                retry_wait_fn=lambda _delay, _cancelled: True)

        self.assertEqual(create.call_count, 1)
        permanent.assert_called_once_with()


class CueLocalLeakLicenseTest(unittest.TestCase):
    def test_neighbor_source_cannot_license_foreign_token(self):
        sources = {"1": "Buñuel arrived.", "2": "The girl arrived."}
        self.assertEqual(gui._chunk_leak_source_text(sources, "2"),
                         "The girl arrived.")
        self.assertTrue(ht.has_non_turkish_target_leak(
            "Buñuel geldi.", source_text=gui._chunk_leak_source_text(sources, "2")))


class RepairFlowParityTest(unittest.TestCase):
    def test_every_production_repair_call_passes_locked_terms(self):
        tree = ast.parse(inspect.getsource(gui))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "_repair_untranslated_sync"
        ]
        self.assertGreaterEqual(len(calls), 6)
        for call in calls:
            with self.subTest(line=call.lineno):
                self.assertIn("locked_terms", {
                    keyword.arg for keyword in call.keywords})

    def test_jsonl_import_uses_semantic_missing_scan_and_stops_before_write(self):
        source = inspect.getsource(gui.App._import_jsonl)
        scan_pos = source.find("missing_ids = _partial_missing_translation_ids(")
        stop_pos = source.find("if self._stop_flag:", scan_pos)
        write_pos = source.find("write_srt(out_path", stop_pos)
        self.assertTrue(0 <= scan_pos < stop_pos < write_pos)


class IdentityInterjectionRegressionTest(unittest.TestCase):
    def test_short_identity_interjections_are_valid_translations(self):
        self.assertEqual(gui._untranslated_reason("Hey, hey!", "Hey, hey!"), "")
        self.assertEqual(gui._untranslated_reason("Jack, hey.", "Jack, hey."), "")
        self.assertEqual(
            gui._untranslated_reason("Hello everyone.", "Hello everyone."),
            "identical_source",
        )
        self.assertEqual(
            gui._untranslated_reason("No, no!", "No, no!"),
            "identical_source",
        )

    def test_real_repair_flow_accepts_identity_interjections_without_retry(self):
        source = {"96": "Hey, hey!", "981": "Jack, hey.", "1441": "Hey, hey."}
        blocks = [(idx, _TS, "[HATA]") for idx in source]
        response = _response([
            {"i": "96", "t": "Hey, hey!"},
            {"i": "981", "t": "Jack, hey."},
            {"i": "1441", "t": "Hey, hey."},
        ])

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, source, object(), "English", "Turkish",
                retry_wait_fn=lambda *_args: self.fail("retry should not run"))

        self.assertEqual(repaired, 3)
        self.assertEqual([text for _idx, _ts, text in result], list(source.values()))
        self.assertEqual(create.call_count, 1)
        self.assertEqual(gui._partial_missing_translation_ids(
            result, source, result, source_language="English"), [])


if __name__ == "__main__":
    unittest.main()
