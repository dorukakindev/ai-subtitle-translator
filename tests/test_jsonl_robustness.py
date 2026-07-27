import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json
import tempfile
from pathlib import Path

class TestJsonlRobustness(unittest.TestCase):
    def test_standalone_prompt_uses_shared_quality_rules(self):
        from subtitle_batch_translate import build_standalone_system_prompt

        prompt = build_standalone_system_prompt("English", "Turkish")
        self.assertIn("MEANING-FIRST", prompt)
        self.assertIn("<=21 CPS", prompt)
        self.assertIn("Preserve every name, number, fact, negation", prompt)
        self.assertIn("Return ONLY the translated subtitle text", prompt)

    def test_provider_resolution_logs_safe_fallback_errors(self):
        from subtitle_batch_translate import resolve_standalone_provider

        messages = []
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_path = Path(tmpdir) / ".gui_settings.json"
            settings_path.write_text("{broken", encoding="utf-8")
            with patch("credential_store.load_key", return_value="secret-key"):
                key, _, service = resolve_standalone_provider(
                    settings_path, log_fn=messages.append)

        self.assertEqual(key, "secret-key")
        self.assertEqual(service, "openai")
        self.assertTrue(any("Ayar dosyası okunamadı" in item for item in messages))
        self.assertNotIn("secret-key", "\n".join(messages))

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

    @patch("subtitle_batch_translate._get_client")
    @patch("subtitle_batch_translate.write_srt")
    def test_explicit_empty_result_only_drops_pure_sdh_source(
            self, mock_write_srt, mock_get_client):
        import subtitle_batch_translate as standalone

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.files.content.return_value.text = (
            '{"custom_id":"sfx","response":{"body":{"choices":[{"message":{"content":""}}]}}}\n'
            '{"custom_id":"dialogue","response":{"body":{"choices":[{"message":{"content":""}}]}}}'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n[MUSIC]\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\nHello\n\n",
                encoding="utf-8",
            )
            fmap = {
                "sfx": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000"),
                "dialogue": (str(source), 1, "2", "00:00:01,000 --> 00:00:02,000"),
            }
            with patch.object(standalone, "INPUT_FOLDER", tmpdir):
                standalone.process_results("out", fmap, [str(source)])

        blocks = mock_write_srt.call_args.args[1]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0][0], "2")
        self.assertEqual(blocks[0][2], "[ÇEVIRI HATASI]")

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

    @patch("repair_batches._get_client")
    def test_repair_batches_main_loop_and_srt_newlines(self, mock_get_client):
        import tempfile
        import repair_batches

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.srt"
            fmap_file = Path(tmpdir) / "batch_fmap_b123.json"

            fmap_data = {
                "output_path": str(out_file),
                "fmap": {
                    "cid1": [[1, "00:00:00,000", "00:00:02,000"]],
                    "cid2": [[2, "00:00:02,000", "00:00:04,000"]],
                }
            }
            fmap_file.write_text(json.dumps(fmap_data), encoding="utf-8")

            mock_batch = MagicMock()
            mock_batch.status = "completed"
            mock_batch.output_file_id = "out_123"
            mock_client.batches.retrieve.return_value = mock_batch

            jsonl_content = (
                '{"custom_id": "cid1"}\n'
                '{"custom_id": "unknown", "response": {"body": {"choices": [{"message": {"content": "ignored"}}]}}}\n'
                '{"custom_id": "cid2", "response": {"body": {"choices": [{"message": {"content": "[{\\"i\\": 2, \\"t\\": \\"Satir 2\\"}]"}}]}}}\n'
            )
            mock_client.files.content.return_value.text = jsonl_content

            with patch("repair_batches.FMAP_FILES", [str(fmap_file)]), \
                    patch("builtins.print") as mock_print:
                repair_batches.main()

            self.assertTrue(out_file.exists())
            written_text = out_file.read_text(encoding="utf-8")

            # 1. Must contain real newlines
            self.assertIn("\n", written_text)
            # 2. Must NOT contain literal "\\n" string
            self.assertNotIn("\\n", written_text)
            # 3. Missing record yielded [HATA], valid record processed successfully
            self.assertIn("[HATA]", written_text)
            self.assertIn("Satir 2", written_text)
            printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list
                                if call.args)
            self.assertIn("unknown: fmap eşleşmesi yok", printed)

    def test_smoke_script_uses_source_driven_sdh_cleanup(self):
        smoke = (Path(__file__).parents[1] / "_smoke_test.py").read_text(encoding="utf-8")
        self.assertIn("src_map=src_map, source_driven=True", smoke)

    def test_atomic_write_srt_preserves_file_on_error(self):
        import subtitle_batch_translate
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "subtitles_tr.srt"
            out_file.write_text("ÖNCEKİ İÇERİK OK", encoding="utf-8")

            blocks = [(1, "00:00:00,000 --> 00:00:02,000", "Merhaba Dünya")]
            subtitle_batch_translate.write_srt(out_file, blocks)

            written = out_file.read_text(encoding="utf-8")
            self.assertIn("1\n00:00:00,000 --> 00:00:02,000\nMerhaba Dünya\n\n", written)
            self.assertNotIn("\\n", written)

            # Exception simulation: target file content must remain unchanged if exception raised before write
            try:
                def bad_normalize(text):
                    raise RuntimeError("Simulated failure during formatting")
                with patch("subtitle_batch_translate._normalize_output_text", side_effect=bad_normalize):
                    subtitle_batch_translate.write_srt(out_file, blocks)
            except RuntimeError:
                pass

            self.assertEqual(out_file.read_text(encoding="utf-8"), written)

if __name__ == '__main__':
    unittest.main()
