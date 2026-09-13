import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import subtitle_translator_gui as gui
import video_subtitles as vs


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class VideoSubtitleGuiTests(unittest.TestCase):
    def test_same_folder_output_uses_original_video_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            video_dir = root / "videos"
            video_dir.mkdir()
            video = video_dir / "Film.mkv"
            video.write_bytes(b"video")
            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                extracted = vs._cache_root(video) / "Film.track-2.eng.srt"
                extracted.parent.mkdir(parents=True)
                extracted.write_text("subtitle", encoding="utf-8")
                vs._write_json_atomic(vs._origin_sidecar(extracted), {
                    "source_video": str(video.resolve()),
                })

                output = gui._resolve_output_path(
                    "", "", str(extracted), same_folder=True)

        self.assertEqual(output, video_dir / "Film.mkv.track-2.eng.tr.srt")

    def test_extracted_subtitles_append_without_replacing_queue(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = root / "old.srt"
            video = root / "video.mkv"
            old.write_text("old", encoding="utf-8")
            video.write_bytes(b"video")
            messages = []
            language_vars = {}

            def refresh(message):
                messages.append(message)
                language_vars[str(new)] = _Var("English")

            with mock.patch.object(vs.tempfile, "gettempdir", return_value=td):
                new = vs._cache_root(video) / "new.srt"
                new.parent.mkdir(parents=True)
                new.write_text("new", encoding="utf-8")
                vs._write_json_atomic(vs._origin_sidecar(new), {
                    "source_video": str(video.resolve()),
                    "language": "ita",
                })
                stub = SimpleNamespace(
                    _selected_files=[str(old)],
                    _input_folder_explicitly_selected=False,
                    input_var=_Var(""),
                    _content_type_preflight_done=True,
                    _language_preflight_done=True,
                    _pm=object(),
                    _dedupe_paths=lambda paths: list(dict.fromkeys(paths)),
                    _refresh_selected_files_ui=refresh,
                    _file_language_vars=language_vars,
                )

                added = gui.App._append_extracted_video_subtitles(
                    stub, [str(new)])

        self.assertEqual(added, 1)
        self.assertEqual(stub._selected_files, [str(old), str(new)])
        self.assertFalse(stub._content_type_preflight_done)
        self.assertFalse(stub._language_preflight_done)
        self.assertIsNone(stub._pm)
        self.assertIn("Videodan +1", messages[0])
        self.assertEqual(language_vars[str(new)].get(), "Italian")

    def test_drop_handler_routes_video_to_probe(self):
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "Film.MKV"
            video.write_bytes(b"video")
            probed = []
            logs = []
            stub = SimpleNamespace(
                _is_running=False,
                tk=SimpleNamespace(splitlist=lambda _data: [str(video)]),
                _selected_files=[],
                _queue_video_probe=lambda paths: probed.extend(paths),
                _log=lambda message, level: logs.append((message, level)),
            )

            gui.App._on_drop(stub, SimpleNamespace(data=str(video)))

        self.assertEqual(probed, [str(video)])
        self.assertEqual(logs, [])

    def test_video_probe_runs_off_ui_thread_via_worker(self):
        started = []
        stub = SimpleNamespace(
            _is_running=False,
            _video_import_busy=False,
            _dedupe_paths=lambda paths: paths,
            _set_status=lambda _message: None,
            _log=lambda _message, _level: None,
        )
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            with mock.patch.object(
                    gui.App, "_start_worker",
                    side_effect=lambda _self, target: started.append(target)):
                gui.App._queue_video_probe(stub, [str(video)])

        self.assertEqual(len(started), 1)
        self.assertTrue(stub._video_import_busy)

    def test_video_probe_worker_start_failure_releases_busy_state(self):
        statuses = []
        logs = []
        stub = SimpleNamespace(
            _is_running=False,
            _video_import_busy=False,
            _dedupe_paths=lambda paths: paths,
            _set_status=statuses.append,
            _log=lambda message, level: logs.append((message, level)),
        )
        with tempfile.TemporaryDirectory() as td:
            video = Path(td) / "film.mkv"
            video.write_bytes(b"video")
            with mock.patch.object(
                    gui.App, "_start_worker", side_effect=RuntimeError("no threads")):
                gui.App._queue_video_probe(stub, [str(video)])

        self.assertFalse(stub._video_import_busy)
        self.assertTrue(statuses)
        self.assertEqual(logs[0][1], "err")

    def test_video_track_language_uses_stream_tag_and_falls_back_to_auto(self):
        self.assertEqual(gui._video_track_language("eng"), "English")
        self.assertEqual(gui._video_track_language("it-IT"), "Italian")
        self.assertEqual(gui._video_track_language("unrecognized"), gui.AUTO_LANGUAGE)


if __name__ == "__main__":
    unittest.main()
