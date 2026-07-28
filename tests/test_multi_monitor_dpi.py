import unittest

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


class MultiMonitorDpiTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
