"""
Deterministic unit tests for UI Dispatcher and thread safety.
Directly tests App._post_ui, App._drain_ui_queue, App._take_run_snapshot, and worker UI isolation.
Does NOT instantiate App() or open GUI windows.
"""
import inspect
import queue
import threading
import time
import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class UIDispatcherTest(unittest.TestCase):

    def setUp(self):
        self.executed_callbacks = []
        self.errors = []

    def _make_dispatcher_stub(self):
        stub = SimpleNamespace(
            _ui_queue=queue.Queue(),
            _is_shutting_down=False,
            _drain_ui_queue_id=None,
            _log_lock=threading.Lock(),
            _log_file=SimpleNamespace(write=lambda s: None, flush=lambda: None),
            _log_pinned=True,
            notify_var=SimpleNamespace(get=lambda: True),
            _active_snapshot={"notify_desktop": True},
            after=lambda delay, fn, *args: setattr(stub, '_drain_ui_queue_id', 'scheduled'),
        )

        # Bind methods to stub
        stub._post_ui = gui.App._post_ui.__get__(stub, gui.App)
        stub._drain_ui_queue = gui.App._drain_ui_queue.__get__(stub, gui.App)
        return stub

    def test_worker_thread_post_ui_enqueues_callback_without_immediate_execution(self):
        """1. Worker thread _post_ui enqueues callback without running it immediately."""
        stub = self._make_dispatcher_stub()
        results = []

        def cb(msg):
            results.append(msg)

        def worker():
            stub._post_ui(cb, "from_worker")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(len(results), 0, "Callback must NOT run immediately on worker thread")
        self.assertEqual(stub._ui_queue.qsize(), 1, "Callback must be queued in _ui_queue")

    def test_main_thread_drain_ui_queue_executes_fifo(self):
        """2. Main thread drain_ui_queue executes callbacks in FIFO order."""
        stub = self._make_dispatcher_stub()
        order = []

        stub._post_ui(lambda x: order.append(x), 1)
        stub._post_ui(lambda x: order.append(x), 2)
        stub._post_ui(lambda x: order.append(x), 3)

        # Force execution on main thread
        stub._drain_ui_queue()

        self.assertEqual(order, [1, 2, 3], "Callbacks must be drained in FIFO order")
        self.assertEqual(stub._ui_queue.qsize(), 0)

    def test_callback_exception_does_not_halt_queue(self):
        """3. A failing callback does not break execution of subsequent queued callbacks."""
        stub = self._make_dispatcher_stub()
        results = []

        def failing_cb():
            raise RuntimeError("Test error")

        def working_cb():
            results.append("success")

        # Worker enqueues failing then working callback
        def worker():
            stub._post_ui(failing_cb)
            stub._post_ui(working_cb)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Drain on main thread
        stub._drain_ui_queue()

        self.assertEqual(results, ["success"], "Subsequent callbacks must execute despite earlier exception")

    def test_shutdown_prevents_callback_execution_and_rescheduling(self):
        """4. Shutdown prevents further callback execution and cancels rescheduling."""
        stub = self._make_dispatcher_stub()
        results = []

        def cb():
            results.append("ran")

        def worker():
            stub._post_ui(cb)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Set shutdown flag before drain
        stub._is_shutting_down = True
        stub._drain_ui_queue()

        self.assertEqual(len(results), 0, "No callback should run after shutdown")
        self.assertNotEqual(getattr(stub, '_drain_ui_queue_id', None), 'scheduled')

    def test_set_status_set_progress_set_running_log_do_not_call_self_after_on_worker(self):
        """5. _set_status, _set_progress, _set_running, _log use _post_ui when on worker thread."""
        stub = self._make_dispatcher_stub()
        after_calls = []

        stub.after = lambda *a, **k: after_calls.append(a)
        stub.progress_lbl = SimpleNamespace(configure=lambda **k: None)
        stub.progress = SimpleNamespace(set=lambda v: None)
        stub.start_btn = SimpleNamespace(configure=lambda **k: None)
        stub.log_box = SimpleNamespace(configure=lambda **k: None, insert=lambda *a: None, see=lambda *a: None)

        # Bind UI helper methods
        stub._set_status = gui.App._set_status.__get__(stub, gui.App)
        stub._set_progress = gui.App._set_progress.__get__(stub, gui.App)
        stub._set_running = gui.App._set_running.__get__(stub, gui.App)
        stub._log = gui.App._log.__get__(stub, gui.App)

        def worker():
            stub._set_status("Translating...")
            stub._set_progress(50)
            stub._set_running(True)
            stub._log("Worker log line", "info")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(len(after_calls), 0, "Worker thread MUST NOT invoke self.after(0) directly")
        self.assertGreater(stub._ui_queue.qsize(), 0, "Worker updates must be queued in _ui_queue")

    def test_modal_callback_runs_via_dispatcher_and_resolves_event(self):
        """6. Modal callbacks run via dispatcher on main thread and set done_event."""
        stub = self._make_dispatcher_stub()
        done_event = threading.Event()
        dialog_opened = []

        def mock_show_dialog(issues, approved, event):
            dialog_opened.append(True)
            event.set()

        stub._show_qc_dialog = mock_show_dialog

        def worker():
            stub._post_ui(stub._show_qc_dialog, ["issue1"], [], done_event)

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertFalse(done_event.is_set(), "Modal callback must wait for main thread drain")

        # Drain on main thread
        stub._drain_ui_queue()

        self.assertTrue(done_event.is_set(), "Modal callback on main thread must resolve done_event")
        self.assertTrue(dialog_opened[0])

    def test_stop_wait_unblocks_worker_during_modal_wait(self):
        """7. Stop/close during modal wait unblocks worker within ~0.2s without hanging."""
        stub = SimpleNamespace(
            _stop_flag=False,
            _is_shutting_down=False,
            _ui_queue=queue.Queue(),
            _dismiss_modal_dialog=lambda target_event=None: None,
        )
        stub._post_ui = gui.App._post_ui.__get__(stub, gui.App)

        event = threading.Event()
        start = time.time()

        # Trigger stop in background
        def stop_trigger():
            time.sleep(0.05)
            stub._stop_flag = True

        t_stop = threading.Thread(target=stop_trigger)
        t_stop.start()

        status = gui.App._wait_for_dialog_event(stub, event, timeout=300)
        elapsed = time.time() - start

        self.assertEqual(status, "stopped")
        self.assertLess(elapsed, 1.0, f"Worker must unblock under 1s, took {elapsed:.2f}s")

    def test_workflow_ui_updates_use_post_ui_or_snapshot(self):
        """8. Source code inspection verifies sync/batch/hybrid flows use _post_ui or snapshot."""
        methods = [
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
            ("_write_results", gui.App._write_results),
            ("_run_batch", gui.App._run_batch),
            ("_run_hybrid", gui.App._run_hybrid),
        ]

        for name, method in methods:
            src = inspect.getsource(method)
            self.assertNotIn("self.after(0,", src, f"Direct self.after(0) found in {name}")

    def test_take_run_snapshot_produces_plain_dict(self):
        """9. _take_run_snapshot produces plain Python dict without live Tk variables."""
        stub = SimpleNamespace(
            input_var=SimpleNamespace(get=lambda: "D:/in"),
            output_var=SimpleNamespace(get=lambda: "D:/out"),
            src_var=SimpleNamespace(get=lambda: "en"),
            tgt_var=SimpleNamespace(get=lambda: "tr"),
            profanity_var=SimpleNamespace(get=lambda: False),
            same_folder_var=SimpleNamespace(get=lambda: False),
            mode_var=SimpleNamespace(get=lambda: "sync"),
            hybrid_mode_var=SimpleNamespace(get=lambda: True),
            auto_glossary_var=SimpleNamespace(get=lambda: False),
            analysis_depth_var=SimpleNamespace(get=lambda: "standard"),
            ext_project_path_var=SimpleNamespace(get=lambda: SimpleNamespace(strip=lambda: "")),
            notify_var=SimpleNamespace(get=lambda: True),
            term_normalize_var=SimpleNamespace(get=lambda: False),
            critic_var=SimpleNamespace(get=lambda: True),
            polish_var=SimpleNamespace(get=lambda: True),
            native_var=SimpleNamespace(get=lambda: True),
            qc_var=SimpleNamespace(get=lambda: True),
            condense_var=SimpleNamespace(get=lambda: False),
            review_pass_var=SimpleNamespace(get=lambda: False),
            twowave_var=SimpleNamespace(get=lambda: False),
            clean_sdh_var=SimpleNamespace(get=lambda: True),
            linebreak_var=SimpleNamespace(get=lambda: True),
            _get_srt_files=lambda: [],
        )

        stub._take_run_snapshot = gui.App._take_run_snapshot.__get__(stub, gui.App)
        snap = stub._take_run_snapshot()

        self.assertIsInstance(snap, dict)
        self.assertEqual(snap["input_dir"], "D:/in")
        self.assertEqual(snap["src_lang"], "en")
        self.assertTrue(snap["notify_desktop"])

    def test_no_direct_self_after_zero_calls_remain_in_gui(self):
        """10. Verify zero self.after(0) calls remain in subtitle_translator_gui.py."""
        src = inspect.getsource(gui)
        self.assertNotIn("self.after(0,", src, "Zero self.after(0) calls must remain in GUI module")


if __name__ == "__main__":
    unittest.main()
