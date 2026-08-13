import json
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


def _batch_line(custom_id, usage):
    return json.dumps({
        "custom_id": custom_id,
        "response": {"body": {
            "usage": usage,
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": '[{"i":"1","t":"Merhaba"}]'},
            }],
        }},
    })


class ReportingAccountingRound4Test(unittest.TestCase):
    def test_batch_usage_is_recorded_per_file_with_main_translation_pass(self):
        text = "\n".join((
            _batch_line("a", {
                "total_tokens": 11, "prompt_tokens": 7,
                "completion_tokens": 4,
                "prompt_tokens_details": {"cached_tokens": 2},
            }),
            _batch_line("b", {
                "total_tokens": 29, "prompt_tokens": 20,
                "completion_tokens": 9,
            }),
        ))
        calls = []
        app = SimpleNamespace(
            _log=lambda *_args, **_kwargs: None,
            _update_batch_tokens=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        client = SimpleNamespace(
            files=SimpleNamespace(content=lambda _output_id: SimpleNamespace(text=text)))
        file_map = {
            "a": [("1", "00:00:01,000 --> 00:00:02,000", "first.srt")],
            "b": [("1", "00:00:01,000 --> 00:00:02,000", "second.srt")],
        }

        raw = gui.App._save_batch_results(
            app, client, "out", expected_ids=set(file_map), file_map=file_map)

        self.assertEqual(set(raw), {"a", "b"})
        self.assertEqual(calls, [
            ((11,), {"cached": 2, "prompt_tokens": 7,
                     "completion_tokens": 4, "file_path": "first.srt"}),
            ((29,), {"cached": 0, "prompt_tokens": 20,
                     "completion_tokens": 9, "file_path": "second.srt"}),
        ])

    def test_enabled_chain_without_chunks_is_not_reported_as_ran(self):
        audit = gui._quality_feature_audit({
            "run_status": "error", "chain_ctx": True,
            "translation_chunks": 0,
        }, {})

        self.assertIn("Zincirleme Bağlam: açık, çalışma kaydı yok", audit)
        self.assertNotIn("Zincirleme Bağlam: çalıştı", audit)

    def test_normal_batch_chain_is_not_reported_as_applied(self):
        audit = gui._quality_feature_audit({
            "run_status": "done", "chain_ctx": True,
            "translation_chunks": 4,
        }, {"mode": "batch", "twowave": False})

        self.assertIn(
            "Zincirleme Bağlam: açık ama normal Batch'te uygulanmadı "
            "(chunk'lar paralel gönderildi)", audit)
        self.assertFalse(any("Zincirleme Bağlam: çalıştı" in line for line in audit))

    def test_twowave_batch_chain_keeps_applied_report(self):
        audit = gui._quality_feature_audit({
            "run_status": "done", "chain_ctx": True,
            "translation_chunks": 4,
            "context_payload_metrics": {"chunks": 4, "prev_tr_chunks": 2},
        }, {"mode": "batch", "twowave": True})

        self.assertIn(
            "Zincirleme Bağlam: çalıştı, 2/4 chunk önceki çeviriyi aldı",
            audit)

    def test_unknown_model_report_does_not_invent_a_usd_price(self):
        text = gui.build_quality_report_text(
            [{"name": "episode.srt", "total": 1}],
            "reseller-unknown", "Turkish", "sync", 1_000_000)

        self.assertNotIn("~$0.6000", text)
        self.assertIn("1,000,000 token maliyeti", text)


if __name__ == "__main__":
    unittest.main()
