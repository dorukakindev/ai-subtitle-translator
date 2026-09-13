import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import video_subtitles as vs


_SAMPLE_SUBTITLE = (
    "1\n"
    "00:00:01,000 --> 00:00:02,000\n"
    "Merhaba.\n"
)


class VideoSubtitleTests(unittest.TestCase):
    def test_probe_returns_text_and_bitmap_streams(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            payload = {
                "streams": [
                    {
                        "index": 2,
                        "codec_name": "subrip",
                        "tags": {"language": "eng", "title": "English"},
                    },
                    {
                        "index": 4,
                        "codec_name": "hdmv_pgs_subtitle",
                        "tags": {"language": "tur"},
                    },
                ]
            }
            runner = mock.Mock(return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(payload), stderr=""))
            streams = vs.probe_subtitle_streams(
                video, runner=runner, which=lambda _name: "ffprobe.exe")

        self.assertEqual([stream.index for stream in streams], [2, 4])
        self.assertTrue(streams[0].supported)
        self.assertFalse(streams[1].supported)
        command = runner.call_args.args[0]
        self.assertEqual(command[0], "ffprobe.exe")
        self.assertEqual(command[-1], str(video))
        self.assertIn("-select_streams", command)

    def test_probe_reports_missing_ffprobe(self):
        with self.assertRaisesRegex(vs.VideoSubtitleError, "bulunamadı"):
            vs._tool_path(
                "definitely-missing-video-tool",
                which=lambda _name: None,
            )

    def test_tool_path_falls_back_to_project_local_binary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            binary = root / "tools" / "ffmpeg" / "ffprobe.exe"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b"binary")
            with mock.patch.object(vs, "__file__", str(root / "video_subtitles.py")):
                resolved = vs._tool_path("ffprobe", which=lambda _name: None)
        self.assertEqual(resolved, str(binary))

    def test_probe_timeout_is_reported_without_hanging(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mp4"
            video.write_bytes(b"video")

            def runner(command, **_kwargs):
                raise vs.subprocess.TimeoutExpired(command, 30)

            with self.assertRaisesRegex(vs.VideoSubtitleError, "30 saniye"):
                vs.probe_subtitle_streams(
                    video, runner=runner, which=lambda _name: "ffprobe.exe")

    def test_probe_rejects_malformed_stream_payload(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mp4"
            video.write_bytes(b"video")
            runner = mock.Mock(return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"streams": {"index": 2}}), stderr=""))
            with self.assertRaisesRegex(vs.VideoSubtitleError, "geçersiz altyazı akışı listesi"):
                vs.probe_subtitle_streams(
                    video, runner=runner, which=lambda _name: "ffprobe.exe")

    def test_extracts_text_stream_atomically_and_records_origin(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "My Film.mkv"
            video.write_bytes(b"video")
            stream = vs.SubtitleStream(3, "subrip", "eng", "English")

            def runner(command, **_kwargs):
                Path(command[-1]).write_text(
                    "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                output = vs.extract_subtitle_stream(
                    video, stream, runner=runner,
                    which=lambda name: f"{name}.exe")
                self.assertTrue(output.is_file())
                self.assertEqual(vs.extracted_video_origin(output), video.resolve())
                self.assertEqual(vs.logical_subtitle_path(output).parent.resolve(), video.parent.resolve())
                self.assertIn("track-3.eng.srt", output.name)

    def test_cached_extraction_skips_second_ffmpeg_call(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            stream = vs.SubtitleStream(2, "ass", "ita")
            calls = []

            def runner(command, **_kwargs):
                calls.append(command)
                Path(command[-1]).write_text(_SAMPLE_SUBTITLE, encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                first = vs.extract_subtitle_stream(
                    video, stream, runner=runner,
                    which=lambda name: f"{name}.exe")
                second = vs.extract_subtitle_stream(
                    video, stream, runner=runner,
                    which=lambda name: f"{name}.exe")

            self.assertEqual(first, second)
            self.assertEqual(len(calls), 1)
            # ASS akışı SRT'ye dönüştürülmeden kopyalanmalı (konum etiketleri korunur)
            self.assertEqual(first.suffix, ".ass")
            self.assertIn("copy", calls[0])

    def test_corrupt_or_mismatched_cache_metadata_forces_reextraction(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            stream = vs.SubtitleStream(2, "ass", "ita")
            calls = []

            def runner(command, **_kwargs):
                calls.append(command)
                Path(command[-1]).write_text("fresh subtitle", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                output = (
                    vs._cache_root(video)
                    / "film.track-2.ita.ass"
                )
                output.parent.mkdir(parents=True)
                output.write_text("stale subtitle", encoding="utf-8")
                vs._origin_sidecar(output).write_text("{broken", encoding="utf-8")

                result = vs.extract_subtitle_stream(
                    video, stream, runner=runner,
                    which=lambda name: f"{name}.exe")
                self.assertEqual(result, output)
                self.assertEqual(len(calls), 1)
                self.assertEqual(
                    output.read_text(encoding="utf-8"), "fresh subtitle")
                self.assertEqual(
                    vs.extracted_video_origin(output), video.resolve())

    def test_rejects_bitmap_stream_without_running_ffmpeg(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            runner = mock.Mock()
            stream = vs.SubtitleStream(5, "dvd_subtitle", "eng")
            with self.assertRaisesRegex(vs.VideoSubtitleError, "OCR"):
                vs.extract_subtitle_stream(
                    video, stream, runner=runner,
                    which=lambda name: f"{name}.exe")
            runner.assert_not_called()

    def test_video_extension_detection_is_case_insensitive(self):
        self.assertTrue(vs.is_video_path("Film.MKV"))
        self.assertTrue(vs.is_video_path("Film.mp4"))
        self.assertFalse(vs.is_video_path("Film.srt"))
        self.assertFalse(vs.is_video_path("source.ts"))

    def test_logical_paths_distinguish_same_stem_video_extensions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mkv = root / "Film.mkv"
            mp4 = root / "Film.mp4"
            mkv.write_bytes(b"mkv")
            mp4.write_bytes(b"mp4")
            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                first = vs._cache_root(mkv) / "first.srt"
                second = vs._cache_root(mp4) / "second.srt"
                first.parent.mkdir(parents=True)
                second.parent.mkdir(parents=True)
                first.write_text(_SAMPLE_SUBTITLE, encoding="utf-8")
                second.write_text(_SAMPLE_SUBTITLE, encoding="utf-8")
                vs._write_json_atomic(vs._origin_sidecar(first), {
                    "source_video": str(mkv.resolve()), "language": "eng"})
                vs._write_json_atomic(vs._origin_sidecar(second), {
                    "source_video": str(mp4.resolve()), "language": "ita"})

                logical_first = vs.logical_subtitle_path(first)
                logical_second = vs.logical_subtitle_path(second)
                language = vs.extracted_video_language(first)

        self.assertNotEqual(logical_first, logical_second)
        self.assertEqual(language, "eng")

    def test_untrusted_origin_sidecar_cannot_redirect_output_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            video = root / "Film.mkv"
            subtitle = root / "downloaded.srt"
            video.write_bytes(b"video")
            subtitle.write_text(_SAMPLE_SUBTITLE, encoding="utf-8")
            vs._write_json_atomic(vs._origin_sidecar(subtitle), {
                "source_video": str(video.resolve()),
                "stream_index": 2,
                "codec": "subrip",
            })

            self.assertEqual(vs.extracted_video_metadata(subtitle), {})
            self.assertEqual(vs.logical_subtitle_path(subtitle), subtitle)


if __name__ == "__main__":
    unittest.main()
