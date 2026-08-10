import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import repair_batches
import subtitle_batch_translate as standalone
import video_subtitles as video
from app_state import atomic_write_text


class _BatchClient:
    def __init__(self, content):
        self.files = SimpleNamespace(content=lambda _file_id: SimpleNamespace(text=content))


class StandaloneHardeningTest(unittest.TestCase):
    def test_partial_result_never_overwrites_existing_final(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input" / "episode.srt"
            output = root / "output" / "episode.srt"
            source.parent.mkdir()
            output.parent.mkdir()
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\nBye\n",
                encoding="utf-8",
            )
            output.write_text("old final", encoding="utf-8")
            fmap = {
                "one": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000"),
                "two": (str(source), 1, "2", "00:00:01,000 --> 00:00:02,000"),
            }
            content = (
                '{"custom_id":"one","response":{"body":{"choices":['
                '{"message":{"content":"Merhaba"}}]}}}'
            )
            with patch.object(standalone, "_get_client", return_value=_BatchClient(content)):
                result = standalone.process_results(
                    "output", fmap, [str(source)],
                    input_folder=str(source.parent), output_folder=str(output.parent),
                )

            self.assertEqual(result["failed_ids"], {"two"})
            self.assertEqual(result["skipped_files"], 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "old final")

    def test_duplicate_or_truncated_result_never_overwrites_existing_final(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input" / "episode.srt"
            output = root / "output" / "episode.srt"
            source.parent.mkdir()
            output.parent.mkdir()
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\nBye\n",
                encoding="utf-8",
            )
            fmap = {
                "one": (str(source), 0, "1", "00:00:00,000 --> 00:00:01,000"),
                "two": (str(source), 1, "2", "00:00:01,000 --> 00:00:02,000"),
            }
            cases = {
                "duplicate": (
                    '{"custom_id":"one","response":{"body":{"choices":['
                    '{"message":{"content":"Merhaba"}}]}}}\n'
                    '{"custom_id":"one","response":{"body":{"choices":['
                    '{"message":{"content":"Tekrar"}}]}}}\n'
                    '{"custom_id":"two","response":{"body":{"choices":['
                    '{"message":{"content":"HoÅŸÃ§a kal"}}]}}}'
                ),
                "truncated": (
                    '{"custom_id":"one","response":{"body":{"choices":['
                    '{"message":{"content":"Merhaba"}}]}}}\n'
                    '{"custom_id":"two","response":{"body":{"choices":['
                    '{"finish_reason":"length","message":{"content":"HoÅŸ"}}]}}}'
                ),
            }
            for name, content in cases.items():
                with self.subTest(name=name):
                    output.write_text("old final", encoding="utf-8")
                    with patch.object(standalone, "_get_client", return_value=_BatchClient(content)):
                        result = standalone.process_results(
                            "output", fmap, [str(source)],
                            input_folder=str(source.parent), output_folder=str(output.parent),
                        )
                    self.assertEqual(result["failed_ids"], {"one"} if name == "duplicate" else {"two"})
                    self.assertEqual(output.read_text(encoding="utf-8"), "old final")

    def test_nested_output_folder_is_not_discovered_as_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "subtitles"
            output = root / "translated"
            output.mkdir(parents=True)
            source = root / "source.srt"
            generated = output / "source.srt"
            source.write_text("source", encoding="utf-8")
            generated.write_text("generated", encoding="utf-8")

            found = standalone.discover_source_srt_files(str(root), str(output))

            self.assertEqual(found, [str(source)])

    def test_repair_preserves_existing_final_when_batch_is_partial(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "final.srt"
            fmap_path = root / "batch_fmap_batch-1.json"
            source.write_text("source", encoding="utf-8")
            output.write_text("old final", encoding="utf-8")
            fmap_path.write_text(json.dumps({
                "source_path": str(source),
                "source_hash": standalone._source_file_sha256(str(source)),
                "output_path": str(output),
                "fmap": {
                    "one": [[1, "00:00:00,000", "00:00:01,000"]],
                    "two": [[2, "00:00:01,000", "00:00:02,000"]],
                },
            }), encoding="utf-8")
            client = SimpleNamespace(
                batches=SimpleNamespace(retrieve=lambda _batch_id: SimpleNamespace(
                    status="completed", output_file_id="out")),
                files=SimpleNamespace(content=lambda _file_id: SimpleNamespace(text=(
                    '{"custom_id":"one","response":{"body":{"choices":['
                    '{"message":{"content":"[{\\"i\\":1,\\"t\\":\\"Yeni\\"}]"}}]}}}'
                ))),
            )
            with patch.object(repair_batches, "_get_client", return_value=client):
                repair_batches.main([str(fmap_path)])

            self.assertEqual(output.read_text(encoding="utf-8"), "old final")
            self.assertFalse(Path(str(output) + ".repair.bak").exists())

    def test_repair_rejects_source_hash_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "final.srt"
            fmap_path = root / "batch_fmap_batch-1.json"
            source.write_text("changed", encoding="utf-8")
            output.write_text("old final", encoding="utf-8")
            fmap_path.write_text(json.dumps({
                "source_path": str(source),
                "source_hash": "0" * 64,
                "output_path": str(output),
                "fmap": {"one": [[1, "00:00:00,000", "00:00:01,000"]]},
            }), encoding="utf-8")

            with patch.object(repair_batches, "_get_client") as get_client:
                repair_batches.main([str(fmap_path)])

            get_client.assert_called_once()
            self.assertEqual(output.read_text(encoding="utf-8"), "old final")

    def test_repair_writes_only_a_complete_unique_map_atomically(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "final.srt"
            fmap_path = root / "batch_fmap_batch-1.json"
            source.write_text("source", encoding="utf-8")
            output.write_text("old final", encoding="utf-8")
            fmap_path.write_text(json.dumps({
                "source_path": str(source),
                "source_hash": standalone._source_file_sha256(str(source)),
                "output_path": str(output),
                "fmap": {"one": [[1, "00:00:00,000", "00:00:01,000"]]},
            }), encoding="utf-8")
            client = SimpleNamespace(
                batches=SimpleNamespace(retrieve=lambda _batch_id: SimpleNamespace(
                    status="completed", output_file_id="out")),
                files=SimpleNamespace(content=lambda _file_id: SimpleNamespace(text=(
                    '{"custom_id":"one","response":{"body":{"choices":['
                    '{"message":{"content":"[{\\"i\\":1,\\"t\\":\\"Yeni\\"}]"}}]}}}'
                ))),
            )
            with patch.object(repair_batches, "_get_client", return_value=client), \
                    patch.object(repair_batches, "atomic_write_text", wraps=atomic_write_text) as writer:
                repair_batches.main([str(fmap_path)])

            writer.assert_called_once()
            self.assertEqual(output.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:01,000\nYeni\n\n")
            self.assertEqual(Path(str(output) + ".repair.bak").read_text(encoding="utf-8"), "old final")

    def test_repair_rejects_duplicate_cue_map_before_writing_final(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.srt"
            output = root / "final.srt"
            fmap_path = root / "batch_fmap_batch-1.json"
            source.write_text("source", encoding="utf-8")
            output.write_text("old final", encoding="utf-8")
            fmap_path.write_text(json.dumps({
                "source_path": str(source),
                "source_hash": standalone._source_file_sha256(str(source)),
                "output_path": str(output),
                "fmap": {
                    "one": [[1, "00:00:00,000", "00:00:01,000"]],
                    "two": [[1, "00:00:00,000", "00:00:01,000"]],
                },
            }), encoding="utf-8")

            with patch.object(repair_batches, "_get_client") as client:
                repair_batches.main([str(fmap_path)])

            client.assert_called_once()
            self.assertEqual(output.read_text(encoding="utf-8"), "old final")

    def test_video_cache_rejects_same_stat_different_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "film.mkv"
            source.write_bytes(b"AAAAA")
            original_stat = source.stat()
            stream = video.SubtitleStream(2, "ass", "eng")
            calls = []

            def runner(command, **_kwargs):
                calls.append(command)
                Path(command[-1]).write_text(f"run-{len(calls)}", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(video.tempfile, "gettempdir", return_value=td):
                first = video.extract_subtitle_stream(
                    source, stream, runner=runner, which=lambda name: name)
                source.write_bytes(b"BBBBB")
                os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                second = video.extract_subtitle_stream(
                    source, stream, runner=runner, which=lambda name: name)

            self.assertNotEqual(first, second)
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
