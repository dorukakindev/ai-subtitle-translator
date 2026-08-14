import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class ClipboardSafetyTest(unittest.TestCase):
    def test_clipboard_failure_is_reported_without_logging_memory_content(self):
        logs = []
        stub = SimpleNamespace(
            _pm=SimpleNamespace(build_context_hint=lambda: "SECRET MEMORY CONTENT"),
            clipboard_clear=MagicMock(side_effect=RuntimeError("clipboard locked")),
            clipboard_append=MagicMock(),
            _log=lambda message, level="": logs.append((message, level)),
        )
        with patch.object(gui.messagebox, "showwarning") as warning:
            result = gui.App._copy_project_memory_to_clipboard(stub)
        self.assertFalse(result)
        warning.assert_called_once()
        self.assertNotIn("SECRET MEMORY CONTENT", " ".join(x[0] for x in logs))


class AdvancedSettingsCancelTest(unittest.TestCase):
    def test_running_app_rejects_advanced_settings(self):
        logs = []
        stub = SimpleNamespace(_is_running=True, _log=lambda *args: logs.append(args))
        with patch.object(gui.ctk, "CTkToplevel") as dialog:
            gui.App._show_advanced_settings(stub)
        dialog.assert_not_called()
        self.assertTrue(logs)

    def test_restore_helper_reverts_only_snapshotted_values(self):
        stub = SimpleNamespace(_chunk_size=99, _temperature=0.9)
        gui.App._restore_advanced_settings(
            stub, {"_chunk_size": 40, "_temperature": 0.2, "_missing": None})
        self.assertEqual(stub._chunk_size, 40)
        self.assertEqual(stub._temperature, 0.2)
        self.assertFalse(hasattr(stub, "_missing"))

    def test_window_close_uses_same_cancel_handler(self):
        src = inspect.getsource(gui.App._show_advanced_settings)
        self.assertIn('dlg.protocol("WM_DELETE_WINDOW", _cancel)', src)
        self.assertIn("command=_cancel", src)
        self.assertIn("command=_save", src)

    def test_recommended_settings_explain_context_budget(self):
        headline, detail = gui._advanced_settings_summary(
            gui.ADVANCED_SETTINGS_RECOMMENDED)
        self.assertIn("25 cue / istek", headline)
        self.assertIn("30 önceki + 15 sonraki", headline)
        self.assertIn("4 paralel işçi", headline)
        self.assertIn("Güçlü bağlam", detail)
        self.assertIn("3.0 sn sahne eşiği", detail)
        self.assertIn("1 hedefli yanıt denemesi", detail)

    def test_summary_marks_small_context_as_limited(self):
        _, detail = gui._advanced_settings_summary({
            "_context_lines": 10,
            "_lookahead_lines": 5,
        })
        self.assertIn("Sınırlı bağlam", detail)

    def test_saved_advanced_settings_are_clamped_to_ui_limits(self):
        normalized = gui._normalize_advanced_settings({
            "_chunk_size": 999,
            "_context_lines": -20,
            "_lookahead_lines": 500,
            "_max_workers": -1,
            "_temperature": 7.5,
            "_max_retry": 0,
            "_scene_gap_seconds": 99,
        })
        self.assertEqual(normalized, {
            "_chunk_size": 100,
            "_context_lines": 1,
            "_lookahead_lines": 20,
            "_max_workers": 1,
            "_temperature": 1.0,
            "_max_retry": 1,
            "_scene_gap_seconds": 5.0,
        })

    def test_invalid_types_fall_back_to_recommended_values(self):
        normalized = gui._normalize_advanced_settings({
            "_chunk_size": "500",
            "_max_workers": True,
            "_temperature": float("nan"),
            "_scene_gap_seconds": float("inf"),
        })
        self.assertEqual(normalized["_chunk_size"], 25)
        self.assertEqual(normalized["_max_workers"], 4)
        self.assertEqual(normalized["_temperature"], 0.2)
        self.assertEqual(normalized["_scene_gap_seconds"], 3.0)

    def test_dialog_keeps_guidance_and_recommended_reset_visible(self):
        src = inspect.getsource(gui.App._show_advanced_settings)
        self.assertIn("Bağlam ve parçalama", src)
        self.assertIn("API ve performans", src)
        self.assertIn("Önerilen ayarlara dön", src)
        self.assertIn("centered_dialog_geometry", src)
        self.assertIn("_update_summary", src)
        self.assertIn("_reset_recommended", src)


class EstimateFailureTest(unittest.TestCase):
    def test_estimate_exception_replaces_calculating_message(self):
        info = _Var()
        stub = SimpleNamespace(
            _chunk_size=40,
            file_info_var=info,
            stat_files_var=_Var(),
            _set_stat=lambda _var, _value: None,
            _is_shutting_down=False,
        )
        with patch.object(gui, "estimate_tokens", side_effect=OSError("unreadable")), \
                patch.object(gui.App, "_start_worker",
                             side_effect=lambda _self, target, args=(), daemon=True: target()):
            gui.App._estimate_async(
                stub, ["one.srt", "two.srt"],
                lambda blocks, est: f"{blocks}:{est}")
        self.assertIn("2 dosya", info.value)
        self.assertIn("tahmini yapılamadı", info.value)
        self.assertNotIn("hesaplanıyor", info.value)


if __name__ == "__main__":
    unittest.main()
