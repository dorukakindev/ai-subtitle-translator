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


def _response_with_usage(payload, total=17, cached=4):
    response = _response(payload)
    response.usage = SimpleNamespace(
        total_tokens=total,
        prompt_tokens_details=SimpleNamespace(cached_tokens=cached),
    )
    return response


class PassProgressFeedbackTest(unittest.TestCase):
    def test_all_native_gui_calls_collect_real_completion_status(self):
        source = inspect.getsource(gui.App)
        self.assertEqual(
            source.count("ht.native_reader_pass("),
            source.count("status_out=_native_status"),
        )
        self.assertGreaterEqual(
            source.count('_native_status.get("status") == "completed"'), 4)

    def test_all_critic_gui_calls_collect_real_completion_status(self):
        source = inspect.getsource(gui.App)
        self.assertEqual(
            source.count("ht.critic_pass_with_helper("),
            source.count("status_out=_critic_status"),
        )
        self.assertGreaterEqual(
            source.count('_critic_status.get("status") == "completed"'), 4)

    def test_all_polish_gui_calls_collect_real_completion_status(self):
        source = inspect.getsource(gui.App)
        self.assertEqual(
            source.count("self._polish_pass("),
            source.count("status_out=_polish_status"),
        )
        self.assertGreaterEqual(
            source.count('_polish_status.get("status") == "completed"'), 5)

    def test_polish_reports_failed_when_both_attempts_fail(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")]
        status = {}
        logs = []
        app = SimpleNamespace(
            _stop_flag=False,
            _log=lambda message, tag="": logs.append((message, tag)),
            _log_exc=lambda message, exc: logs.append((f"{message}: {exc}", "err")),
            _update_tokens=lambda *args, **kwargs: None,
        )
        with patch("openai.OpenAI", return_value=MagicMock()), \
             patch.object(gui, "_safe_chat_create", side_effect=RuntimeError("503")), \
             patch.object(gui.time, "sleep", return_value=None):
            result = gui.App._polish_pass(
                app, blocks, "Turkish", "key", "https://example.test/v1",
                "model", status_out=status)

        self.assertEqual(result, blocks)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 1)
        self.assertTrue(any("tamamlanamadı" in message for message, _ in logs))

    def test_critic_does_not_report_no_fix_when_every_request_failed(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")]
        cues = [SimpleNamespace(index=1, text="Hello.")]
        status = {}
        logs = []
        with patch("openai.OpenAI", return_value=MagicMock()), \
             patch.object(ht, "run_validators", return_value=[
                 (1, "ts", "text", "TEST")]), \
             patch.object(ht, "_safe_chat_create", side_effect=RuntimeError("503")):
            result = ht.critic_pass_with_helper(
                cues, blocks, "key", status_out=status,
                log_fn=lambda message, tag="": logs.append((message, tag)))

        self.assertEqual(result, blocks)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 1)
        self.assertTrue(any("tamamlanamadı" in message for message, _ in logs))
        self.assertFalse(any("ek düzeltme gerekmedi" in message for message, _ in logs))

    def test_qc_reports_failed_when_every_request_failed(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")]
        cues = [SimpleNamespace(index=1, text="Hello.")]
        status = {}
        logs = []
        with patch("openai.OpenAI", return_value=MagicMock()), patch.object(
                ht, "_safe_chat_create", side_effect=RuntimeError("503")):
            issues = ht.quality_check_with_helper(
                cues, blocks, "key", status_out=status,
                log_fn=lambda message, tag="": logs.append((message, tag)))

        self.assertEqual(issues, [])
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["failed_chunks"], 1)
        self.assertTrue(any("tamamlanamadı" in message for message, _ in logs))

    def test_qc_reports_response_usage(self):
        callback = MagicMock()
        with patch("openai.OpenAI", return_value=MagicMock()), patch.object(
                ht, "_safe_chat_create",
                return_value=_response_with_usage({"issues": []})):
            issues = ht.quality_check_with_helper(
                [SimpleNamespace(index=1, text="Hello.")],
                [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")],
                "key", token_callback=callback)

        self.assertEqual(issues, [])
        callback.assert_called_once_with(17, cached=4)

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
