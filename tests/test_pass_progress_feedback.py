import json
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


def _response(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(payload)))],
        usage=None,
    )


class PassProgressFeedbackTest(unittest.TestCase):
    def test_all_native_gui_calls_collect_real_completion_status(self):
        source = inspect.getsource(gui.App)
        self.assertEqual(
            source.count("ht.native_reader_pass("),
            source.count("status_out=_native_status"),
        )
        self.assertGreaterEqual(
            source.count('_native_status.get("status") == "completed"'), 4)

    def test_native_does_not_report_natural_when_every_request_failed(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")]
        status = {}
        logs = []
        with patch("openai.OpenAI", return_value=MagicMock()), patch.object(
                ht, "_safe_chat_create", side_effect=RuntimeError("503")):
            result = ht.native_reader_pass(
                blocks, "key", status_out=status,
                log_fn=lambda message, tag="": logs.append((message, tag)))

        self.assertEqual(result, blocks)
        self.assertEqual(status, {
            "status": "failed", "successful_chunks": 0,
            "failed_chunks": 1, "total_chunks": 1, "changed": 0,
        })
        self.assertTrue(any("tamamlanamadı" in message for message, _ in logs))
        self.assertFalse(any("zaten doğal" in message for message, _ in logs))

    def test_native_reports_request_wait_and_completion(self):
        events = []
        status = {}
        with patch("openai.OpenAI", return_value=MagicMock()), \
             patch.object(ht, "_safe_chat_create", return_value=_response([])):
            ht.native_reader_pass(
                [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")],
                "key",
                progress_callback=lambda *args: events.append(args),
                status_out=status,
            )

        self.assertEqual(events, [
            (0, 1, "requesting"),
            (1, 1, "completed"),
        ])
        self.assertEqual(status["status"], "completed")

    def test_semantic_reports_each_api_batch(self):
        cluster = {
            "cluster": "c1",
            "items": [{
                "id": "1", "source": "Hello.", "translation": "Merhaba.",
                "suspect": True, "reasons": ["POST_PASS_CHANGED"],
            }],
            "suspect_ids": ["1"],
        }
        events = []
        with patch("openai.OpenAI", return_value=MagicMock()), \
             patch.object(ht, "build_semantic_reconciliation_clusters",
                          return_value=[cluster]), \
             patch.object(ht, "_safe_chat_create", return_value=_response([])), \
             patch.object(ht, "_semantic_reason_map", return_value={}):
            ht.semantic_reconciliation_pass(
                {"1": "Hello."},
                [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")],
                api_key="key",
                model="model",
                progress_callback=lambda *args: events.append(args),
            )

        self.assertEqual(events, [
            (0, 1, "requesting"),
            (1, 1, "completed"),
        ])

    def test_gui_feedback_shows_waiting_packet_and_real_progress(self):
        phases = []
        rows = []
        app = SimpleNamespace(
            _set_phase=lambda *args: phases.append(args),
            _update_file_progress=lambda *args: rows.append(args),
        )
        callback = gui.App._pass_progress_callback(
            app, "C:/subs/episode.srt", "Native Okuyucu", 90.0, 96.0)

        callback(2, 6, "requesting")
        callback(3, 6, "completed")

        self.assertIn("Paket 3/6 · yanıt bekleniyor", phases[0][1])
        self.assertIn("Paket 3/6 · yanıt alındı", phases[1][1])
        self.assertEqual(rows[0][-1], 92.0)
        self.assertEqual(rows[1][-1], 93.0)


if __name__ == "__main__":
    unittest.main()
