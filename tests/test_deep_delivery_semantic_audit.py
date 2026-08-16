import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


def _response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=json.dumps(payload, ensure_ascii=False)))],
        usage=None,
    )


class DeepDeliverySemanticCoreTest(unittest.TestCase):
    def test_full_coverage_plan_contains_every_cue(self):
        blocks = [
            (str(i), f"00:00:{i:02d},000 --> 00:00:{i:02d},900", f"Çeviri {i}.")
            for i in range(1, 31)
        ]
        src_map = {str(i): f"Source sentence {i}." for i in range(1, 31)}

        clusters = ht.build_semantic_reconciliation_clusters(
            src_map, blocks, target_coverage=1.0)
        covered = {
            item["id"] for cluster in clusters for item in cluster["items"]
        }

        self.assertEqual(covered, set(src_map))

    def test_report_only_validates_suggestion_without_mutating_blocks(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Eski çeviri.")]
        src_map = {"1": "Correct source."}
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "1", "text": "Doğru çeviri.", "reason": "meaning"}],
        }]
        status = {}

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)), \
             patch("hybrid_translate.validate_semantic_reconciliation_candidate",
                   return_value=(True, "")), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                apply_changes=False, target_coverage=1.0, status_out=status,
                pass_label="Derin teslim anlam taraması",
                checkpoint_label="deep_delivery_semantic",
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["suggested"], 1)
        self.assertEqual(stats["details"][-1]["status"], "suggested")
        self.assertTrue(status["report_only"])
        self.assertEqual(status["suggested"], 1)

    def test_report_proves_start_middle_end_coverage(self):
        blocks = [(str(i), "t", f"Çeviri {i}") for i in range(1, 10)]
        stats = {
            "clusters": 3, "api_requests": 1, "processed_cues": 9,
            "processed_coverage_pct": 100.0,
            "processed_ids": [str(i) for i in range(1, 10)],
            "suggested": 0, "rejected": 0, "details": [],
        }

        report = gui.build_deep_delivery_semantic_report(stats, blocks)

        self.assertIn("Durum: TAM KAPSAM", report)
        self.assertIn("baş 3/3 (%100.0)", report)
        self.assertIn("orta 3/3 (%100.0)", report)
        self.assertIn("son 3/3 (%100.0)", report)
        self.assertIn("altyazı metnini değiştirmez", report)


class DeepDeliverySemanticGuiTest(unittest.TestCase):
    def test_wrapper_requests_full_report_only_coverage_and_writes_report(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {
            "deep_delivery_semantic": True,
            "src_lang": "English", "tgt_lang": "Turkish",
        }
        app._active_run_record = None
        app._helper_request_canceller = None
        app.deep_delivery_semantic_var = SimpleNamespace(get=lambda: True)
        app._log = MagicMock()
        app._set_phase = MagicMock()
        app._update_file_progress = MagicMock()
        app._helper_api_key = MagicMock(return_value="k")
        app._helper_api_base_url = MagicMock(return_value="https://example.test/v1")
        app._helper_api_model = MagicMock(return_value="m")
        app._run_scene_gap = MagicMock(return_value=3.0)
        app._get_locked_terms_dict = MagicMock(return_value={})
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Mevcut.")]
        stats = {
            "clusters": 1, "api_requests": 1, "processed_cues": 1,
            "processed_coverage_pct": 100.0, "processed_ids": ["1"],
            "suggested": 1, "rejected": 0,
            "details": [{
                "cluster": "c1", "status": "suggested", "ids": ["1"],
                "reasons": {"1": "meaning"},
                "changes": {"1": {
                    "source": "Source.", "before": "Mevcut.", "after": "Öneri.",
                }},
            }],
        }
        status = {}

        with tempfile.TemporaryDirectory() as tmp, \
             patch("hybrid_translate.semantic_reconciliation_pass",
                   return_value=(list(blocks), stats)) as semantic, \
             patch.object(gui.App, "_token_callback_for_pass", return_value=MagicMock()), \
             patch.object(gui.App, "_pass_progress_callback", return_value=None):
            out = Path(tmp) / "episode.srt"
            suggested = app._maybe_deep_delivery_semantic_audit(
                out, {"1": "Source."}, blocks, source_path="source.srt",
                status_out=status)
            report = out.parent / "Raporlar" / (
                "episode.derin_teslim_anlam_taramasi.txt")
            report_exists = report.exists()
            report_text = report.read_text(encoding="utf-8")

        self.assertEqual(suggested, 1)
        self.assertEqual(blocks[0][2], "Mevcut.")
        self.assertEqual(semantic.call_args.kwargs["target_coverage"], 1.0)
        self.assertFalse(semantic.call_args.kwargs["apply_changes"])
        self.assertEqual(
            semantic.call_args.kwargs["checkpoint_label"],
            "deep_delivery_semantic")
        self.assertTrue(status["coverage_complete"])
        self.assertTrue(report_exists)
        self.assertIn("mevcut: Mevcut.", report_text)

    def test_all_four_delivery_flows_call_deep_audit(self):
        for name in (
            "_run_sync_hybrid", "_wait_batch_hybrid", "_write_results", "_run_hybrid",
        ):
            source = inspect.getsource(getattr(gui.App, name))
            self.assertIn("_maybe_deep_delivery_semantic_audit(", source, name)


if __name__ == "__main__":
    unittest.main()
