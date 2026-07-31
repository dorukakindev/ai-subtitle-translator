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
        self.assertEqual(blocks[0][2], "Hello")

    @patch("subtitle_batch_translate._get_client")
    @patch("subtitle_batch_translate.write_srt")
    def test_process_results_rejects_duplicate_and_truncated_records(
            self, mock_write_srt, mock_get_client):
        import subtitle_batch_translate as standalone

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.files.content.return_value.text = (
            '{"custom_id":"first","response":{"body":{"choices":[{"message":{"content":"Ilk"}}]}}}\n'
            '{"custom_id":"first","response":{"body":{"choices":[{"message":{"content":"Ikinci"}}]}}}\n'
            '{"custom_id":"cut","response":{"body":{"choices":[{"finish_reason":"length","message":{"content":"Yarim"}}]}}}'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nOne\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\nTwo\n\n", encoding="utf-8")
            fmap = {
                "first": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000"),
                "cut": (str(source), 1, "2", "00:00:01,000 --> 00:00:02,000"),
            }
            result = standalone.process_results(
                "out", fmap, [str(source)], input_folder=tmpdir, output_folder=tmpdir)

        blocks = mock_write_srt.call_args.args[1]
        self.assertEqual([block[2] for block in blocks], ["One", "Two"])
        self.assertEqual(result["failed_ids"], {"first", "cut"})

    def test_standalone_recovery_preserves_submitted_source_signature(self):
        import subtitle_batch_translate as standalone

        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:01,000\nOne\n", encoding="utf-8")
            recovery = Path(tmpdir) / "recovery.json"
            fmap = {"cid": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000")}
            with patch.object(standalone, "standalone_recovery_path", return_value=recovery):
                standalone.save_standalone_recovery("batch_123", fmap, input_folder=tmpdir, output_folder=tmpdir)
                record = standalone.load_standalone_recovery()

            self.assertEqual(record["file_map"], fmap)
            self.assertEqual(record["source_hashes"][str(source)], standalone._source_file_sha256(str(source)))

    @patch("subtitle_batch_translate._get_client")
    @patch("subtitle_batch_translate.write_srt")
    def test_standalone_never_overwrites_source_when_output_matches_input(
            self, mock_write_srt, mock_get_client):
        import subtitle_batch_translate as standalone
        mock_get_client.return_value.files.content.return_value.text = (
            '{"custom_id":"cid","response":{"body":{"choices":[{"message":{"content":"Merhaba"}}]}}}'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            standalone.process_results(
                "out", {"cid": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000")},
                [str(source)], input_folder=tmpdir, output_folder=tmpdir)
        self.assertEqual(mock_write_srt.call_args.args[0], source.with_name("source.tr.srt"))

    def test_non_turkish_standalone_output_skips_turkish_artifact_rewrite(self):
        import subtitle_batch_translate as standalone
        self.assertEqual(standalone._normalize_output_text("Yada", "German"), "Yada")

    def test_try_extract_fenced_newlines(self):
        from repair_batches import _try_extract
        fenced_content = "```json\n[{\"i\": 1, \"t\": \"Merhaba\"}]\n```"
        result = _try_extract(fenced_content)
        self.assertIsNotNone(result)
        self.assertEqual(result, [{"i": 1, "t": "Merhaba"}])

    def test_repair_chunk_rejects_duplicate_or_unknown_cue_ids(self):
        from repair_batches import parse_chunk
        info = [["1", "00:00:00,000", "00:00:01,000"]]
        self.assertEqual(parse_chunk('[{"i":"1","t":"A"},{"i":"1","t":"B"}]', info, "cid"), {})
        self.assertEqual(parse_chunk('[{"i":"99","t":"A"}]', info, "cid"), {})

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

    @patch("repair_batches._get_client")
    def test_repair_batches_keeps_cues_missing_from_output(self, mock_get_client):
        import repair_batches

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "out.srt"
            fmap_file = Path(tmpdir) / "batch_fmap_b123.json"
            fmap_file.write_text(json.dumps({
                "output_path": str(out_file),
                "fmap": {
                    "seen": [[1, "00:00:00,000", "00:00:01,000"]],
                    "missing": [[2, "00:00:01,000", "00:00:02,000"]],
                },
            }), encoding="utf-8")
            mock_batch = MagicMock(status="completed", output_file_id="out_123")
            mock_client.batches.retrieve.return_value = mock_batch
            mock_client.files.content.return_value.text = (
                '{"custom_id":"seen","response":{"body":{"choices":[{"message":{"content":"[{\\"i\\": 1, \\"t\\": \\"Tamam\\"}]"}}]}}}'
            )

            with patch("repair_batches.FMAP_FILES", [str(fmap_file)]):
                repair_batches.main()

            written = out_file.read_text(encoding="utf-8")
            self.assertIn("1\n00:00:00,000 --> 00:00:01,000\nTamam", written)
            self.assertIn("2\n00:00:01,000 --> 00:00:02,000\n[HATA]", written)

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
