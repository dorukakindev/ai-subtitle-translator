import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

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

if __name__ == '__main__':
    unittest.main()
