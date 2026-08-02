import unittest
import inspect

import subtitle_translator_gui as gui


class _FakeWindow:
    def __init__(self):
        self._block_update_dimensions_event = False
        self.idle_calls = []
        self.dpi_callbacks = 0

    def after_idle(self, callback):
        self.idle_calls.append(callback)

    def _after_dpi_scaling(self):
        self.dpi_callbacks += 1


class _FakeToplevel(_FakeWindow):
    pass


class _FakeCanvas:
    def __init__(self):
        self.scrollregion = None
        self.position = 0.4

    def yview(self):
        return self.position, 0.8

    def bbox(self, _tag):
        return 0, 0, 400, 1200

    def configure(self, **kwargs):
        self.scrollregion = kwargs.get("scrollregion")

    def yview_moveto(self, position):
        self.position = position


class _GridProbe:
    def __init__(self):
        self.columns = []

    def grid_columnconfigure(self, column, **kwargs):
        self.columns.append((column, kwargs))


class _CardProbe:
    def __init__(self):
        self.layouts = []

    def grid_configure(self, **kwargs):
        self.layouts.append(kwargs)


class _MainProbe:
    def __init__(self, width):
        self.width = width

    def winfo_width(self):
        return self.width


class MultiMonitorDpiTest(unittest.TestCase):
    def test_main_panel_is_vertically_scrollable(self):
        source = inspect.getsource(gui.App._build_main)
        self.assertIn("main = ctk.CTkScrollableFrame(", source)
        self.assertIn("scrollbar_button_color=BORDER", source)

    def test_runtime_uses_fixed_scaling(self):
        try:
            from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
        except Exception:
            self.skipTest("Gerçek CustomTkinter paketi devrede değil")
        self.assertTrue(ScalingTracker.deactivate_automatic_dpi_awareness)

    def test_dpi_guard_blocks_dimension_events_during_scaling(self):
        root_cls = type("Root", (_FakeWindow,), {})
        top_cls = type("Top", (_FakeToplevel,), {})

        self.assertTrue(gui._install_customtkinter_dpi_guard(root_cls, top_cls))
        window = root_cls()
        window.block_update_dimensions_event()
        self.assertTrue(window._block_update_dimensions_event)

        window.unblock_update_dimensions_event()
        self.assertFalse(window._block_update_dimensions_event)
        self.assertEqual(len(window.idle_calls), 1)
        window.idle_calls[0]()
        self.assertEqual(window.dpi_callbacks, 1)

    def test_scroll_region_and_position_are_restored_after_dpi_change(self):
        canvas = _FakeCanvas()
        frame = type("Frame", (), {"_parent_canvas": canvas})()

        self.assertTrue(gui._refresh_scrollable_frame_after_dpi(frame))
        self.assertEqual(canvas.scrollregion, (0, 0, 400, 1200))
        self.assertEqual(canvas.position, 0.4)

    def test_missing_canvas_is_safe(self):
        self.assertFalse(gui._refresh_scrollable_frame_after_dpi(object()))

    def test_stat_cards_use_two_rows_when_main_panel_is_narrow(self):
        self.assertEqual(gui._dashboard_stat_columns(899), 3)
        self.assertEqual(gui._dashboard_stat_columns(900), 6)

    def test_dashboard_reflow_preserves_a_compact_three_column_grid(self):
        cards = [_CardProbe() for _ in range(6)]
        app = type("AppProbe", (), {
            "_dashboard_layout_after_id": "stale",
            "_main_frame": _MainProbe(680),
            "_stats_frame": _GridProbe(),
            "_stat_cards": cards,
            "_dashboard_stat_layout_cols": None,
        })()

        gui.App._refresh_dashboard_layout(app)

        self.assertEqual(app._dashboard_layout_after_id, None)
        self.assertEqual(app._dashboard_stat_layout_cols, 3)
        self.assertEqual(
            [(card.layouts[-1]["row"], card.layouts[-1]["column"])
             for card in cards],
            [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)],
        )


if __name__ == "__main__":
    unittest.main()
