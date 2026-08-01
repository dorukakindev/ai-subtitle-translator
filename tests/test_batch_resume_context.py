import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class BatchRunContextTest(unittest.TestCase):
    def test_context_is_versioned_and_contains_no_credentials(self):
        snapshot = {
            "tgt_lang": "Turkish",
            "main_model_name": "gpt-5.4",
            "critic": True,
            "helper_models": {"critic": "gpt-5.4-mini"},
            "helper_keys": {"critic": "secret-helper"},
            "main_api_key": "secret-main",
        }
        context = gui._batch_run_context(snapshot, api_key="secret-main")
        self.assertEqual(context["context_version"], 1)
        self.assertEqual(context["tgt_lang"], "Turkish")
        self.assertNotIn("main_api_key", context)
        self.assertNotIn("helper_keys", context)
        self.assertNotEqual(context["api_key_fingerprint"], "secret-main")

    def test_resume_merge_keeps_current_credentials(self):
        current = {
            "tgt_lang": "German",
            "main_api_key": "current-main",
            "helper_keys": {"critic": "current-helper"},
        }
        saved = {"context_version": 1, "tgt_lang": "Turkish", "critic": True}
        merged = gui._merge_batch_resume_snapshot(current, saved)
        self.assertEqual(merged["tgt_lang"], "Turkish")
        self.assertEqual(merged["main_api_key"], "current-main")
        self.assertEqual(merged["helper_keys"]["critic"], "current-helper")


class RegularBatchResumeIsolationTest(unittest.TestCase):
    @staticmethod
    def _request(cid):
        return {
            "custom_id": cid,
            "body": {"messages": [{"role": "system", "content": "x"},
                                    {"role": "user", "content": "{}"}]},
        }

    def _app(self, writes, cleared):
        app = SimpleNamespace(
            _main_api_base_url=lambda: "https://example.test/v1",
            output_var=SimpleNamespace(get=lambda: "current-out"),
            src_var=SimpleNamespace(get=lambda: "English"),
            tgt_var=SimpleNamespace(get=lambda: "German"),
            _main_model_name=lambda: "current-model",
            _stop_flag=False,
            _register_batch=lambda *args: None,
            _unregister_batch=lambda *args: None,
            _wait_batch=lambda _client, bid, *_args, **_kwargs: (
                {"c1" if bid == "batch_one" else "c2": "[]"}, True),
            _retry_hata=lambda *args, **kwargs: set(),
            _write_results=lambda *args, **kwargs: writes.append(
                (args, kwargs, app._active_snapshot["tgt_lang"])) or True,
            _log=lambda *args, **kwargs: None,
            _max_retry=1,
            _active_snapshot={
                "tgt_lang": "German", "main_api_key": "live-key",
                "helper_keys": {"critic": "live-helper"},
            },
            _frozen_run_var_getters=[],
            _save_quality_report=lambda *args, **kwargs: None,
            _clear_batch_recovery=lambda bids: cleared.extend(bids),
            _set_running=lambda value: None,
        )
        return app

    def _fmap(self, run_id, cid, output_dir, target="Turkish"):
        return {
            "type": "regular",
            "run_id": run_id,
            "part_index": 0,
            "part_count": 1,
            "output_dir": output_dir,
            "output_paths": {f"{cid}.srt": f"{output_dir}/{cid}.srt"},
            "source_languages": {f"{cid}.srt": "English"},
            "schema_names": {f"{cid}.srt": "Film"},
            "source_hashes": {},
            "output_baselines": {},
            "run_context": {
                "context_version": 1, "src_lang": "English",
                "tgt_lang": target, "main_model_name": "saved-model",
                "critic": True,
                "api_key_fingerprint": __import__("hashlib").sha256(
                    b"live-key").hexdigest(),
            },
            "locked_terms_by_file": {f"{cid}.srt": {"Source": "Frozen"}},
            "requests": [self._request(cid)],
            "fmap": {cid: [[1, "00:00:01,000 --> 00:00:02,000", f"{cid}.srt"]]},
        }

    def test_different_runs_are_written_separately_with_saved_context(self):
        writes, cleared = [], []
        app = self._app(writes, cleared)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for bid, data in (
                ("batch_one", self._fmap("run-one", "c1", "out-one")),
                ("batch_two", self._fmap("run-two", "c2", "out-two", "Italian")),
            ):
                (root / f"batch_fmap_{bid}.json").write_text(
                    json.dumps(data), encoding="utf-8")
            with patch("subtitle_translator_gui.OpenAI", return_value=object()), \
                 patch("subtitle_translator_gui.state_path",
                       side_effect=lambda _file, name: root / name):
                gui.App._resume_batches(app, "live-key", ["batch_one", "batch_two"])

        self.assertEqual(len(writes), 2)
        self.assertEqual([item[0][2] for item in writes], ["out-one", "out-two"])
        self.assertEqual([item[2] for item in writes], ["Turkish", "Italian"])
        self.assertEqual(set(cleared), {"batch_one", "batch_two"})
        self.assertEqual(app._active_snapshot["tgt_lang"], "German")

    def test_missing_context_fails_closed_and_keeps_recovery(self):
        writes, cleared = [], []
        app = self._app(writes, cleared)
        data = self._fmap("legacy", "c1", "out")
        data.pop("run_context")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "batch_fmap_batch_one.json").write_text(
                json.dumps(data), encoding="utf-8")
            with patch("subtitle_translator_gui.OpenAI", return_value=object()), \
                 patch("subtitle_translator_gui.state_path",
                       side_effect=lambda _file, name: root / name):
                gui.App._resume_batches(app, "live-key", ["batch_one"])
        self.assertEqual(writes, [])
        self.assertEqual(cleared, [])

    def test_different_api_key_fails_closed_before_provider_call(self):
        writes, cleared = [], []
        app = self._app(writes, cleared)
        data = self._fmap("run-one", "c1", "out")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "batch_fmap_batch_one.json").write_text(
                json.dumps(data), encoding="utf-8")
            with patch("subtitle_translator_gui.OpenAI") as openai, \
                 patch("subtitle_translator_gui.state_path",
                       side_effect=lambda _file, name: root / name):
                gui.App._resume_batches(app, "different-key", ["batch_one"])
        openai.assert_not_called()
        self.assertEqual(writes, [])
        self.assertEqual(cleared, [])


if __name__ == "__main__":
    unittest.main()
