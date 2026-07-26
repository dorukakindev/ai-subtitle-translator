import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


def _response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
        )],
        usage=None,
    )


class SemanticClusterBuilderTest(unittest.TestCase):
    def test_changed_cue_gets_two_neighbor_context(self):
        translations = ["Bir.", "İki.", "Üç.", "Dört.", "Beş.", "Altı."]
        blocks = [
            (str(i), f"00:00:0{i} --> 00:00:0{i + 1}", translations[i - 1])
            for i in range(1, 7)
        ]
        sources = ["First.", "Second.", "Third.", "Fourth.", "Fifth.", "Sixth."]
        src_map = {str(i): sources[i - 1] for i in range(1, 7)}

        clusters = ht.build_semantic_reconciliation_clusters(
            src_map, blocks, changed_ids={"3"}
        )

        self.assertEqual(len(clusters), 1)
        self.assertEqual(
            [item["id"] for item in clusters[0]["items"]],
            ["1", "2", "3", "4", "5"],
        )
        suspect = next(item for item in clusters[0]["items"] if item["id"] == "3")
        self.assertIn("POST_PASS_CHANGED", suspect["reasons"])

    def test_neighbor_repeat_is_selected_without_changed_ids(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Merhaba."),
            ("2", "00:00:02 --> 00:00:03", "Merhaba."),
            ("3", "00:00:03 --> 00:00:04", "Sonra."),
        ]
        src_map = {"1": "Hello.", "2": "How are you?", "3": "Then."}

        clusters = ht.build_semantic_reconciliation_clusters(src_map, blocks)

        self.assertEqual(len(clusters), 1)
        reasons = {
            item["id"]: item["reasons"]
            for item in clusters[0]["items"] if item["suspect"]
        }
        self.assertTrue(any("NEIGHBOR_ECHO" in values for values in reasons.values()))

    def test_near_homophone_wordplay_is_selected_from_source(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Tahtaya yaz."),
            ("2", "00:00:02 --> 00:00:03", "Sıkıldım."),
            ("3", "00:00:03 --> 00:00:04", "Devam et."),
        ]
        src_map = {
            "1": "Write it on the board.",
            "2": "I am bored.",
            "3": "Go on.",
        }

        clusters = ht.build_semantic_reconciliation_clusters(src_map, blocks)

        self.assertEqual(len(clusters), 1)
        suspects = {
            item["id"]: item["reasons"]
            for item in clusters[0]["items"] if item["suspect"]
        }
        self.assertIn("SOURCE_WORDPLAY_RISK", suspects["1"])
        self.assertIn("SOURCE_WORDPLAY_RISK", suspects["2"])

    def test_dense_suspects_stay_bounded_and_non_overlapping(self):
        blocks = [
            (str(i), f"00:00:{i:02d} --> 00:00:{i + 1:02d}", f"Çeviri {i}.")
            for i in range(1, 31)
        ]
        src_map = {str(i): f"Source {i}." for i in range(1, 31)}

        clusters = ht.build_semantic_reconciliation_clusters(
            src_map, blocks, changed_ids={str(i) for i in range(1, 31)}
        )

        seen = set()
        for cluster in clusters:
            ids = {item["id"] for item in cluster["items"]}
            self.assertLessEqual(len(ids), 12)
            self.assertFalse(seen & ids)
            seen |= ids


class SemanticReconciliationPassTest(unittest.TestCase):
    def test_valid_source_driven_retranslation_is_applied(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Merhaba."),
            ("2", "00:00:02 --> 00:00:03", "Merhaba."),
        ]
        src_map = {"1": "Hello.", "2": "How are you?"}
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "2", "text": "Nasılsın?", "reason": "duplicate meaning"}],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response(payload)) as chat:
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"2"}
            )

        self.assertEqual(result[1][2], "Nasılsın?")
        self.assertEqual(stats["fixed"], 1)
        self.assertEqual(stats["rejected"], 0)
        self.assertIn("untrusted data", chat.call_args.kwargs["messages"][0]["content"])
        self.assertEqual(
            stats["details"][0]["changes"]["2"]["source"], "How are you?"
        )

    def test_one_unsafe_fix_rejects_the_whole_cluster(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Merhaba."),
            ("2", "00:00:02 --> 00:00:03", "12 tane var."),
        ]
        src_map = {"1": "How are you?", "2": "We have 12."}
        payload = [{
            "cluster": "c1",
            "fixes": [
                {"id": "1", "text": "Nasılsın?", "reason": "meaning"},
                {"id": "2", "text": "13 tane var.", "reason": "number"},
            ],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1", "2"}
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["rejected"], 1)

    def test_duplicate_cluster_response_is_fail_closed(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Merhaba.")]
        src_map = {"1": "How are you?"}
        item = {
            "cluster": "c1",
            "fixes": [{"id": "1", "text": "Nasılsın?", "reason": "meaning"}],
        }

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response([item, item])):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"}
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["rejected"], 1)


class SemanticGuiIntegrationTest(unittest.TestCase):
    def test_wrapper_runs_after_backtranslation_and_mutates_in_place(self):
        app = gui.App.__new__(gui.App)
        app.semantic_reconcile_var = SimpleNamespace(get=lambda: True)
        app.backtrans_var = SimpleNamespace(get=lambda: False)
        app.src_var = SimpleNamespace(get=lambda: "English")
        app.tgt_var = SimpleNamespace(get=lambda: "Turkish")
        app._log = MagicMock()
        app._helper_api_key = MagicMock(return_value="k")
        app._helper_api_base_url = MagicMock(return_value="https://example.test/v1")
        app._helper_api_model = MagicMock(return_value="m")
        app._token_callback_for_model = MagicMock(return_value=MagicMock())
        blocks = [("1", "00:00:01 --> 00:00:02", "Eski.")]
        stats = {
            "clusters": 1, "suspects": 1, "proposed": 1,
            "fixed": 1, "rejected": 0,
            "details": [{"cluster": "c1", "status": "applied", "ids": ["1"]}],
        }

        with patch("hybrid_translate.semantic_reconciliation_pass",
                   return_value=([("1", blocks[0][1], "Yeni.")], stats)), \
             patch("builtins.open", mock_open()):
            fixed = app._run_final_semantic_checks(
                "out.srt", {"1": "Source."}, blocks, changed_ids={"1"}
            )

        self.assertEqual(fixed, 1)
        self.assertEqual(blocks[0][2], "Yeni.")

    def test_worker_uses_snapshot_toggle(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {"semantic_reconcile": False}
        app.semantic_reconcile_var = MagicMock()

        with patch("subtitle_translator_gui.threading.current_thread"), \
             patch("subtitle_translator_gui.threading.main_thread") as main_thread:
            main_thread.return_value = object()
            self.assertFalse(app._semantic_reconcile_enabled())

        app.semantic_reconcile_var.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
