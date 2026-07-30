"""
Deterministic unit tests for "Duraklat — mevcut dosya bitince duracak" (Pause between files) feature.
Directly invokes production App._wait_between_files and App._stop with stub objects.
Does NOT instantiate App() or open GUI windows.
"""
import inspect
import threading
import time
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class PauseBetweenFilesTest(unittest.TestCase):

    def setUp(self):
        self.logs = []
        self.statuses = []

    def _make_stub(self, stop_flag=False, paused=False):
        pause_event = threading.Event()
        if not paused:
            pause_event.set()

        stub = SimpleNamespace(
            _stop_flag=stop_flag,
            _pause_btw_files=pause_event,
            _log=lambda msg, tag="info": self.logs.append((msg, tag)),
            _set_status=lambda st: self.statuses.append(st),
            _removed_files=set(),
            _is_queued_file_removed=lambda self_stub, fp: fp in self_stub._removed_files if hasattr(self_stub, '_removed_files') else False,
        )
        return stub

    def test_wait_between_files_returns_continue_immediately_when_unpaused(self):
        """Verify _wait_between_files returns 'continue' instantly when not paused."""
        stub = self._make_stub(paused=False)
        res = gui.App._wait_between_files(stub, file_index=0, total_files=3, current_filename="file1.srt")
        self.assertEqual(res, "continue")

    def test_wait_between_files_returns_continue_immediately_on_last_file(self):
        """Verify _wait_between_files does not pause after the last file of a queue."""
        stub = self._make_stub(paused=True)  # even if pause is set
        res = gui.App._wait_between_files(stub, file_index=2, total_files=3, current_filename="file3.srt")
        self.assertEqual(res, "continue")

    def test_wait_between_files_pauses_until_set(self):
        """Verify worker pauses when pause_event is cleared, and resumes when set() is called."""
        stub = self._make_stub(paused=True)
        results = []

        def worker():
            r = gui.App._wait_between_files(stub, file_index=0, total_files=3, current_filename="file1.srt")
            results.append(r)

        t = threading.Thread(target=worker)
        t.start()

        time.sleep(0.1)
        self.assertEqual(len(results), 0, "Worker should be waiting in pause loop")

        # Resume execution
        stub._pause_btw_files.set()
        t.join(timeout=2.0)

        self.assertEqual(results, ["continue"])
        self.assertTrue(any("Duraklatıldı" in log[0] for log in self.logs))
        self.assertTrue(any("Devam ediliyor" in log[0] for log in self.logs))

    def test_wait_between_files_wakes_and_returns_stopped_on_stop_flag(self):
        """Verify worker wakes up within ~0.3s and returns 'stopped' when _stop_flag becomes True."""
        stub = self._make_stub(paused=True)
        results = []

        def worker():
            r = gui.App._wait_between_files(stub, file_index=0, total_files=3, current_filename="file1.srt")
            results.append(r)

        t = threading.Thread(target=worker)
        t.start()

        time.sleep(0.1)
        self.assertEqual(len(results), 0)

        # Trigger stop (as _stop() does)
        stub._stop_flag = True
        stub._pause_btw_files.set()
        start = time.time()
        t.join(timeout=2.0)
        elapsed = time.time() - start

        self.assertEqual(results, ["stopped"])
        self.assertLess(elapsed, 1.0, f"Expected wake under 1s, took {elapsed:.2f}s")

    def test_stop_method_sets_stop_flag_and_wakes_pause_event(self):
        """Verify App._stop sets _stop_flag=True and calls _pause_btw_files.set()."""
        stub = SimpleNamespace(
            _stop_flag=False,
            _pause_btw_files=threading.Event(),  # cleared (paused)
            _log=lambda *a, **k: None,
            _set_status=lambda *a, **k: None,
            _batch_lock=threading.Lock(),
            _active_batches={},
        )
        self.assertFalse(stub._pause_btw_files.is_set())

        gui.App._stop(stub)

        self.assertTrue(stub._stop_flag)
        self.assertTrue(stub._pause_btw_files.is_set(), "_stop must wake pause_btw_files event")

    def test_multi_file_loop_pause_and_stop_semantics(self):
        """Simulate a 3-file execution loop: pause after file 1, then stop. File 2 and 3 must not run."""
        stub = self._make_stub(paused=False)
        processed_files = []
        files = ["file1.srt", "file2.srt", "file3.srt"]

        for fi, fname in enumerate(files):
            # Process file
            processed_files.append(fname)
            
            # After file 1 finishes, user clicks Pause
            if fname == "file1.srt":
                stub._pause_btw_files.clear()
                # Then user clicks Stop while paused
                stub._stop_flag = True
                stub._pause_btw_files.set()

            if gui.App._wait_between_files(stub, fi, len(files), fname) == "stopped":
                break

        self.assertEqual(processed_files, ["file1.srt"], "Only file 1 should have been processed")

    def test_queue_removal_during_pause(self):
        """Simulate pausing after file 1, removing file 2 from queue, then resuming. File 2 must be skipped."""
        stub = self._make_stub(paused=False)
        processed_files = []
        files = ["file1.srt", "file2.srt", "file3.srt"]

        for fi, fname in enumerate(files):
            if stub._is_queued_file_removed(stub, fname):
                continue

            processed_files.append(fname)

            if fname == "file1.srt":
                stub._pause_btw_files.clear()
                # Remove file 2 from queue while paused
                stub._removed_files.add("file2.srt")

                # Resume worker in background
                def resume_after_delay():
                    time.sleep(0.1)
                    stub._pause_btw_files.set()
                threading.Thread(target=resume_after_delay).start()

            if gui.App._wait_between_files(stub, fi, len(files), fname) == "stopped":
                break

        self.assertEqual(processed_files, ["file1.srt", "file3.srt"], "file2.srt should have been skipped")

    def test_source_code_inspection_for_pause_checkpoints(self):
        """Verify source code of _run_sync_hybrid, _write_results, and _resume_batches contains _wait_between_files calls."""
        methods_to_check = [
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
            ("_write_results", gui.App._write_results),
            ("_resume_batches", gui.App._resume_batches),
        ]

        for name, method in methods_to_check:
            src = inspect.getsource(method)
            self.assertIn("_wait_between_files", src, f"Missing _wait_between_files checkpoint in {name}")

    def test_partial_write_does_not_clear_recovery_or_report_success(self):
        """A stop at the pause boundary must remain recoverable and suppress completion UI."""
        run_sync = inspect.getsource(gui.App._run_sync)
        run_batch = inspect.getsource(gui.App._run_batch)
        resume = inspect.getsource(gui.App._resume_batches)
        write_results = inspect.getsource(gui.App._write_results)

        self.assertIn(
            "is_full_success = bool(_all_written and not unresolved)", run_sync)
        self.assertIn(
            "should_clear_sync_ckpt(self._stop_flag, is_full_success)", run_sync)
        self.assertIn("final_written = self._write_results(", run_batch)
        self.assertIn("regular_written = self._write_results(", resume)
        self.assertIn('if not summary["is_full_success"]:', write_results)
        self.assertIn('return summary["is_recovery_complete"]', write_results)

    def test_sync_hybrid_marks_file_done_before_pause_checkpoint(self):
        """A fully written file stays visibly complete if Stop is pressed while paused."""
        src = inspect.getsource(gui.App._run_sync_hybrid)
        done_at = src.index('f"Tamamlandı  {len(sorted_blocks)} satır"')
        pause_at = src.index(
            "self._wait_between_files(fi, n_files, fname)", done_at)
        self.assertLess(done_at, pause_at)


if __name__ == "__main__":
    unittest.main()
