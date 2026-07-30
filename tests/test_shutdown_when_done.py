import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class ShutdownWhenDoneTest(unittest.TestCase):
    def test_only_full_success_is_scheduled(self):
        stub = SimpleNamespace(
            _active_snapshot={"shutdown_when_done": True},
            _auto_shutdown_scheduled_run_id="",
            shutdown_when_done_var=MagicMock(),
            _log=MagicMock(),
            after=MagicMock(),
        )
        for status in ("durduruldu", "kısmen tamamlandı", "başarısız", "eksik"):
            self.assertFalse(gui.App._schedule_shutdown_after_success(
                stub, {"run_id": "run-1", "status": status}))
        stub.after.assert_not_called()

    def test_success_is_scheduled_once_and_switch_resets(self):
        stub = SimpleNamespace(
            _active_snapshot={"shutdown_when_done": True},
            _auto_shutdown_scheduled_run_id="",
            shutdown_when_done_var=MagicMock(),
            _log=MagicMock(),
            after=MagicMock(),
        )
        record = {"run_id": "run-1", "status": "tamamlandı"}
        self.assertTrue(gui.App._schedule_shutdown_after_success(stub, record))
        self.assertFalse(gui.App._schedule_shutdown_after_success(stub, record))
        stub.shutdown_when_done_var.set.assert_called_once_with(False)
        stub.after.assert_called_once()

    def test_log_is_saved_and_copied_before_shutdown(self):
        with tempfile.TemporaryDirectory() as td:
            desktop = Path(td)
            stub = SimpleNamespace(
                _complete_session_log_text=lambda: "FULL SESSION LOG\n",
                _log=MagicMock(),
                clipboard_clear=MagicMock(),
                clipboard_append=MagicMock(),
                update_idletasks=MagicMock(),
            )
            with patch.object(gui, "_desktop_directory", return_value=desktop), \
                    patch.object(gui.subprocess, "Popen") as popen:
                result = gui.App._export_log_and_shutdown(
                    stub, {"run_id": "20260730-test"})

            saved = desktop / "ceviri_logu_20260730-test.txt"
            self.assertTrue(result)
            self.assertEqual(saved.read_text(encoding="utf-8"), "FULL SESSION LOG\n")
            stub.clipboard_append.assert_called_once_with("FULL SESSION LOG\n")
            args = popen.call_args.args[0]
            self.assertIn("/s", args)
            self.assertEqual(args[args.index("/t") + 1], "30")

    def test_failed_desktop_save_prevents_shutdown(self):
        stub = SimpleNamespace(
            _complete_session_log_text=lambda: "FULL SESSION LOG\n",
            _log=MagicMock(),
            clipboard_clear=MagicMock(),
            clipboard_append=MagicMock(),
            update_idletasks=MagicMock(),
        )
        with patch.object(gui, "atomic_write_text", side_effect=OSError("disk full")), \
                patch.object(gui.subprocess, "Popen") as popen:
            result = gui.App._export_log_and_shutdown(
                stub, {"run_id": "20260730-test"})
        self.assertFalse(result)
        popen.assert_not_called()

    def test_countdown_dialog_failure_does_not_misreport_shutdown_command(self):
        with tempfile.TemporaryDirectory() as td:
            stub = SimpleNamespace(
                _complete_session_log_text=lambda: "FULL SESSION LOG\n",
                _log=MagicMock(),
                clipboard_clear=MagicMock(),
                clipboard_append=MagicMock(),
                update_idletasks=MagicMock(),
                _show_shutdown_countdown=MagicMock(
                    side_effect=RuntimeError("Tk unavailable")),
            )
            with patch.object(gui, "_desktop_directory", return_value=Path(td)), \
                    patch.object(gui.subprocess, "Popen") as popen:
                result = gui.App._export_log_and_shutdown(
                    stub, {"run_id": "20260730-test"})
        self.assertTrue(result)
        popen.assert_called_once()
        self.assertTrue(any(
            "geri sayım penceresi" in str(call.args[0])
            for call in stub._log.call_args_list
        ))

    def test_failed_shutdown_abort_keeps_countdown_open(self):
        dialog = MagicMock()
        stub = SimpleNamespace(
            _shutdown_countdown_after_id="after-1",
            _shutdown_countdown_dialog=dialog,
            after_cancel=MagicMock(),
            _log=MagicMock(),
        )
        completed = SimpleNamespace(returncode=1)
        with patch.object(gui.subprocess, "run", return_value=completed):
            result = gui.App._cancel_scheduled_shutdown(stub)
        self.assertFalse(result)
        stub.after_cancel.assert_not_called()
        dialog.destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
