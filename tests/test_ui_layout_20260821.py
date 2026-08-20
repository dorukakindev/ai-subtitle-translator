# -*- coding: utf-8 -*-
"""Arayüz yerleşimi düzeltmeleri (2026-08-21).

- Açılış pencere boyutu ve kayıtlı konumun bu ekrana sığdırılması
- Kaydırılabilir ana panelin tuval boyunu doldurması (log pencereyle büyür)
- Klavye kısayolu tablosu
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g


class DefaultWindowGeometryTest(unittest.TestCase):
    """Kayıtlı konum yokken pencere ekrana göre boyutlanır."""

    @staticmethod
    def _parse(geometry):
        match = g._GEOMETRY_RE.fullmatch(geometry)
        assert match, geometry
        return (int(match.group(1)), int(match.group(2)),
                int(match.group(4)), int(match.group(6)))

    def test_wide_screen_gets_a_capped_window(self):
        width, height, x, y = self._parse(g._default_window_geometry(3840, 2160))
        self.assertEqual(width, 1560)
        self.assertEqual(height, 980)
        self.assertGreater(x, 0)
        self.assertGreater(y, 0)

    def test_small_screen_never_drops_below_the_minimum(self):
        width, height, _x, _y = self._parse(g._default_window_geometry(1024, 640))
        self.assertGreaterEqual(width, g.WINDOW_MIN_WIDTH)
        self.assertGreaterEqual(height, g.WINDOW_MIN_HEIGHT)

    def test_window_is_horizontally_centred(self):
        width, _height, x, _y = self._parse(g._default_window_geometry(1920, 1080))
        self.assertEqual(x, (1920 - width) // 2)

    def test_broken_screen_size_still_returns_a_geometry(self):
        self.assertIn("x", g._default_window_geometry(None, None))


class ClampGeometryToScreenTest(unittest.TestCase):
    """Başka makinede kaydedilmiş konum pencereyi kaybettirmemeli."""

    def test_reasonable_geometry_is_untouched(self):
        self.assertEqual(
            g._clamp_geometry_to_screen("1200x800+100+50", 1920, 1080),
            "1200x800+100+50")

    def test_oversized_window_is_shrunk_to_the_desktop(self):
        self.assertEqual(
            g._clamp_geometry_to_screen("4000x3000+0+0", 1920, 1080),
            "1920x1080+0+0")

    def test_fully_offscreen_window_falls_back_to_the_default(self):
        self.assertEqual(
            g._clamp_geometry_to_screen("1200x800+5000+50", 1920, 1080),
            g._default_window_geometry(1920, 1080))

    def test_left_hand_second_monitor_is_preserved(self):
        # Tk mutlak negatif x'i '+-1500' diye yazar.
        self.assertEqual(
            g._clamp_geometry_to_screen(
                "1200x800+-1500+40", 1920, 1080, 3840, 1080, -1920, 0),
            "1200x800+-1500+40")

    def test_the_same_position_is_reset_when_that_monitor_is_gone(self):
        self.assertEqual(
            g._clamp_geometry_to_screen("1200x800+-1500+40", 1920, 1080),
            g._default_window_geometry(1920, 1080))

    def test_right_anchored_position_keeps_its_offsets(self):
        # '-100' SAĞ kenardan uzaklıktır; Tk zaten ekrana göre çözer.
        self.assertEqual(
            g._clamp_geometry_to_screen("1200x800-100+40", 1920, 1080),
            "1200x800-100+40")

    def test_negative_y_is_pulled_down_so_the_title_bar_stays_grabbable(self):
        self.assertEqual(
            g._clamp_geometry_to_screen("1200x800+100+-200", 1920, 1080),
            "1200x800+100+0")

    def test_unparsable_geometry_is_rejected(self):
        for value in ("", "salak", None, "1200x800"):
            with self.subTest(value=value):
                self.assertEqual(
                    g._clamp_geometry_to_screen(value, 1920, 1080), "")


class ScrollableStretchTest(unittest.TestCase):
    """İçerik tuvalden kısaysa uzatılır, uzunsa doğal boyunda kalır."""

    class _FakeCanvas:
        def __init__(self, height):
            self._height = height
            self.applied = None
            self.bindings = []

        def winfo_height(self):
            return self._height

        def bind(self, sequence, func, add=None):
            self.bindings.append((sequence, func, add))

        def itemconfigure(self, _item, height=None):
            self.applied = height

    class _FakeFrame:
        def __init__(self, canvas, natural):
            self._parent_canvas = canvas
            self._create_window_id = 1
            self._natural = natural
            self.bindings = []

        def winfo_reqheight(self):
            return self._natural

        def bind(self, sequence, func, add=None):
            self.bindings.append((sequence, func, add))

        def after_idle(self, func):
            func()

    def _run(self, canvas_height, natural):
        canvas = self._FakeCanvas(canvas_height)
        frame = self._FakeFrame(canvas, natural)
        g._stretch_scrollable_to_canvas(frame)
        return canvas, frame

    def test_short_content_is_stretched_to_the_canvas(self):
        canvas, _frame = self._run(900, 500)
        self.assertEqual(canvas.applied, 900)

    def test_tall_content_keeps_its_natural_height(self):
        canvas, _frame = self._run(600, 1400)
        self.assertEqual(canvas.applied, 1400)

    def test_repeating_the_same_target_does_not_reconfigure(self):
        canvas, frame = self._run(900, 500)
        canvas.applied = None
        frame._restretch_to_canvas()
        self.assertIsNone(canvas.applied)

    def test_a_widget_without_the_internals_is_ignored(self):
        g._stretch_scrollable_to_canvas(object())  # yükselmemeli

    def test_a_widget_whose_internals_are_the_wrong_type_is_ignored(self):
        broken = self._FakeFrame(lambda: None, 500)
        g._stretch_scrollable_to_canvas(broken)  # yükselmemeli


class KeyboardShortcutTableTest(unittest.TestCase):
    """Kısayol listesi tek kaynaktır ve gerçekten bağlı olanları anlatır."""

    def test_every_entry_has_keys_and_a_description(self):
        self.assertTrue(g.KEYBOARD_SHORTCUTS)
        for keys, description in g.KEYBOARD_SHORTCUTS:
            with self.subTest(keys=keys):
                self.assertTrue(keys.strip())
                self.assertTrue(description.strip())

    def test_the_documented_bindings_exist_on_the_app(self):
        for method in ("_shortcut_show_shortcuts", "_shortcut_copy_complete_log",
                       "_shortcut_copy_diagnostic", "_shortcut_show_last_summary",
                       "_shortcut_pin_log_bottom", "_show_shortcuts_dialog"):
            with self.subTest(method=method):
                self.assertTrue(callable(getattr(g.App, method, None)))

    def test_f1_is_listed(self):
        self.assertIn("F1", [keys for keys, _text in g.KEYBOARD_SHORTCUTS])


if __name__ == "__main__":
    unittest.main()
