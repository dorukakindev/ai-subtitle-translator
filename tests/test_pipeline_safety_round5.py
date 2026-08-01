import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui
import hybrid_translate as ht
from subtitle_formats import get_subtitle_files


class BatchWriteGuardTests(unittest.TestCase):
    def test_rejects_changed_source_and_changed_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "source.srt"
            out = root / "target.srt"
            src.write_text("old", encoding="utf-8")
            expected = gui._file_content_sha256(src)
            baseline = gui._file_state_signature(out)
            self.assertEqual(
                gui._batch_write_guard_reason(src, out, expected, baseline), "")

            src.write_text("new", encoding="utf-8")
            self.assertEqual(
                gui._batch_write_guard_reason(src, out, expected, baseline),
                "source_changed")

            expected = gui._file_content_sha256(src)
            out.write_text("newer final", encoding="utf-8")
            self.assertEqual(
                gui._batch_write_guard_reason(src, out, expected, baseline),
                "output_changed")

    def test_output_source_fingerprint_rejects_stale_same_id_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "Raporlar"
            src = root / "source.srt"
            out = root / "target.srt"
            src.write_text("first", encoding="utf-8")
            out.write_text("translated", encoding="utf-8")
            gui._write_output_source_fingerprint(
                report, out, gui._file_content_sha256(src))
            self.assertTrue(gui._output_matches_source_fingerprint(report, out, src))
            src.write_text("changed", encoding="utf-8")
            self.assertFalse(gui._output_matches_source_fingerprint(report, out, src))


class RunRecordFailureTests(unittest.TestCase):
    def test_partial_report_remains_error(self):
        source = str(Path("film.srt").absolute())
        record = {
            "files": {source: {"status": "running", "phase": "Yazılıyor"}},
            "fixes_applied": 0,
            "reports": [],
        }
        stub = SimpleNamespace(
            _run_record_lock=threading.RLock(),
            _active_run_record=record,
        )
        with patch.object(gui, "atomic_write_json"):
            gui.App._record_quality_report(
                stub,
                [{"name": "film.srt", "source_path": source,
                  "run_status": "error"}],
                [],
            )
        self.assertEqual(record["files"][source]["status"], "error")


class SceneLookaheadTests(unittest.TestCase):
    def _request_payloads(self, blocks):
        requests, _ = gui.build_requests(
            ["virtual.srt"], "English", "Turkish", "gpt-5.4",
            chunk_size=2, block_cache={"virtual.srt": blocks},
            context_lines=2, lookahead_lines=2, scene_gap_sec=4.0,
        )
        import json
        return [json.loads(req["body"]["messages"][1]["content"])
                for req in requests]

    def test_future_context_does_not_cross_scene_gap(self):
        payloads = self._request_payloads([
            ("1", "00:00:00,000 --> 00:00:01,000", "Wait."),
            ("2", "00:00:01,100 --> 00:00:02,000", "Listen."),
            ("3", "00:00:10,000 --> 00:00:11,000", "Good morning."),
        ])
        self.assertNotIn("next_ctx", payloads[0])

    def test_future_context_is_kept_inside_scene(self):
        payloads = self._request_payloads([
            ("1", "00:00:00,000 --> 00:00:01,000", "Wait."),
            ("2", "00:00:01,100 --> 00:00:02,000", "Listen."),
            ("3", "00:00:02,300 --> 00:00:03,000", "Come here."),
        ])
        self.assertEqual(payloads[0]["next_ctx"][0]["i"], "3")

    def test_hybrid_future_context_does_not_cross_scene_gap(self):
        cues = [
            SimpleNamespace(index=1, start="00:00:00,000", end="00:00:01,000", text="Wait."),
            SimpleNamespace(index=2, start="00:00:01,100", end="00:00:02,000", text="Listen."),
            SimpleNamespace(index=3, start="00:00:10,000", end="00:00:11,000", text="Good morning."),
        ]
        requests, _ = ht.build_batch_requests(
            cues, "system", "gpt-5.4", chunk_size=2,
            lookahead_lines=2, scene_gap_sec=4.0,
        )
        payload = json.loads(requests[0]["body"]["messages"][1]["content"])
        self.assertNotIn("next_ctx", payload)


class OutputRootExclusionTests(unittest.TestCase):
    def test_nested_active_output_root_is_not_reingested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "translated"
            output.mkdir()
            (root / "source.srt").write_text("source", encoding="utf-8")
            (output / "source.srt").write_text("translated", encoding="utf-8")
            files = get_subtitle_files(
                str(root), recursive=True, exclude_paths=[str(output)])
            self.assertEqual(files, [str(root / "source.srt")])


class FingerprintAndTargetLanguageTests(unittest.TestCase):
    def test_checkpoint_hash_includes_system_prompt(self):
        req_a = {"body": {"messages": [
            {"role": "system", "content": "rule A"},
            {"role": "user", "content": json.dumps({"tr": [{"i": 1, "t": "Hi"}]})},
        ]}}
        req_b = copy.deepcopy(req_a)
        req_b["body"]["messages"][0]["content"] = "rule B"
        self.assertNotEqual(
            gui.App._chunk_src_hash(req_a, "same"),
            gui.App._chunk_src_hash(req_b, "same"),
        )

    def test_non_turkish_output_skips_turkish_artifact_rewrites(self):
        self.assertEqual(
            ht._normalize_output_text("yada mummy mortuary", "German"),
            "yada mummy mortuary",
        )


if __name__ == "__main__":
    unittest.main()
