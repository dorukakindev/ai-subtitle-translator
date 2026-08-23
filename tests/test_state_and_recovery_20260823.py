# -*- coding: utf-8 -*-
"""Durum/kurtarma denetimi — çökme geri sayımı, tespit önbelleği, DUR sözleşmesi."""
import inspect
import os
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

NL = chr(10)


class CrashResumeDoesNotHijackTest(unittest.TestCase):
    """Geri sayım modal değil: 10 saniye içinde yeni koşu başlamış olabilir.

    Eskiden sayaç dolunca AKTİF koşunun dosya listesi eski yarım kuyrukla
    değiştiriliyor, eski ayarlar `_resume_snapshot_override`e yazılıyordu.
    """

    def _app(self, running):
        app = g.App.__new__(g.App)
        app._is_running = running
        app._is_shutting_down = False
        app._crash_resume_after_id = None
        app._crash_resume_dialog = None
        app._crash_resume_source_paths = set()
        app._crash_resume_record_path = ""
        app._selected_files = ["NEW.srt"]
        app._resume_snapshot_override = {"origin": "OLD-RUN"}
        app.logs = []
        app._log = lambda msg, level="info": app.logs.append((msg, level))
        app.after_cancel = lambda *a: None
        app._set_status = lambda *a, **k: None
        return app

    def test_an_active_run_is_never_replaced(self):
        app = self._app(running=True)
        g.App._restore_interrupted_run(app, {"settings": {}, "files": ["old.srt"]})
        self.assertEqual(app._selected_files, ["NEW.srt"])

    def test_the_stale_override_is_dropped(self):
        app = self._app(running=True)
        g.App._restore_interrupted_run(app, {"settings": {}, "files": ["old.srt"]})
        self.assertNotIn("_resume_snapshot_override", app.__dict__)

    def test_the_user_is_told_why(self):
        app = self._app(running=True)
        g.App._restore_interrupted_run(app, {"settings": {}, "files": ["old.srt"]})
        self.assertTrue(any("kurtarması iptal" in msg for msg, _lvl in app.logs))

    def test_shutdown_also_blocks_it(self):
        app = self._app(running=False)
        app._is_shutting_down = True
        g.App._restore_interrupted_run(app, {"settings": {}, "files": ["old.srt"]})
        self.assertEqual(app._selected_files, ["NEW.srt"])

    def test_starting_a_run_cancels_the_countdown(self):
        source = inspect.getsource(g.App._start)
        self.assertIn("_cancel_crash_resume(self, forget=False)", source)


class DetectionCacheRaceTest(unittest.TestCase):
    """Kilitsiz read-modify-write alan kaybediyordu.

    İki thread ile 100 turluk ölçümde her turda en az bir alan kayboldu,
    66 turda okunabilir sonuç bile kalmadı. Düzeltmeden sonra 100/100.
    """

    def _srt(self, folder):
        path = Path(folder) / "a.srt"
        path.write_text(
            "1" + NL + "00:00:01,000 --> 00:00:02,000" + NL + "Hello." + NL,
            encoding="utf-8")
        return path

    def test_concurrent_writes_keep_both_fields(self):
        for _round in range(12):
            with TemporaryDirectory() as td:
                srt = self._srt(td)
                threads = [
                    threading.Thread(
                        target=g.save_detection_cache,
                        args=(str(srt),), kwargs={"source_language": "French"}),
                    threading.Thread(
                        target=g.save_detection_cache,
                        args=(str(srt),), kwargs={"content_type": "Film"}),
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                data = g.load_detection_cache(str(srt))
                self.assertEqual(data.get("source_language"), "French")
                self.assertEqual(data.get("content_type"), "Film")

    def test_a_single_write_still_works(self):
        with TemporaryDirectory() as td:
            srt = self._srt(td)
            self.assertTrue(
                g.save_detection_cache(str(srt), content_type="Belgesel"))
            self.assertEqual(
                g.load_detection_cache(str(srt)).get("content_type"), "Belgesel")

    def test_clearing_a_field_still_works(self):
        with TemporaryDirectory() as td:
            srt = self._srt(td)
            g.save_detection_cache(str(srt), content_type="Belgesel",
                                   source_language="French")
            g.save_detection_cache(str(srt), content_type="Otomatik")
            data = g.load_detection_cache(str(srt))
            self.assertNotIn("content_type", data)
            self.assertEqual(data.get("source_language"), "French")

    def test_the_write_runs_under_the_shared_lock(self):
        source = inspect.getsource(g.save_detection_cache)
        self.assertIn("_interprocess_lock(path)", source)
        self.assertIn("_save_detection_cache_locked(", source)
        self.assertIn("atomic_write_json(path, data)",
                      inspect.getsource(g._save_detection_cache_locked))


class StopIsTerminalForPreflightTest(unittest.TestCase):
    """DUR'dan sonra ön analiz onay penceresi açılmamalı."""

    def test_both_api_preflights_check_the_stop_flag(self):
        for name in ("_start_content_type_preflight",
                     "_start_source_language_preflight"):
            with self.subTest(name=name):
                source = inspect.getsource(getattr(g.App, name))
                marker = source.index("def _finish():")
                window = source[marker:marker + 900]
                self.assertIn('getattr(self, "_stop_flag", False)', window)
                self.assertIn("onay penceresi açılmadı", window)


if __name__ == "__main__":
    unittest.main()
