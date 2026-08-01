import json
import tempfile
import threading
import unittest
from pathlib import Path
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
    def test_fragment_sentence_is_never_split_between_clusters(self):
        class Cue:
            def __init__(self, index, text):
                self.index = index
                self.text = text
                self.start = f"00:00:{index:02d},000"
                self.end = f"00:00:{index:02d},500"

        cues = [
            Cue(i, f"fragment {i}" + ("." if i == 8 else ","))
            for i in range(1, 9)
        ]
        blocks = [
            (str(i), f"00:00:{i:02d} --> 00:00:{i:02d}", f"Parça {i}")
            for i in range(1, 9)
        ]
        src_map = {str(cue.index): cue.text for cue in cues}

        clusters = ht.build_semantic_reconciliation_clusters(
            src_map, blocks, cues=cues, changed_ids={"1", "8"})

        containing = [
            cluster for cluster in clusters
            if {"1", "8"} & {item["id"] for item in cluster["items"]}
        ]
        self.assertEqual(len(containing), 1)
        self.assertEqual(
            [item["id"] for item in containing[0]["items"]],
            [str(i) for i in range(1, 9)],
        )
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
            self.assertTrue(set(cluster["suspect_ids"]).issubset(ids))
            seen |= ids
        self.assertEqual(
            {
                item["id"]
                for cluster in clusters
                for item in cluster["items"]
                if item["suspect"]
            },
            {str(i) for i in range(1, 31)},
        )

    def test_expanded_validator_reasons_are_selected(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Bozuk."),
            ("2", "00:00:02 --> 00:00:03", "Kalan."),
        ]
        src_map = {"1": "Broken.", "2": "Left."}
        reasons = {
            "1": {"GARBLE_TOKEN", "DANGLING_TURKISH_FRAGMENT"},
            "2": {"EN_TURKISH_SUFFIX_LEFTOVER", "SOURCE_LANG_LEFTOVER"},
        }

        with patch("hybrid_translate._semantic_reason_map", return_value=reasons):
            clusters = ht.build_semantic_reconciliation_clusters(src_map, blocks)

        selected = {
            item["id"]: set(item["reasons"])
            for cluster in clusters
            for item in cluster["items"]
            if item["suspect"]
        }
        self.assertEqual(selected["1"], reasons["1"])
        self.assertEqual(selected["2"], reasons["2"])

    def test_explicit_mixed_term_ids_are_selected(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Bir."),
            ("2", "00:00:02 --> 00:00:03", "İki."),
        ]
        src_map = {"1": "One.", "2": "Two."}

        with patch("hybrid_translate._semantic_reason_map", return_value={}):
            clusters = ht.build_semantic_reconciliation_clusters(
                src_map, blocks,
                extra_suspect_reasons={"2": {"MIXED_TERM_INCONSISTENCY"}},
            )

        suspect = next(
            item for item in clusters[0]["items"] if item["id"] == "2"
        )
        self.assertIn("MIXED_TERM_INCONSISTENCY", suspect["reasons"])

    def test_adaptive_review_reaches_requested_coverage_without_full_file(self):
        blocks = [
            (str(i), f"00:00:{i:02d} --> 00:00:{i + 1:02d}", f"Çeviri {i}.")
            for i in range(1, 101)
        ]
        src_map = {str(i): "Ordinary source." for i in range(1, 101)}

        with patch("hybrid_translate._semantic_reason_map", return_value={}), \
             patch("hybrid_translate._source_wordplay_risk_ids", return_value=set()):
            clusters = ht.build_semantic_reconciliation_clusters(
                src_map, blocks, target_coverage=0.65)

        covered = {
            item["id"] for cluster in clusters for item in cluster["items"]
        }
        reasons = {
            reason
            for cluster in clusters
            for item in cluster["items"]
            for reason in item["reasons"]
        }
        self.assertGreaterEqual(len(covered), 65)
        self.assertLess(len(covered), 100)
        self.assertIn("ADAPTIVE_COVERAGE_REVIEW", reasons)

    def test_mixed_term_helper_returns_concrete_cue_ids(self):
        clusters = {
            "Laboratory": [
                [("4", "Tedarik"), ("8", "Tedarik")],
                [("11", "Sağlama"), ("15", "Sağlama")],
            ],
            "Ambiguous": [
                [("20", "Bir"), ("21", "Bir")],
                [("22", "İki")],
            ],
        }

        with patch("subtitle_translator_gui._mixed_term_clusters",
                   return_value=clusters):
            suspects = gui._mixed_term_suspect_ids([], {})

        self.assertEqual(suspects, {"4", "8", "11", "15"})

class SemanticReconciliationPassTest(unittest.TestCase):
    def test_matching_scene_plan_is_injected_into_cluster_payload(self):
        blocks = [("7", "00:00:01 --> 00:00:02", "Onu geri ver.")]
        src_map = {"7": "Give it back."}
        scene_plan = [{
            "start": 5, "end": 9, "summary": "Ayla demands the key back.",
            "speakers": ["Ayla"], "speaker_goals": {"Ayla": "recover the key"},
            "referents": {"it": "the key"}, "tone": "angry",
        }]
        with patch("openai.OpenAI"), patch(
                "hybrid_translate._safe_chat_create", return_value=_response([])) as create:
            ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"7"},
                scene_plan=scene_plan)

        payload = json.loads(create.call_args.kwargs["messages"][1]["content"])
        item = payload["clusters"][0]["items"][0]
        self.assertEqual(item["scene"][0]["referents"]["it"], "the key")

    def test_file_analysis_context_is_injected_into_reconciler_prompt(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Sana söyledim.")]
        src_map = {"1": "I told you."}
        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response([])) as create:
            ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                analysis_context_hint="Ayşe, Mehmet'e siz diye hitap eder.",
            )
        prompt = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("FILE ANALYSIS CONTEXT", prompt)
        self.assertIn("Ayşe, Mehmet'e siz diye hitap eder.", prompt)

    def test_season_canon_hint_is_injected_into_reconciler_prompt(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Sana söyledim.")]
        src_map = {"1": "I told you."}
        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response([])) as create:
            ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                canon_hint="Alice → Bob: 'siz'",
            )
        prompt = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("SEASON CANON", prompt)
        self.assertIn("Alice → Bob: 'siz'", prompt)

    def test_missing_predicate_regression_is_rejected(self):
        ok, reason = ht.validate_semantic_reconciliation_candidate(
            "Kral Behemoth korunuyor...",
            "Kral Behemoth'un",
            source_text="The King Behemoth is protected...",
        )

        self.assertFalse(ok)
        self.assertEqual(reason, "missing_predicate")

    def test_unchanged_proposal_is_not_counted_or_rejected(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Zaten doğru.")]
        src_map = {"1": "Already correct."}
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "1", "text": " Zaten doğru. ", "reason": "none"}],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"}
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["proposed"], 0)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["rejected"], 0)
        self.assertEqual(stats["details"], [])

    def test_non_string_proposal_is_rejected_instead_of_stringified(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Doğru çeviri.")]
        src_map = {"1": "Correct translation."}
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "1", "text": None, "reason": "meaning"}],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"}
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["details"][-1]["reason"], "fix_id_or_text")

    def test_locked_term_cannot_be_removed(self):
        blocks = [(
            "1", "00:00:01 --> 00:00:02",
            "Biyoteknoloji Tedarik Laboratuvarı.",
        )]
        src_map = {"1": "Biotechnology Provision Laboratory."}
        payload = [{
            "cluster": "c1",
            "fixes": [{
                "id": "1",
                "text": "Biyoteknoloji Sağlama Laboratuvarı.",
                "reason": "terminology",
            }],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response(payload)) as chat:
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                locked_terms={
                    "Biotechnology Provision Laboratory":
                        "Biyoteknoloji Tedarik Laboratuvarı"
                },
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["details"][-1]["reason"], "locked_term_violation")
        self.assertIn(
            "Biotechnology Provision Laboratory -> "
            "Biyoteknoloji Tedarik Laboratuvarı",
            chat.call_args.kwargs["messages"][0]["content"],
        )

    def test_locked_term_split_across_cues_cannot_be_removed(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Yeni"),
            ("2", "00:00:02 --> 00:00:03", "York geldi."),
        ]
        src_map = {"1": "New", "2": "York arrived."}
        payload = [{
            "cluster": "c1",
            "fixes": [{
                "id": "2",
                "text": "Şehir geldi.",
                "reason": "wording",
            }],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"2"},
                locked_terms={"New York": "Yeni York"},
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["details"][-1]["reason"], "locked_term_violation")

    def test_malformed_fixes_are_reported_as_rejected(self):
        blocks = [("1", "00:00:01 --> 00:00:02", "Bir.")]
        src_map = {"1": "One."}
        payload = [{"cluster": "c1", "fixes": "not-a-list"}]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(stats["details"][-1]["reason"], "fix_shape")

    def test_locked_proper_name_suffix_cannot_be_changed(self):
        blocks = [(
            "1", "00:00:01 --> 00:00:02",
            "Kaori Sweet Seventeen'den verileri aktardım.",
        )]
        src_map = {"1": "I transferred the data from Kaori Sweet Seventeen."}
        payload = [{
            "cluster": "c1",
            "fixes": [{
                "id": "1",
                "text": "Kaori Sweet Seventeen'dan verileri aktardım.",
                "reason": "wording",
            }],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"},
                locked_terms={"Sweet Seventeen": "Sweet Seventeen"},
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["details"][-1]["reason"], "locked_term_violation")

    def test_reflow_does_not_bypass_semantic_rewrite_guard(self):
        blocks = [(
            "1", "00:00:01 --> 00:00:02",
            "Eski birinci satır.\nEski ikinci satır.",
        )]
        src_map = {"1": "A corrected subtitle over two lines."}
        payload = [{
            "cluster": "c1",
            "fixes": [{
                "id": "1",
                "text": "Düzeltilmiş altyazı iki satır boyunca akar.",
                "reason": "meaning",
            }],
        }]

        with patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)), \
             patch("hybrid_translate._semantic_reason_map", return_value={}):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m", changed_ids={"1"}
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["reflow_recovered"], 0)
        self.assertEqual(stats["details"][-1]["reason"], "semantic_rewrite_unverified")

    def test_unresolved_triggering_issue_rejects_cluster(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Tekrar."),
            ("2", "00:00:02 --> 00:00:03", "Tekrar."),
        ]
        src_map = {"1": "First meaning.", "2": "Second meaning."}
        cluster = {
            "cluster": "c1",
            "items": [
                {"id": "1", "source": src_map["1"], "translation": "Tekrar.",
                 "suspect": True, "reasons": ["NEIGHBOR_ECHO"]},
                {"id": "2", "source": src_map["2"], "translation": "Tekrar.",
                 "suspect": True, "reasons": ["NEIGHBOR_ECHO"]},
            ],
            "suspect_ids": ["1", "2"],
        }
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "2", "text": "İkinci anlam.", "reason": "partial"}],
        }]

        with patch("hybrid_translate.build_semantic_reconciliation_clusters",
                   return_value=[cluster]), \
             patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", return_value=_response(payload)), \
             patch("hybrid_translate.validate_semantic_reconciliation_candidate",
                   return_value=(True, "")), \
             patch("hybrid_translate._semantic_reason_map",
                   side_effect=[
                       {"1": {"NEIGHBOR_ECHO"}, "2": {"NEIGHBOR_ECHO"}},
                       {"1": {"NEIGHBOR_ECHO"}},
                   ]):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m"
            )

        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["details"][-1]["reason"], "unresolved_cluster_issue")

    def test_permanent_auth_error_stops_remaining_batches(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Bir."),
            ("2", "00:00:02 --> 00:00:03", "İki."),
        ]
        src_map = {"1": "One.", "2": "Two."}
        clusters = [
            {
                "cluster": f"c{i}",
                "items": [{"id": str(i), "source": src_map[str(i)],
                           "translation": blocks[i - 1][2], "suspect": True,
                           "reasons": ["POST_PASS_CHANGED"]}],
                "suspect_ids": [str(i)],
            }
            for i in (1, 2)
        ]
        error = RuntimeError(
            "Error code: 401 - {'code': 'invalid_api_key'}"
        )

        with patch("hybrid_translate.build_semantic_reconciliation_clusters",
                   return_value=clusters), \
             patch("hybrid_translate._semantic_cluster_batches",
                   return_value=[[clusters[0]], [clusters[1]]]), \
             patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   side_effect=error) as chat:
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m"
            )

        self.assertEqual(result, blocks)
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(stats["rejected"], 2)
        self.assertEqual(stats["processed_cues"], 0)
        self.assertEqual(stats["processed_coverage_pct"], 0.0)
        self.assertEqual(stats["details"][-1]["reason"], "permanent_api_error")
        self.assertEqual(stats["details"][-1]["count"], 1)

    def test_plan_logs_real_coverage_and_request_count(self):
        blocks = [
            (str(i), f"00:00:{i:02d} --> 00:00:{i + 1:02d}", f"Çeviri {i}.")
            for i in range(1, 101)
        ]
        src_map = {str(i): f"Source {i}." for i in range(1, 101)}
        clusters = []
        for number, start in enumerate((1, 31), 1):
            items = [
                {"id": str(i), "source": src_map[str(i)],
                 "translation": blocks[i - 1][2], "suspect": True,
                 "reasons": ["POST_PASS_CHANGED"]}
                for i in range(start, start + 30)
            ]
            clusters.append({
                "cluster": f"c{number}",
                "items": items,
                "suspect_ids": [item["id"] for item in items],
            })
        log = MagicMock()

        with patch("hybrid_translate.build_semantic_reconciliation_clusters",
                   return_value=clusters):
            _result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="", model="m", log_fn=log
            )

        self.assertEqual(stats["covered_cues"], 60)
        self.assertEqual(stats["coverage_pct"], 60.0)
        self.assertEqual(stats["api_requests"], 2)
        message, level = log.call_args.args
        self.assertIn("60/100 cue (%60.0)", message)
        self.assertIn("2 ek API isteği", message)
        self.assertEqual(level, "warn")

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

    def test_rejects_new_issue_on_neighbor_just_outside_cluster(self):
        blocks = [
            ("0", "00:00:00 --> 00:00:01", "Merhaba."),
            ("1", "00:00:01 --> 00:00:02", "Selam."),
            ("2", "00:00:02 --> 00:00:03", "Dünya."),
        ]
        src_map = {"0": "Hello.", "1": "Greetings.", "2": "World."}
        cluster = {
            "cluster": "c1",
            "items": [
                {"id": "1", "source": "Greetings.", "translation": "Selam.",
                 "suspect": True, "reasons": ["POST_PASS_CHANGED"]},
                {"id": "2", "source": "World.", "translation": "Dünya.",
                 "suspect": False, "reasons": []},
            ],
            "suspect_ids": ["1"],
        }
        payload = [{
            "cluster": "c1",
            "fixes": [{"id": "1", "text": "Merhaba.", "reason": "meaning"}],
        }]
        with patch("hybrid_translate.build_semantic_reconciliation_clusters",
                   return_value=[cluster]), \
             patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create",
                   return_value=_response(payload)):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m")
        self.assertEqual(result, blocks)
        self.assertEqual(stats["fixed"], 0)
        self.assertEqual(stats["rejected"], 1)
        self.assertEqual(stats["details"][0]["reason"], "new_validator_issue")

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

    def test_cluster_cannot_be_applied_again_from_another_batch(self):
        blocks = [
            ("1", "00:00:01 --> 00:00:02", "Eski bir."),
            ("2", "00:00:02 --> 00:00:03", "Eski iki."),
        ]
        src_map = {"1": "First.", "2": "Second."}
        clusters = [
            {
                "cluster": "c1",
                "items": [{"id": "1", "source": "First.",
                           "translation": "Eski bir.", "suspect": True,
                           "reasons": ["POST_PASS_CHANGED"]}],
                "suspect_ids": ["1"],
            },
            {
                "cluster": "c2",
                "items": [{"id": "2", "source": "Second.",
                           "translation": "Eski iki.", "suspect": True,
                           "reasons": ["POST_PASS_CHANGED"]}],
                "suspect_ids": ["2"],
            },
        ]
        responses = [
            _response([{
                "cluster": "c1",
                "fixes": [{"id": "1", "text": "İlk.", "reason": "meaning"}],
            }]),
            _response([{
                "cluster": "c1",
                "fixes": [{"id": "1", "text": "İkinci kez.", "reason": "retry"}],
            }]),
        ]

        with patch("hybrid_translate.build_semantic_reconciliation_clusters",
                   return_value=clusters), \
             patch("hybrid_translate._semantic_cluster_batches",
                   return_value=[[clusters[0]], [clusters[1]]]), \
             patch("openai.OpenAI"), \
             patch("hybrid_translate._safe_chat_create", side_effect=responses), \
             patch("hybrid_translate._semantic_reason_map", return_value={}), \
             patch("hybrid_translate.validate_semantic_reconciliation_candidate",
                   return_value=(True, "")):
            result, stats = ht.semantic_reconciliation_pass(
                src_map, blocks, api_key="k", model="m"
            )

        self.assertEqual(result[0][2], "İlk.")
        self.assertEqual(result[1][2], "Eski iki.")
        self.assertEqual(stats["fixed"], 1)
        self.assertEqual(stats["rejected"], 1)
        self.assertIn(
            "cluster_outside_batch",
            [detail.get("reason") for detail in stats["details"]],
        )


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
                   return_value=([("1", blocks[0][1], "Yeni.")], stats)) as semantic, \
             patch("builtins.open", mock_open()):
            fixed = app._run_final_semantic_checks(
                "out.srt", {"1": "Source."}, blocks, changed_ids={"1"}
            )

        self.assertEqual(fixed, 1)
        self.assertEqual(semantic.call_args.kwargs["target_coverage"], 0.65)
        self.assertEqual(blocks[0][2], "Yeni.")
        app._helper_api_key.assert_called_with("critic")
        app._helper_api_base_url.assert_called_with("critic")
        app._helper_api_model.assert_called_with("critic")

    def test_worker_uses_snapshot_toggle(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = {"semantic_reconcile": False}
        app.semantic_reconcile_var = MagicMock()

        with patch("subtitle_translator_gui.threading.current_thread"), \
             patch("subtitle_translator_gui.threading.main_thread") as main_thread:
            main_thread.return_value = object()
            self.assertFalse(app._semantic_reconcile_enabled())

        app.semantic_reconcile_var.get.assert_not_called()

    def test_report_parent_is_created_before_write(self):
        app = gui.App.__new__(gui.App)
        app._pm = None
        app.semantic_reconcile_var = SimpleNamespace(get=lambda: True)
        app.src_var = SimpleNamespace(get=lambda: "English")
        app.tgt_var = SimpleNamespace(get=lambda: "Turkish")
        app._log = MagicMock()
        app._helper_api_key = MagicMock(return_value="k")
        app._helper_api_base_url = MagicMock(return_value=None)
        app._helper_api_model = MagicMock(return_value="m")
        app._token_callback_for_model = MagicMock(return_value=MagicMock())
        app._get_file_glossary = MagicMock(return_value="")
        blocks = [("1", "00:00:01 --> 00:00:02", "Eski.")]
        stats = {
            "clusters": 1, "suspects": 1, "covered_cues": 1,
            "coverage_pct": 100.0, "api_requests": 1, "proposed": 0,
            "fixed": 0, "rejected": 0, "reflow_recovered": 0,
            "details": [],
        }

        with tempfile.TemporaryDirectory() as tmp, \
             patch("hybrid_translate.semantic_reconciliation_pass",
                   return_value=(list(blocks), stats)):
            out_path = Path(tmp) / "new" / "nested" / "episode.srt"
            app._maybe_semantic_reconciliation(
                str(out_path), {"1": "Source."}, blocks
            )
            report = out_path.with_suffix(".anlamsal_mutabakat.txt")
            self.assertTrue(report.exists())
            report_text = report.read_text(encoding="utf-8")
            self.assertIn("Planlanan kapsam: 1/1", report_text)
            self.assertIn("İşlenen kapsam: 0/1", report_text)

    def test_targeted_pass_uses_custom_coverage_and_report_path(self):
        app = gui.App.__new__(gui.App)
        app._pm = None
        app.semantic_reconcile_var = SimpleNamespace(get=lambda: True)
        app.src_var = SimpleNamespace(get=lambda: "English")
        app.tgt_var = SimpleNamespace(get=lambda: "Turkish")
        app._log = MagicMock()
        app._helper_api_key = MagicMock(return_value="k")
        app._helper_api_base_url = MagicMock(return_value=None)
        app._helper_api_model = MagicMock(return_value="m")
        app._token_callback_for_model = MagicMock(return_value=MagicMock())
        app._get_file_glossary = MagicMock(return_value="")
        app._active_run_record = {"reports": []}
        app._run_record_lock = threading.Lock()
        blocks = [("1", "00:00:01 --> 00:00:02", "Eski.")]
        stats = {
            "clusters": 1, "suspects": 1, "covered_cues": 1,
            "coverage_pct": 100.0, "api_requests": 1, "proposed": 0,
            "fixed": 0, "rejected": 0, "reflow_recovered": 0,
            "details": [],
        }

        with tempfile.TemporaryDirectory() as tmp, \
             patch("hybrid_translate.semantic_reconciliation_pass",
                   return_value=(list(blocks), stats)) as semantic:
            report = Path(tmp) / "Raporlar" / "season.txt"
            app._maybe_semantic_reconciliation(
                Path(tmp) / "episode.srt", {"1": "Source."}, blocks,
                target_coverage=0.0, report_path=report,
            )

            self.assertEqual(semantic.call_args.kwargs["target_coverage"], 0.0)
            self.assertTrue(report.exists())
            self.assertIn(str(report), app._active_run_record["reports"])

    def test_locked_terms_merge_file_project_and_series_memory(self):
        app = gui.App.__new__(gui.App)
        app._pm = MagicMock()
        app._pm.get_glossary.return_value = {"Project Term": "Proje Terimi"}
        app._get_file_glossary = MagicMock(return_value="glossary.json")
        app._get_file_schema = MagicMock(return_value={
            "glossary": {"Schema Term": "Şema Terimi"}
        })
        app.series_memory_var = SimpleNamespace(get=lambda: True)
        app.input_var = SimpleNamespace(get=lambda: "C:/subs")
        app._log = MagicMock()
        series = MagicMock()
        series.get_terms.return_value = {"King Behemoth": "Kral Behemoth"}

        with patch("hybrid_translate.load_glossary",
                   return_value={"Provision Laboratory": "Tedarik Laboratuvarı"}), \
             patch("hybrid_translate.sanitize_glossary_for_turkish",
                   side_effect=lambda terms, **_kwargs: terms), \
             patch("series_memory.SeriesMemory.load", return_value=series):
            terms = app._get_locked_terms_dict(
                "C:/subs/Betterman.S01E02.srt", "Turkish"
            )

        self.assertEqual(terms["Provision Laboratory"], "Tedarik Laboratuvarı")
        self.assertEqual(terms["Schema Term"], "Şema Terimi")
        self.assertEqual(terms["Project Term"], "Proje Terimi")
        self.assertEqual(terms["King Behemoth"], "Kral Behemoth")

    def test_locked_terms_propagates_project_memory_cancellation(self):
        app = gui.App.__new__(gui.App)
        app._pm = MagicMock()
        app._pm.get_glossary.side_effect = gui.RequestCancelled("cancelled")
        app._get_file_glossary = MagicMock(return_value="")
        app._get_file_schema = MagicMock(return_value={})
        app._effective_file_source_language = MagicMock(return_value="English")
        app._project_memory_for = MagicMock(return_value=app._pm)

        with self.assertRaises(gui.RequestCancelled):
            app._get_locked_terms_dict("C:/subs/episode.srt", "Turkish")


if __name__ == "__main__":
    unittest.main()
