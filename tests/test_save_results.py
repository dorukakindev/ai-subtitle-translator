import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import hybrid_translate as ht


class SaveResultsBozukJsonlTest(unittest.TestCase):
    def _mkout(self):
        fd, path = tempfile.mkstemp(suffix=".srt")
        os.close(fd)
        return path

    def test_bozuk_jsonl_satiri_atlanir(self):
        out_path = self._mkout()
        log_calls = []

        def log_fn(msg, level="info"):
            log_calls.append((level, msg))

        mock_client = mock.MagicMock()
        mock_client.files.content.return_value.text = (
            '{"custom_id": "ok", "response": {"body": {"choices": [{"message": {"content": "a"}}]}}}\n'
            "not valid json\n"
            '{"custom_id": "ok2", "response": {"body": {"choices": [{"message": {"content": "b"}}]}}}\n'
        )
        file_map = {
            "ok": [(1, "00:00:01,000", "00:00:02,000")],
            "ok2": [(2, "00:00:02,000", "00:00:03,000")],
        }

        try:
            with mock.patch("openai.OpenAI", return_value=mock_client):
                count, n_marked = ht.save_results(
                    openai_api_key="fake",
                    output_file_id="fid",
                    file_map=file_map,
                    output_path=out_path,
                    log_fn=log_fn,
                )

            self.assertEqual(count, 2)
            self.assertIn(("warn", "Satır ayrıştırılamadı: not valid json"), log_calls)
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_tamamen_bozuk_jsonl_hata_vermez(self):
        out_path = self._mkout()
        mock_client = mock.MagicMock()
        mock_client.files.content.return_value.text = (
            "garbage line 1\n"
            "garbage line 2\n"
        )

        try:
            with mock.patch("openai.OpenAI", return_value=mock_client):
                count, n_marked = ht.save_results(
                    openai_api_key="fake",
                    output_file_id="fid",
                    file_map={"x": [(1, "00:00:01,000", "00:00:02,000")]},
                    output_path=out_path,
                )

            self.assertEqual(count, 1)
            self.assertIn(
                "[HATA_MISSING_RESPONSE]",
                Path(out_path).read_text(encoding="utf-8"))
        finally:
            Path(out_path).unlink(missing_ok=True)

    def test_single_line_fenced_batch_translation_is_preserved(self):
        out_path = self._mkout()
        mock_client = mock.MagicMock()
        mock_client.files.content.return_value.text = (
            '{"custom_id":"ok","response":{"body":{"choices":[{"message":'
            '{"content":"```json [{\\\"i\\\":\\\"1\\\",\\\"t\\\":\\\"Merhaba\\\"}]```"}}]}}}\n'
        )
        try:
            with mock.patch("openai.OpenAI", return_value=mock_client):
                count, marked = ht.save_results(
                    "fake", "fid", {"ok": [(1, "00:00:01,000", "00:00:02,000")]}, out_path)
            self.assertEqual((count, marked), (1, 0))
            self.assertIn("Merhaba", Path(out_path).read_text(encoding="utf-8"))
            self.assertNotIn("[HATA]", Path(out_path).read_text(encoding="utf-8"))
        finally:
            Path(out_path).unlink(missing_ok=True)
