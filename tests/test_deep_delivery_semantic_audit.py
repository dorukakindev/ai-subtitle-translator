import ast
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
            "fixes": [{
                "id": "1", "text": "Doğru çeviri.", "reason": "subject_swap",
                "confidence": 0.91,
            }],
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
        self.assertEqual(stats["details"][-1]["confidence"]["1"], 0.91)
        self.assertEqual(stats["cluster_context"]["c1"][0]["source"], "Correct source.")
        self.assertTrue(status["report_only"])
        self.assertEqual(status["suggested"], 1)

    def test_full_scan_records_complete_fragment_group_coverage(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Gitmem"),
            ("2", "00:00:02,000 --> 00:00:03,000", "gerekiyor."),
        ]
        src_map = {"1": "I need", "2": "to leave."}

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response([])), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m",
                apply_changes=False, target_coverage=1.0)

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fragment_groups_total"], 1)
        self.assertEqual(stats["fragment_groups_processed"], 1)
        self.assertEqual(stats["fragment_groups_incomplete"], [])

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

    def test_report_contains_neighbors_risk_confidence_critic_and_fragment_scope(self):
        blocks = [(str(i), "t", f"Mevcut {i}") for i in range(1, 5)]
        stats = {
            "clusters": 1, "api_requests": 1, "processed_cues": 4,
            "processed_coverage_pct": 100.0,
            "processed_ids": ["1", "2", "3", "4"],
            "sentence_groups_total": 1, "sentence_groups_processed": 1,
            "fragment_groups_total": 1, "fragment_groups_processed": 0,
            "fragment_groups_incomplete": [{
                "group": "fg_2_3", "items": ["2", "3"],
                "processed": ["2"], "missing": ["3"], "complete": False,
            }],
            "suggested": 1, "rejected": 0,
            "critic_status": {
                "suggested": 3, "rejected_count": 2, "changed": 0,
                "report_only": True, "rejected_reasons": {"source_modality": 2},
            },
            "alignment_findings": [{
                "type": "missing_dialogue", "idx": "4", "detail": "Missing source",
            }],
            "owner_mismatch_ids": ["3"],
            "cluster_context": {"c1": [
                {"id": "1", "source": "Before.", "translation": "Önce.",
                 "frag": "none", "suspect": False, "reasons": []},
                {"id": "2", "source": "He must", "translation": "O gitmek",
                 "frag": "start", "suspect": True, "reasons": ["SOURCE_MODALITY"]},
                {"id": "3", "source": "leave.", "translation": "isteyebilir.",
                 "frag": "end", "suspect": True, "reasons": ["SUBJECT_SWAP"]},
            ]},
            "details": [{
                "cluster": "c1", "status": "suggested", "ids": ["2", "3"],
                "reasons": {"2": "source_modality", "3": "subject_swap"},
                "confidence": {"2": 0.96, "3": 0.89},
                "changes": {
                    "2": {"source": "He must", "before": "O gitmek", "after": "Gitmek"},
                    "3": {"source": "leave.", "before": "isteyebilir.",
                          "after": "zorunda."},
                },
            }],
        }

        report = gui.build_deep_delivery_semantic_report(stats, blocks)

        self.assertIn("Guard reddi: 2 | Uygulanan: 0", report)
        self.assertIn("Eksik fragment fg_2_3", report)
        self.assertIn("missing_dialogue: cue=4", report)
        self.assertIn("yanlış cue içeriği adayları: 3", report)
        self.assertIn("En Riskli 20 Küme", report)
        self.assertIn("güven=%96", report)
        self.assertIn("[1] frag=none", report)
        self.assertIn("kaynak: Before.", report)
        self.assertIn("olumsuzluk/kip/zaman", report)
        self.assertIn("özne/nesne/kişi", report)


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
                critic_status={
                    "suggested": 2, "rejected_count": 1, "changed": 0,
                    "report_only": True,
                }, status_out=status)
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
        self.assertIn("Önerilen: 2 | Guard reddi: 1 | Uygulanan: 0", report_text)

    def test_all_four_delivery_flows_call_deep_audit(self):
        for name in (
            "_run_sync_hybrid", "_wait_batch_hybrid", "_write_results", "_run_hybrid",
        ):
            source = inspect.getsource(getattr(gui.App, name))
            self.assertIn("_maybe_deep_delivery_semantic_audit(", source, name)

    def test_every_gui_critic_call_is_forced_report_only(self):
        tree = ast.parse(inspect.getsource(gui))
        critic_calls = []
        report_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "critic_pass_with_helper":
                critic_calls.append(node)
            elif node.func.attr == "_write_critic_change_report":
                report_calls.append(node)
        self.assertEqual(len(critic_calls), 5)
        self.assertEqual(len(report_calls), 5)
        for call in critic_calls:
            keyword = next(
                (item for item in call.keywords if item.arg == "apply_changes"), None)
            self.assertIsNotNone(keyword)
            self.assertIsInstance(keyword.value, ast.Constant)
            self.assertIs(keyword.value.value, False)
        for call in report_calls:
            keyword = next(
                (item for item in call.keywords if item.arg == "report_only"), None)
            self.assertIsNotNone(keyword)
            self.assertIsInstance(keyword.value, ast.Constant)
            self.assertIs(keyword.value.value, True)


if __name__ == "__main__":
    unittest.main()
