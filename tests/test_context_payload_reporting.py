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
    def test_write_results_receives_explicit_translation_requests(self):
        import inspect

        signature = inspect.signature(gui.App._write_results)
        self.assertIn("translation_requests", signature.parameters)

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
        self.assertEqual(metrics["context_gap_chunks"], [])

    def test_reports_exact_cue_ranges_for_missing_source_context(self):
        first = _request({"tr": [{"i": 10, "t": "First"}]})
        first["custom_id"] = "chunk_10"
        second = _request({"tr": [{"i": 11, "t": "Second"}]})
        second["custom_id"] = "chunk_11"

        metrics = gui._context_payload_metrics([first, second])

        self.assertEqual(metrics["context_gap_chunks"], [
            {
                "chunk": "chunk_10", "cue_start": "10", "cue_end": "10",
                "before": 0, "after": 0, "ctx": 0, "prev_scene": 0,
                "reasons": ["sonraki_kaynak_yok"],
            },
            {
                "chunk": "chunk_11", "cue_start": "11", "cue_end": "11",
                "before": 0, "after": 0, "ctx": 0, "prev_scene": 0,
                "reasons": ["önceki_kaynak_yok"],
            },
        ])
        lines = gui._quality_feature_audit({
            "context_payload_metrics": metrics,
        }, {"chain_ctx": True})
        report = "\n".join(lines)
        self.assertIn("chunk_10#10-10[sonraki_kaynak_yok]", report)
        self.assertIn("chunk_11#11-11[önceki_kaynak_yok]", report)

    def test_scene_boundaries_are_not_reported_as_context_gaps(self):
        first = _request({"tr": [{"i": 20, "t": "Scene one"}]})
        first["custom_id"] = "chunk_20"
        second = _request({
            "tr": [{"i": 21, "t": "Scene two"}],
            "prev_scene": [{"i": 20, "t": "Scene one"}],
        })
        second["custom_id"] = "chunk_21"

        metrics = gui._context_payload_metrics([first, second])

        self.assertEqual(metrics["context_gap_chunks"], [])

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
                "chain_breaks": [
                    {"chunk": "film__g51", "reason": "empty_dialogue"},
                ],
            },
            "pass_status": {
                "Critic": {
                    "status": "completed", "report_only": True,
                    "reviewed_sentence_groups": 3,
                    "reviewed_sentence_cues": 7,
                    "rejected_count": 2,
                    "rejected_reasons": {"person_swap": 2},
                    "rejected_candidates": [
                        {"id": "21", "reason": "person_swap"},
                        {"id": "22", "reason": "person_swap"},
                    ],
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
        self.assertIn("cue [21,22]", report)
        self.assertIn("person_swap:2", report)
        self.assertIn("Critic deterministik inceleme adayları: 2 cue [11,12]", report)
        self.assertIn("BROKEN_FRAGMENT_FLOW:1", report)
        self.assertIn("EARLY_VERB_CLOSURE:1", report)
        self.assertIn(
            "Zincirleme bağlam kopması: 1 chunk — film__g51[empty_dialogue]",
            report)

    def test_critic_rejected_candidate_details_fill_missing_reason_summary(self):
        lines = gui._quality_feature_audit({
            "pass_status": {
                "Critic": {
                    "status": "completed",
                    "reviewed_sentence_groups": 1,
                    "reviewed_sentence_cues": 2,
                    "rejected_count": 2,
                    "rejected_candidates": [
                        {"id": "41", "reason": "source_modality"},
                        {"id": "42", "reason": "source_modality"},
                    ],
                }
            },
        }, {"critic": True})

        report = "\n".join(lines)
        self.assertIn("cue [41,42]", report)
        self.assertIn("source_modality:2", report)

    def test_chain_report_requires_real_previous_translation_injection(self):
        one_chunk = "\n".join(gui._quality_feature_audit({
            "chain_ctx": True,
            "translation_chunks": 1,
            "context_payload_metrics": {"chunks": 1, "prev_tr_chunks": 0},
        }, {"chain_ctx": True}))
        self.assertIn("dosya tek chunk olduğu için", one_chunk)
        self.assertNotIn("Zincirleme Bağlam: çalıştı", one_chunk)

        no_injection = "\n".join(gui._quality_feature_audit({
            "chain_ctx": True,
            "translation_chunks": 3,
            "context_payload_metrics": {"chunks": 3, "prev_tr_chunks": 0},
        }, {"chain_ctx": True}))
        self.assertIn("hiçbirine önceki çeviri enjekte edilmedi", no_injection)
        self.assertNotIn("Zincirleme Bağlam: çalıştı", no_injection)

        injected = "\n".join(gui._quality_feature_audit({
            "chain_ctx": True,
            "translation_chunks": 3,
            "context_payload_metrics": {"chunks": 3, "prev_tr_chunks": 2},
        }, {"chain_ctx": True}))
        self.assertIn("çalıştı, 2/3 chunk", injected)

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
