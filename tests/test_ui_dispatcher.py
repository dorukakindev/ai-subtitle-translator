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
from unittest import mock

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

        def worker():
            stub._post_ui(lambda x: order.append(x), 1)
            stub._post_ui(lambda x: order.append(x), 2)
            stub._post_ui(lambda x: order.append(x), 3)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertEqual(order, [])
        self.assertEqual(stub._ui_queue.qsize(), 3)

        # Force execution on main thread
        stub._drain_ui_queue()

        self.assertEqual(order, [1, 2, 3], "Callbacks must be drained in FIFO order")
        self.assertEqual(stub._ui_queue.qsize(), 0)

    def test_worker_without_initialized_queue_never_falls_back_to_tk(self):
        calls = []
        stub = SimpleNamespace(
            _is_shutting_down=False,
            after=lambda *args: calls.append("after"),
        )
        callback = lambda: calls.append("callback")

        thread = threading.Thread(target=gui._post_ui, args=(stub, callback))
        thread.start()
        thread.join()

        self.assertEqual(calls, [])

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

    def test_drain_yields_when_time_budget_is_exhausted(self):
        stub = self._make_dispatcher_stub()
        delays = []
        stub.after = lambda delay, fn, *args: delays.append(delay)
        results = []
        for value in range(3):
            stub._ui_queue.put((lambda item=value: results.append(item), (), {}))

        with mock.patch.object(gui.time, "monotonic", side_effect=[0.0, 0.02]):
            stub._drain_ui_queue()

        self.assertEqual(results, [0])
        self.assertEqual(stub._ui_queue.qsize(), 2)
        self.assertEqual(delays, [1])

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

    def test_workflow_ui_updates_do_not_schedule_after_zero(self):
        """8. Source code inspection verifies flows do not schedule Tk callbacks from workers."""
        methods = [
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
            ("_write_results", gui.App._write_results),
            ("_run_batch", gui.App._run_batch),
            ("_run_hybrid", gui.App._run_hybrid),
        ]

        for name, method in methods:
            src = inspect.getsource(method)
            self.assertNotIn("self.after(0,", src, f"Direct self.after(0) found in {name}")

    def test_dispatcher_state_is_initialized_before_first_poll(self):
        src = inspect.getsource(gui.App.__init__)
        self.assertLess(src.index("self._ui_queue"), src.index("self._drain_ui_queue)"))
        self.assertIn("self._is_shutting_down", src)

    def test_cancelled_close_keeps_dispatcher_alive(self):
        queued = queue.Queue()
        queued.put((lambda: None, (), {}))
        stub = SimpleNamespace(
            _is_running=True,
            _is_shutting_down=False,
            _ui_queue=queued,
            _drain_ui_queue_id="tick",
            after_cancel=mock.Mock(),
            destroy=mock.Mock(),
            _stop_elapsed_timer=mock.Mock(),
            _save_settings=mock.Mock(),
            _tm=None,
            _log_file=None,
        )

        with mock.patch("subtitle_translator_gui.messagebox.askyesno", return_value=False):
            gui.App._on_close(stub)

        self.assertFalse(stub._is_shutting_down)
        self.assertEqual(queued.qsize(), 1)
        stub.after_cancel.assert_not_called()
        stub.destroy.assert_not_called()

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
            hybrid_var=SimpleNamespace(get=lambda: True),
            auto_glossary_var=SimpleNamespace(get=lambda: False),
            analysis_depth_var=SimpleNamespace(get=lambda: "standard"),
            ext_project_path_var=SimpleNamespace(get=lambda: SimpleNamespace(strip=lambda: "")),
            notify_var=SimpleNamespace(get=lambda: True),
            shutdown_when_done_var=SimpleNamespace(get=lambda: False),
            term_normalize_var=SimpleNamespace(get=lambda: False),
            critic_var=SimpleNamespace(get=lambda: True),
            polish_var=SimpleNamespace(get=lambda: True),
            native_var=SimpleNamespace(get=lambda: True),
            qc_var=SimpleNamespace(get=lambda: True),
            condense_var=SimpleNamespace(get=lambda: False),
            backtrans_var=SimpleNamespace(get=lambda: False),
            semantic_reconcile_var=SimpleNamespace(get=lambda: True),
            review_pass_var=SimpleNamespace(get=lambda: False),
            twowave_var=SimpleNamespace(get=lambda: False),
            clean_sdh_var=SimpleNamespace(get=lambda: True),
            linebreak_var=SimpleNamespace(get=lambda: True),
            ai_segment_var=SimpleNamespace(get=lambda: False),
            merge_cues_var=SimpleNamespace(get=lambda: False),
            chain_ctx_var=SimpleNamespace(get=lambda: True),
            precontext_var=SimpleNamespace(get=lambda: False),
            series_memory_var=SimpleNamespace(get=lambda: False),
            season_canon_var=SimpleNamespace(get=lambda: False),
            media_mode_var=SimpleNamespace(get=lambda: "Dizi"),
            prevent_sleep_var=SimpleNamespace(get=lambda: True),
            auto_retry_files_var=SimpleNamespace(get=lambda: True),
            auto_resume_crash_var=SimpleNamespace(get=lambda: True),
            workflow_profile_var=SimpleNamespace(get=lambda: "Özel"),
            content_type_var=SimpleNamespace(get=lambda: "Otomatik"),
            glossary_var=SimpleNamespace(get=lambda: SimpleNamespace(strip=lambda: "")),
            _get_srt_files=lambda: [],
            _main_api_key=lambda: "sk-test",
            _main_api_base_url=lambda: "https://api.openai.com/v1",
            _main_model_name=lambda: "gpt-4o",
            _get_schema=lambda: {"name": "Otomatik"},
            _helper_api_key=lambda role: "hk-test",
            _helper_api_base_url=lambda role: "https://api.openai.com/v1",
            _helper_api_model=lambda role: "gpt-4o-mini",
            _file_schema_vars={},
            _chunk_size=25,
            _context_lines=20,
            _lookahead_lines=10,
            _max_workers=4,
            _temperature=0.2,
            _max_retry=3,
            _scene_gap_seconds=3.0,
        )

        stub._take_run_snapshot = gui.App._take_run_snapshot.__get__(stub, gui.App)
        snap = stub._take_run_snapshot()

        self.assertIsInstance(snap, dict)
        self.assertEqual(snap["input_dir"], "D:/in")
        self.assertEqual(snap["src_lang"], "en")
        self.assertTrue(snap["notify_desktop"])
        self.assertFalse(snap["shutdown_when_done"])
        self.assertTrue(snap["hybrid_mode"])
        # New fields
        self.assertEqual(snap["main_api_key"], "sk-test")
        self.assertEqual(snap["main_model_name"], "gpt-4o")
        self.assertIn("helper_keys", snap)
        self.assertEqual(snap["helper_keys"]["critic"], "hk-test")
        self.assertFalse(snap["ai_segment"])
        self.assertTrue(snap["chain_ctx"])
        self.assertTrue(snap["semantic_reconcile"])

    def test_worker_thread_reads_snapshot_not_tk_vars(self):
        """Worker-called methods read from snapshot when on background thread."""
        stub = SimpleNamespace(
            _active_snapshot={
                "main_api_key": "snap-key",
                "main_api_base_url": "https://snap.example.com/v1",
                "main_model_name": "snap-model",
                "helper_keys": {"critic": "snap-hk"},
                "helper_urls": {"critic": "https://snap-helper.example.com/v1"},
                "helper_models": {"critic": "snap-helper-model"},
                "file_schemas": {"/test.srt": {"name": "Anime"}},
                "file_glossaries": {"/test.srt": "/glossary.json"},
                "global_glossary_path": "/global.json",
                "schema": {"name": "Otomatik"},
                "ai_segment": True,
                "merge_cues": False,
            },
            _file_schema_vars={},
            _main_custom_active=lambda: False,
            api_key_entry=SimpleNamespace(get=lambda: "SHOULD-NOT-READ"),
            main_custom_key_entry=SimpleNamespace(get=lambda: "SHOULD-NOT-READ"),
            api_url_var=SimpleNamespace(get=lambda: "SHOULD-NOT-READ"),
            model_var=SimpleNamespace(get=lambda: "SHOULD-NOT-READ"),
            glossary_var=SimpleNamespace(get=lambda: SimpleNamespace(strip=lambda: "SHOULD-NOT-READ")),
            content_type_var=SimpleNamespace(get=lambda: "SHOULD-NOT-READ"),
        )
        results = {}

        def worker():
            results["api_key"] = gui.App._main_api_key(stub)
            results["base_url"] = gui.App._main_api_base_url(stub)
            results["model"] = gui.App._main_model_name(stub)
            results["helper_key"] = gui.App._helper_api_key(stub, "critic")
            results["file_schema"] = gui.App._get_file_schema(stub, "/test.srt")
            results["file_glossary"] = gui.App._get_file_glossary(stub, "/test.srt")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        self.assertEqual(results["api_key"], "snap-key")
        self.assertEqual(results["base_url"], "https://snap.example.com/v1")
        self.assertEqual(results["model"], "snap-model")
        self.assertEqual(results["helper_key"], "snap-hk")
        self.assertEqual(results["file_schema"]["name"], "Anime")
        self.assertEqual(results["file_glossary"], "/glossary.json")

    def test_start_and_resume_capture_snapshot_before_worker_launch(self):
        start_src = inspect.getsource(gui.App._start)
        resume_src = inspect.getsource(gui.App._resume)
        self.assertLess(
            start_src.index("self._active_snapshot = self._take_run_snapshot()"),
            start_src.index("App._start_worker(self,"),
        )
        self.assertLess(
            resume_src.index("self._active_snapshot = self._take_run_snapshot()"),
            resume_src.index("App._start_worker(self, _guarded_resume"),
        )

    def test_auxiliary_workers_do_not_read_tk_variables(self):
        test_src = inspect.getsource(gui.App._test_translate)
        test_worker = test_src[test_src.index("def _run():"):]
        for forbidden in (
            "self._main_api_base_url()",
            "self._get_file_schema(",
            "self._get_file_glossary(",
            "self.profanity_var.get()",
            "self.chain_ctx_var.get()",
        ):
            self.assertNotIn(forbidden, test_worker)

        post_src = inspect.getsource(gui.App._run_post_process)
        for forbidden in (
            "self.tgt_var.get()",
            "self.analysis_depth_var.get()",
            "self.ext_project_path_var.get()",
            "self._helper_api_key(",
            "self._helper_api_base_url(",
            "self._helper_api_model(",
            "self._get_file_glossary(",
        ):
            self.assertNotIn(forbidden, post_src)

        content_src = inspect.getsource(gui.App._start_content_type_preflight)
        content_worker = content_src[content_src.index("def _worker():"):]
        self.assertNotIn("self._main_api_base_url()", content_worker)

    def test_set_running_refreshes_and_clears_snapshot_on_main_thread(self):
        button = SimpleNamespace(configure=lambda **kwargs: None)
        snapshot = {"notify_desktop": True, "marker": "fresh"}
        stub = SimpleNamespace(
            start_btn=button,
            resume_btn=button,
            jsonl_btn=button,
            postprocess_btn=button,
            stop_btn=button,
            pause_btn=button,
            _is_running=True,
            _active_snapshot={"marker": "stale"},
            _take_run_snapshot=lambda: snapshot,
            _start_elapsed_timer=lambda: None,
            _stop_elapsed_timer=lambda: None,
            _job_rows={},
        )

        gui.App._set_running(stub, True)
        self.assertIs(stub._active_snapshot, snapshot)
        gui.App._set_running(stub, True)
        self.assertIs(stub._active_snapshot, snapshot)
        gui.App._set_running(stub, False)
        self.assertIsNone(stub._active_snapshot)

    def test_run_freezes_tk_variable_getters_to_snapshot_values(self):
        class Var:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        src_var = Var("English")
        stub = SimpleNamespace(
            _active_snapshot={"src_lang": "Spanish"},
            src_var=src_var,
        )
        gui.App._freeze_run_variable_reads(stub)
        src_var.value = "Italian"
        self.assertEqual(src_var.get(), "Spanish")
        gui.App._unfreeze_run_variable_reads(stub)
        self.assertEqual(src_var.get(), "Italian")

    def test_jsonl_worker_uses_values_captured_before_thread_launch(self):
        src = inspect.getsource(gui.App._import_jsonl)
        worker_at = src.index("def _do():")
        for assignment in (
            "src = self.src_var.get()",
            "tgt = self.tgt_var.get()",
            "clean_sdh_on = self.clean_sdh_var.get()",
            "polish_on = self.polish_var.get()",
            "profanity = self.profanity_var.get()",
        ):
            self.assertLess(src.index(assignment), worker_at)

    def test_no_direct_self_after_zero_calls_remain_in_gui(self):
        """10. Verify zero self.after(0) calls remain in subtitle_translator_gui.py."""
        src = inspect.getsource(gui)
        self.assertNotIn("self.after(0,", src, "Zero self.after(0) calls must remain in GUI module")


if __name__ == "__main__":
    unittest.main()
