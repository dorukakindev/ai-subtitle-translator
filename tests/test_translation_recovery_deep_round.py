import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


def _request(items):
    return {
        "custom_id": "chunk_0",
        "body": {
            "model": "gpt-5.4",
            "messages": [
                {"role": "developer", "content": "translate"},
                {"role": "user", "content": json.dumps({"tr": items})},
            ],
        },
    }


class MissingRepairUnitsTest(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"i": 1, "t": "I want"},
            {"i": 2, "t": "to leave."},
            {"i": 3, "t": "Now."},
        ]
        self.groups = [{"id": "g1", "items": [1, 2]}]

    def test_complete_fragment_sentence_is_repaired_as_one_unit(self):
        units, deferred = gui._missing_repair_units(
            self.items, self.groups, self.items[:2])
        self.assertEqual([[item["i"] for item in unit] for unit in units], [[1, 2]])
        self.assertEqual(deferred, set())

    def test_partial_fragment_sentence_is_reported_not_retranslated_in_isolation(self):
        units, deferred = gui._missing_repair_units(
            self.items, self.groups, [self.items[0]])
        self.assertEqual(units, [])
        self.assertEqual(deferred, {"1"})

    def test_unrelated_missing_cue_remains_single_cue_repair(self):
        units, deferred = gui._missing_repair_units(
            self.items, self.groups, [self.items[2]])
        self.assertEqual([[item["i"] for item in unit] for unit in units], [[3]])
        self.assertEqual(deferred, set())

    def test_resend_keeps_a_whole_fragment_sentence_in_one_request(self):
        request = _request(self.items)
        payload = json.loads(request["body"]["messages"][1]["content"])
        payload["sentence_groups"] = self.groups
        request["body"]["messages"][1]["content"] = json.dumps(payload)
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = MagicMock()
        raw = json.dumps([
            {"i": 1, "t": "[HATA]"},
            {"i": 2, "t": "[HATA]"},
            {"i": 3, "t": "Şimdi."},
        ])

        with patch.object(gui, "_safe_chat_create",
                          side_effect=gui.RequestCancelled("stop")) as send:
            gui.App._resend_missing_blocks(app, object(), request, raw)

        sent = json.loads(send.call_args.kwargs["messages"][1]["content"])
        self.assertEqual([item["i"] for item in sent["tr"]], [1, 2])
        self.assertEqual(sent["sentence_groups"], self.groups)

    def test_resend_does_not_send_an_isolated_fragment_member(self):
        request = _request(self.items)
        payload = json.loads(request["body"]["messages"][1]["content"])
        payload["sentence_groups"] = self.groups
        request["body"]["messages"][1]["content"] = json.dumps(payload)
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = MagicMock()
        raw = json.dumps([
            {"i": 1, "t": "[HATA]"},
            {"i": 2, "t": "Ayrılmak istiyorum."},
            {"i": 3, "t": "Şimdi."},
        ])

        with patch.object(gui, "_safe_chat_create") as send:
            result = gui.App._resend_missing_blocks(app, object(), request, raw)

        send.assert_not_called()
        result_by_id = {item["i"]: item["t"] for item in json.loads(result)}
        self.assertEqual(result_by_id[1], "[HATA]")
        self.assertIn("teslim incelemesine", str(app._log.call_args_list))


class PartialTranslationRetryTest(unittest.TestCase):
    def test_partial_json_never_retries_the_complete_chunk(self):
        items = [
            {"i": "1", "t": "One."},
            {"i": "2", "t": "Two."},
            {"i": "3", "t": "Three."},
        ]
        raw_map = {
            "chunk_0": json.dumps([
                {"i": "1", "t": "Bir."},
                {"i": "2", "t": "Iki."},
            ])
        }
        partial = json.dumps([
            {"i": "1", "t": "Bir."},
            {"i": "2", "t": "Iki."},
            {"i": "3", "t": "[HATA]"},
        ])
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._json_repair_pass = MagicMock()
        app._resend_missing_blocks = MagicMock(return_value=partial)
        app._log = MagicMock()

        with patch.object(
                gui, "_safe_chat_create",
                side_effect=AssertionError("whole chunk was retried")) as create:
            unresolved = gui.App._retry_hata(
                app, object(), raw_map, [_request(items)], max_rounds=2)

        create.assert_not_called()
        self.assertEqual(unresolved, {"chunk_0"})
        result = {row["i"]: row["t"] for row in json.loads(raw_map["chunk_0"])}
        self.assertEqual(result["1"], "Bir.")
        self.assertEqual(result["2"], "Iki.")
        self.assertEqual(result["3"], "[HATA]")


class BatchRecoveryMetadataTest(unittest.TestCase):
    def test_intent_cleanup_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            intent_directory = Path(tmpdir) / "intent.json"
            intent_directory.mkdir()
            logs = []

            ok = gui._unlink_batch_intent_nonfatal(
                intent_directory, lambda message, level: logs.append((message, level)))

            self.assertFalse(ok)
            self.assertTrue(intent_directory.is_dir())
            self.assertTrue(any(level == "warn" for _message, level in logs))

    def test_malformed_fmap_blocks_paid_part_resubmission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "batch_fmap_batch_bad.json").write_text(
                "{broken", encoding="utf-8")
            app = SimpleNamespace(_log=MagicMock())

            with patch.object(gui, "state_path", side_effect=lambda _f, name: root / name):
                result = gui.App._submit_missing_regular_batch_parts(
                    app, "key", ["batch_bad"])

            self.assertEqual(result, ["batch_bad"])
            self.assertTrue(any(
                "çoğaltmamak" in str(call.args[0])
                for call in app._log.call_args_list))

    def test_malformed_manifest_is_reported_without_resubmission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "batch_fmap_batch_ok.json").write_text(json.dumps({
                "type": "regular", "run_id": "run-a", "part_index": 0,
            }), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text("{broken", encoding="utf-8")
            app = SimpleNamespace(_log=MagicMock())

            with patch.object(gui, "state_path", side_effect=lambda _f, name: root / name), \
                    patch.object(gui, "_regular_batch_manifest_path", return_value=manifest):
                result = gui.App._submit_missing_regular_batch_parts(
                    app, "key", ["batch_ok"])

            self.assertEqual(result, ["batch_ok"])
            self.assertTrue(any(
                "manifesti okunamadı" in str(call.args[0])
                for call in app._log.call_args_list))


if __name__ == "__main__":
    unittest.main()
