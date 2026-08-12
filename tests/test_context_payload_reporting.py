import json
import unittest

import subtitle_translator_gui as gui


def _request(payload):
    return {
        "body": {
            "messages": [
                {"role": "system", "content": "rules"},
                {"role": "user", "content": json.dumps(payload)},
            ]
        }
    }


class ContextPayloadReportingTests(unittest.TestCase):
    def test_counts_context_that_was_really_injected(self):
        metrics = gui._context_payload_metrics([
            _request({
                "tr": [
                    {"i": 1, "t": "If I", "frag": "start"},
                    {"i": 2, "t": "leave.", "frag": "end"},
                ],
                "ctx": [{"i": 0, "t": "Before"}],
                "next_ctx": [{"i": 3, "t": "After"}],
                "prev_tr": [{"src": "Before", "tr": "Önce"}],
                "scene": [{"start": 1, "end": 2}],
                "sentence_groups": [{"id": "fg_1_2", "items": ["1", "2"]}],
            }),
            _request({
                "tr": [{"i": 3, "t": "New scene"}],
                "prev_scene": [{"i": 2, "t": "leave."}],
            }),
        ])

        self.assertEqual(metrics["chunks"], 2)
        self.assertEqual(metrics["source_cues"], 3)
        self.assertEqual(metrics["ctx_chunks"], 1)
        self.assertEqual(metrics["prev_tr_pairs"], 1)
        self.assertEqual(metrics["scene_plan_chunks"], 1)
        self.assertEqual(metrics["sentence_groups"], 1)
        self.assertEqual(metrics["fragment_cues"], 2)
        self.assertEqual(metrics["prev_scene_chunks"], 1)

    def test_quality_report_exposes_context_and_critic_coverage(self):
        lines = gui._quality_feature_audit({
            "run_status": "done",
            "chain_ctx": True,
            "translation_chunks": 2,
            "context_payload_metrics": {
                "chunks": 2, "ctx_chunks": 1, "next_ctx_chunks": 2,
                "prev_tr_chunks": 1, "scene_plan_chunks": 2,
                "sentence_groups": 3, "fragment_cues": 7,
                "prev_scene_chunks": 1,
            },
            "pass_status": {
                "Critic": {
                    "status": "completed", "report_only": True,
                    "reviewed_sentence_groups": 3,
                    "reviewed_sentence_cues": 7,
                    "rejected_count": 2,
                    "rejected_reasons": {"person_swap": 2},
                    "validator_candidates": [
                        {"id": "11", "reason": "BROKEN_FRAGMENT_FLOW"},
                        {"id": "12", "reason": "EARLY_VERB_CLOSURE|CROSS_CUE_SENTENCE_REVIEW"},
                    ],
                }
            },
        }, {"critic": True, "chain_ctx": True})

        report = "\n".join(lines)
        self.assertIn("Bağlam taşıma kanıtı", report)
        self.assertIn("Cümle zinciri kanıtı", report)
        self.assertIn("Critic cümle-zinciri kapsamı: 3 grup/7 cue", report)
        self.assertIn("person_swap:2", report)
        self.assertIn("Critic deterministik inceleme adayları: 2 cue [11,12]", report)
        self.assertIn("BROKEN_FRAGMENT_FLOW:1", report)
        self.assertIn("EARLY_VERB_CLOSURE:1", report)

    def test_filters_multi_file_requests_with_file_map(self):
        first = _request({"tr": [{"i": 1, "t": "First"}], "ctx": [{"i": 0}]})
        first["custom_id"] = "first"
        second = _request({"tr": [{"i": 1, "t": "Second"}], "scene": [{"start": 1}]})
        second["custom_id"] = "second"
        fmap = {
            "first": [(1, "00:00:00,000 --> 00:00:01,000", "C:/one.srt")],
            "second": [(1, "00:00:00,000 --> 00:00:01,000", "C:/two.srt")],
        }

        metrics = gui._context_payload_metrics(
            [first, second], "C:/one.srt", fmap)

        self.assertEqual(metrics["chunks"], 1)
        self.assertEqual(metrics["ctx_chunks"], 1)
        self.assertEqual(metrics["scene_plan_chunks"], 0)


if __name__ == "__main__":
    unittest.main()
