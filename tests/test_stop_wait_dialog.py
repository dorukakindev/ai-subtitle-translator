"""
Deterministic unit tests for modal dialog stop & timeout wait loops.
Directly invokes production App._wait_for_dialog_event with stub objects.
Does NOT instantiate App() or open actual GUI windows.
"""
import inspect
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class StopWaitDialogTest(unittest.TestCase):

    def setUp(self):
        self.after_calls = []

    def _make_stub(self, stop_flag=False):
        stub = SimpleNamespace(
            _stop_flag=stop_flag,
            _is_shutting_down=False,
            _ui_queue=queue.Queue(),
            _active_modal_dlg=None,
            after=lambda ms, fn: self.after_calls.append(fn),
            _dismiss_modal_dialog=lambda *a, **k: None,
            _helper_api_key=lambda r: "sk-fake",
            _helper_api_base_url=lambda r: "https://api.openai.com/v1",
            _helper_api_model=lambda r: "gpt-5.4-mini",
            _log=lambda *a, **k: None,
            _log_exc=lambda *a, **k: None,
            _show_glossary_dialog=lambda *a, **k: None,
            src_var=SimpleNamespace(get=lambda: "English"),
            tgt_var=SimpleNamespace(get=lambda: "Turkish"),
            glossary_var=SimpleNamespace(get=lambda: ""),
        )
        return stub

    def test_wait_for_dialog_event_returns_completed_when_event_set(self):
        """Verify _wait_for_dialog_event returns 'completed' instantly if event is set."""
        stub = self._make_stub()
        event = threading.Event()
        event.set()

        res = gui.App._wait_for_dialog_event(stub, event, timeout=10.0, poll_interval=0.1)
        self.assertEqual(res, "completed")
        self.assertEqual(len(self.after_calls), 0)

    def test_wait_for_dialog_event_returns_stopped_when_stop_flag_set(self):
        """Verify _wait_for_dialog_event returns 'stopped' within ~0.2s when _stop_flag becomes True."""
        stub = self._make_stub(stop_flag=False)
        event = threading.Event()
        result = {}

        def wait_worker():
            start = time.time()
            result["status"] = gui.App._wait_for_dialog_event(
                stub, event, timeout=300.0, poll_interval=0.1)
            result["elapsed"] = time.time() - start

        t = threading.Thread(target=wait_worker)
        t.start()
        time.sleep(0.1)
        stub._stop_flag = True
        t.join()
        self.assertEqual(result["status"], "stopped")
        self.assertLess(result["elapsed"], 2.0)
        self.assertEqual(stub._ui_queue.qsize(), 1)
        self.assertEqual(len(self.after_calls), 0)

    def test_wait_for_dialog_event_returns_timeout_on_small_timeout(self):
        """Verify _wait_for_dialog_event returns 'timeout' deterministically when timeout expires."""
        stub = self._make_stub()
        event = threading.Event()
        result = {}

        def wait_worker():
            start = time.time()
            result["status"] = gui.App._wait_for_dialog_event(
                stub, event, timeout=0.05, poll_interval=0.01)
            result["elapsed"] = time.time() - start

        thread = threading.Thread(target=wait_worker)
        thread.start()
        thread.join()

        self.assertEqual(result["status"], "timeout")
        self.assertLess(result["elapsed"], 0.5)
        self.assertEqual(stub._ui_queue.qsize(), 1)
        self.assertEqual(len(self.after_calls), 0)

    def test_no_direct_300s_event_wait_remains_in_modal_workflows(self):
        """Verify via source code inspection that no direct .wait(timeout=300) remains in any modal workflow."""
        methods_to_check = [
            ("_run_quality_check_inline", gui.App._run_quality_check_inline),
            ("_run_auto_glossary", gui.App._run_auto_glossary),
            ("_run_batch", gui.App._run_batch),
            ("_wait_batch_hybrid", gui.App._wait_batch_hybrid),
            ("_run_sync_hybrid", gui.App._run_sync_hybrid),
        ]

        for name, method in methods_to_check:
            src = inspect.getsource(method)
            lines = src.splitlines()
            for line in lines:
                if ".wait(timeout=300)" in line:
                    self.fail(f"Found unhandled direct 300s wait in {name}: '{line.strip()}'")

    def test_translation_flows_stop_before_recording_or_writing_after_helper_calls(self):
        flows = (
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        )
        checkpoints = [
            ("ht.critic_pass_with_helper(", "_record_pass_change(_pass_trace, \"Critic\""),
            ("self._polish_pass(", "_record_pass_change(_pass_trace, \"Polish\""),
            ("ht.native_reader_pass(", "_record_pass_change(_pass_trace, \"Native\""),
            ("self._maybe_condense(", "_record_pass_change(_pass_trace, \"Condense\""),
            ("self._run_final_semantic_checks(", "_normalize_mixed_terms("),
            ("_normalize_mixed_terms(", "_fill_hata_with_source("),
        ]
        for flow in flows:
            src = inspect.getsource(flow)
            for call, next_step in checkpoints:
                with self.subTest(flow=flow.__name__, call=call):
                    start = src.find(call)
                    end = src.find(next_step, start + len(call))
                    self.assertGreaterEqual(start, 0)
                    self.assertGreater(end, start)
                    self.assertIn("if self._stop_flag:", src[start:end])
                    self.assertIn("break", src[start:end])

    def test_auto_glossary_does_not_write_file_when_stopped(self):
        """Verify _run_auto_glossary does not append to glossary file if dialog wait returns 'stopped' or 'timeout'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            glossary_file = Path(tmpdir) / "test_glossary.txt"
            glossary_file.write_text("# Initial\n", encoding="utf-8")

            stub = self._make_stub(stop_flag=True)
            stub.glossary_var = SimpleNamespace(get=lambda: str(glossary_file))
            stub._wait_for_dialog_event = lambda e, timeout=300: "stopped"

            suggestions = [{"src": "AI", "tgt": "Yapay Zeka", "category": "technical"}]
            with patch("hybrid_translate.build_glossary_suggestions", return_value=suggestions), \
                 patch("hybrid_translate.load_glossary", return_value={}):
                gui.App._run_auto_glossary(stub, [], [], "sub.srt")

            content = glossary_file.read_text(encoding="utf-8")
            self.assertEqual(content, "# Initial\n", "Glossary file must not be modified when stopped")

    def test_dismiss_modal_dialog_target_guard(self):
        """Verify _dismiss_modal_dialog with target_dlg parameter ignores late calls from older dialogs."""
        mock_dlg1 = MagicMock()
        mock_dlg2 = MagicMock()
        old_event = threading.Event()
        current_event = threading.Event()

        stub = SimpleNamespace(
            _active_modal_dlg=mock_dlg2,
            _active_modal_event=current_event,
        )

        # An old worker must not close the current dialog even without its dialog reference.
        gui.App._dismiss_modal_dialog(stub, target_event=old_event)
        self.assertEqual(stub._active_modal_dlg, mock_dlg2)
        mock_dlg2.destroy.assert_not_called()
        
        # Calling dismiss with old dialog (mock_dlg1) when active is mock_dlg2 should be a no-op
        gui.App._dismiss_modal_dialog(stub, target_dlg=mock_dlg1)
        self.assertEqual(stub._active_modal_dlg, mock_dlg2)
        mock_dlg2.destroy.assert_not_called()

        # Calling dismiss with current active dialog (mock_dlg2) should destroy it
        gui.App._dismiss_modal_dialog(stub, target_dlg=mock_dlg2)
        self.assertIsNone(stub._active_modal_dlg)
        self.assertIsNone(stub._active_modal_event)
        mock_dlg2.destroy.assert_called_once()

    def test_cancelled_event_does_not_open_late_qc_dialog(self):
        """A GUI callback queued before timeout must not create a dialog afterwards."""
        stub = self._make_stub()
        event = threading.Event()
        event._dialog_cancelled = True
        stub._build_qc_dialog = MagicMock()

        gui.App._show_qc_dialog(stub, [{"id": "1"}], [], event)

        stub._build_qc_dialog.assert_not_called()

    @patch("subtitle_translator_gui.ctk.CTkToplevel")
    def test_cancelled_event_does_not_open_late_glossary_dialog(self, toplevel):
        """A timed-out glossary callback must not create an orphaned window."""
        stub = self._make_stub()
        event = threading.Event()
        event._dialog_cancelled = True

        gui.App._show_glossary_dialog(stub, [{"src": "AI", "tgt": "YZ"}], [], event, "")

        toplevel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
