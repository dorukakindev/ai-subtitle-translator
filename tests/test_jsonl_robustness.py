import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
from pathlib import Path

class TestJsonlRobustness(unittest.TestCase):
    @patch("credential_store.load_key")
    def test_imports_do_not_trigger_network_or_store(self, mock_load_key):
        import subtitle_batch_translate
        import repair_batches
        import read_errors
        import resume_batch
        
        mock_load_key.assert_not_called()

    def test_safe_parse_jsonl_line(self):
        from subtitle_batch_translate import safe_parse_jsonl_line
        
        # Valid JSON
        valid = safe_parse_jsonl_line('{"custom_id": "test", "response": {"body": {"choices": [{"message": {"content": "text"}}]}}}')
        self.assertIsNotNone(valid)
        self.assertEqual(valid["custom_id"], "test")
        
        # Corrupt JSON
        corrupt = safe_parse_jsonl_line('{corrupt')
        self.assertIsNone(corrupt)
        
        # Empty line
        empty = safe_parse_jsonl_line('   ')
        self.assertIsNone(empty)

    @patch("subtitle_batch_translate._get_client")
    @patch("subtitle_batch_translate.write_srt")
    def test_process_results_mixed_validity(self, mock_write_srt, mock_get_client):
        from subtitle_batch_translate import process_results
        
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Simulate output file content
        content = '''{invalid json
{"custom_id": "cid1", "response": {"body": {"choices": [{"message": {"content": "Valid Translation"}}]}}}
{"custom_id": "cid2", "error": {"message": "Some error"}}
{"custom_id": "cid3"}  # missing choices
'''
        mock_client.files.content.return_value.text = content
        
        file_map = {
            "cid1": ("./subtitles/file1.srt", 0, "1", "00:00:00,000 --> 00:00:01,000"),
            "cid2": ("./subtitles/file1.srt", 1, "2", "00:00:01,000 --> 00:00:02,000"),
            "cid3": ("./subtitles/file1.srt", 2, "3", "00:00:02,000 --> 00:00:03,000"),
        }
        
        process_results("fake_file_id", file_map, ["./subtitles/file1.srt"])
        
        mock_write_srt.assert_called_once()
        args, _ = mock_write_srt.call_args
        blocks = args[1]
        
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0][2], "Valid Translation")
        self.assertEqual(blocks[1][2], "[ÇEVIRI HATASI]")
        self.assertEqual(blocks[2][2], "[ÇEVIRI HATASI]")

    def test_try_extract_fenced_newlines(self):
        from repair_batches import _try_extract
        fenced_content = "```json\n[{\"i\": 1, \"t\": \"Merhaba\"}]\n```"
        result = _try_extract(fenced_content)
        self.assertIsNotNone(result)
        self.assertEqual(result, [{"i": 1, "t": "Merhaba"}])

    def test_standalone_provider_resolution(self):
        from subtitle_batch_translate import resolve_standalone_provider
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".gui_settings.json"
            # 1. Official OpenAI default
            settings_path.write_text(json.dumps({"main_custom": False, "api_url": "https://api.openai.com/v1"}), encoding="utf-8")
            with patch("credential_store.load_key", return_value="sk-official"):
                key, url, service = resolve_standalone_provider(settings_path)
                self.assertEqual(key, "sk-official")
                self.assertEqual(service, "openai")

            # 2. Custom provider active
            settings_path.write_text(json.dumps({"main_custom": True, "main_custom_url": "https://custom.endpoint.com/v1"}), encoding="utf-8")
            with patch("credential_store.load_key", side_effect=lambda s: "sk-custom" if s == "main_custom" else "sk-official"):
                key, url, service = resolve_standalone_provider(settings_path)
                self.assertEqual(key, "sk-custom")
                self.assertEqual(url, "https://custom.endpoint.com/v1")
                self.assertEqual(service, "main_custom")

            # 3. Custom provider missing key raises RuntimeError (does not fall back to official key)
            with patch("credential_store.load_key", return_value=None):
                with self.assertRaises(RuntimeError):
                    resolve_standalone_provider(settings_path)

if __name__ == '__main__':
    unittest.main()
