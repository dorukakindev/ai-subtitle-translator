import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


class LogContextMenuTest(unittest.TestCase):
    def test_keyboard_shortcuts_delegate_to_existing_safe_actions(self):
        app = SimpleNamespace(
            _copy_complete_log_to_clipboard=MagicMock(),
            _pin_log_bottom=MagicMock(),
        )

        self.assertEqual(
            gui.App._shortcut_copy_complete_log(app), "break")
        self.assertEqual(gui.App._shortcut_pin_log_bottom(app), "break")
        app._copy_complete_log_to_clipboard.assert_called_once_with()
        app._pin_log_bottom.assert_called_once_with()

    def test_selected_log_text_is_copied_without_touching_layout(self):
        app = SimpleNamespace(
            log_box=MagicMock(),
            clipboard_clear=MagicMock(),
            clipboard_append=MagicMock(),
            update_idletasks=MagicMock(),
            _log=MagicMock(),
        )
        app.log_box.get.return_value = "yalnız bu satır"

        copied = gui.App._copy_selected_log_text(app)

        self.assertTrue(copied)
        app.clipboard_append.assert_called_once_with("yalnız bu satır")
        app._log.assert_not_called()

    def test_context_menu_disables_copy_and_clear_when_log_is_empty(self):
        menu = MagicMock()
        log_box = MagicMock()
        log_box.tag_ranges.return_value = ()
        log_box.get.return_value = ""
        app = SimpleNamespace(_log_context_menu=menu, log_box=log_box)

        result = gui.App._show_log_context_menu(
            app, SimpleNamespace(x_root=120, y_root=240))

        self.assertEqual(result, "break")
        menu.entryconfigure.assert_any_call(0, state="disabled")
        menu.entryconfigure.assert_any_call(1, state="disabled")
        menu.entryconfigure.assert_any_call(4, state="disabled")
        menu.tk_popup.assert_called_once_with(120, 240)
        menu.grab_release.assert_called_once()

    def test_context_menu_enables_selected_and_full_copy(self):
        menu = MagicMock()
        log_box = MagicMock()
        log_box.tag_ranges.return_value = ("1.0", "1.4")
        log_box.get.return_value = "log"
        app = SimpleNamespace(_log_context_menu=menu, log_box=log_box)

        gui.App._show_log_context_menu(
            app, SimpleNamespace(x_root=1, y_root=2))

        menu.entryconfigure.assert_any_call(0, state="normal")
        menu.entryconfigure.assert_any_call(1, state="normal")
        menu.entryconfigure.assert_any_call(4, state="normal")


if __name__ == "__main__":
    unittest.main()
