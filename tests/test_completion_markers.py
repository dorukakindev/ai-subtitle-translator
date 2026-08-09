import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class CompletionMarkerTest(unittest.TestCase):
    def _record(self, root, files):
        return {
            "run_id": "run-marker",
            "started_at": "2026-07-31T20:00:00",
            "ended_at": "2026-07-31T20:10:00",
            "status": "tamamlandı",
            "settings": {
                "output_dir": str(root / "ÇIKIŞ"),
                "selected_folder_roots": [str(root)],
            },
            "files": files,
            "outputs": [],
            "reports": [],
            "completion_markers": [],
            "fixes_applied": 0,
            "suggestions_rejected": 0,
            "warnings": 0,
            "errors": 0,
            "log_path": "run.log",
            "last_traceback": "",
        }

    def test_writes_marker_only_when_every_file_in_root_is_done(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "film"
            root.mkdir()
            first = root / "one.srt"
            second = root / "two.srt"
            first.write_text("source", encoding="utf-8")
            second.write_text("source", encoding="utf-8")
            record = self._record(root, {
                str(first): {"status": "done"},
                str(second): {"status": "error"},
            })
            self.assertEqual(gui._write_completion_markers(record), [])
            self.assertFalse((root / "ÇEVRİLDİ.txt").exists())

            record["files"][str(second)]["status"] = "done"
            markers = gui._write_completion_markers(record)
            marker = root / "ÇEVRİLDİ.txt"
            self.assertEqual(markers, [str(marker)])
            text = marker.read_text(encoding="utf-8")
            self.assertIn("ÇEVRİLDİ", text)
            self.assertIn("Çevrilen altyazı sayısı: 2", text)
            self.assertIn("one.srt", text)
            self.assertIn("two.srt", text)

    def test_nested_selected_root_gets_its_own_marker(self):
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td) / "series"
            season = parent / "season 1"
            season.mkdir(parents=True)
            source = season / "episode 1.srt"
            source.write_text("source", encoding="utf-8")
            record = self._record(parent, {str(source): {"status": "done"}})
            record["settings"]["selected_folder_roots"] = [str(parent), str(season)]
            markers = gui._write_completion_markers(record)
            self.assertEqual(markers, [str(season / "ÇEVRİLDİ.txt")])
            self.assertFalse((parent / "ÇEVRİLDİ.txt").exists())

    def test_does_not_mark_whole_root_when_unselected_subtitle_remains(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "series"
            root.mkdir()
            selected = root / "episode 1.srt"
            unselected = root / "episode 2.srt"
            selected.write_text("source", encoding="utf-8")
            unselected.write_text("source", encoding="utf-8")
            record = self._record(root, {
                str(selected): {"status": "done"},
            })

            self.assertEqual(gui._write_completion_markers(record), [])
            self.assertFalse((root / "ÇEVRİLDİ.txt").exists())

    def test_finalize_writes_marker_and_records_it_in_summary(self):
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            root = temp / "movie"
            root.mkdir()
            source = root / "movie.srt"
            source.write_text("source", encoding="utf-8")
            record = self._record(root, {str(source): {"status": "done"}})
            record["status"] = "çalışıyor"
            stub = SimpleNamespace(
                _run_record_lock=threading.RLock(),
                _active_run_record=record,
                _last_run_record=None,
                _stop_flag=False,
                _log=MagicMock(),
            )
            with patch.object(gui, "_resolve_report_dir", return_value=temp), \
                    patch.object(
                        gui, "state_path",
                        side_effect=lambda _file, *parts: temp.joinpath(*parts)):
                result = gui.App._finalize_run_record(stub)
            marker = root / "ÇEVRİLDİ.txt"
            self.assertTrue(marker.exists())
            self.assertEqual(result["completion_markers"], [str(marker)])
            summary = (temp / "calistirma_run-marker_ozet.txt").read_text(
                encoding="utf-8")
            self.assertIn("ÇEVRİLDİ işaretleri", summary)
            self.assertIn(str(marker), summary)

    def test_diagnostic_settings_preserve_selected_roots_without_keys(self):
        snapshot = {
            "input_dir": "C:/in",
            "output_dir": "C:/out",
            "selected_folder_roots": ("C:/in/movie",),
            "main_api_key": "sk-secret",
        }
        result = gui.App._diagnostic_run_settings(SimpleNamespace(), snapshot)
        self.assertEqual(result["selected_folder_roots"], ["C:/in/movie"])
        self.assertNotIn("main_api_key", result)


if __name__ == "__main__":
    unittest.main()
