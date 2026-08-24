# -*- coding: utf-8 -*-
"""Modal ön analiz penceresi her zaman görünür bir monitörde ve önde açılır."""
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

# Kullanıcının gerçek düzeni: birincil DPI ölçekli (Tk 1707 görüyor),
# ikincil X=2560'ta başlıyor. Arada 853 piksellik ÖLÜ BÖLGE var.
MONITORS = [(0, 0, 1707, 920), (2560, 116, 1920, 1040)]


class ADialogNeverLandsInTheDeadZoneTest(unittest.TestCase):
    """Uygulama `deactivate_automatic_dpi_awareness()` çağırıyor; Tk birincil
    ekranı 1707 görürken ikincil monitör 2560'ta başlıyor. Hesaplanan konum
    hiçbir monitöre denk gelmeyebiliyordu ve pencere `grab_set` +
    `wait_window` ile modal olduğu için uygulama tamamen donmuş görünüyordu.
    2026-08-24 ölçümü: 36 saniye, CPU %0, disk %0.
    """

    def test_a_position_in_the_gap_is_pulled_onto_a_monitor(self):
        self.assertEqual(
            g.clamp_dialog_to_monitor(2000, 400, 700, 500, MONITORS),
            (2560, 400))

    def test_a_visible_position_is_left_alone(self):
        for x, y in ((3170, 406), (500, 200)):
            with self.subTest(x=x):
                self.assertEqual(
                    g.clamp_dialog_to_monitor(x, y, 700, 500, MONITORS), (x, y))

    def test_a_position_left_of_every_screen_is_pulled_back(self):
        self.assertEqual(
            g.clamp_dialog_to_monitor(-900, 100, 700, 500, MONITORS),
            (0, 100))

    def test_a_dialog_taller_than_the_monitor_still_starts_on_it(self):
        x, y = g.clamp_dialog_to_monitor(2000, 400, 700, 2000, MONITORS)
        self.assertEqual(x, 2560)
        self.assertGreaterEqual(y, 116)

    def test_without_monitor_data_the_position_is_untouched(self):
        # Kör düzeltme, çalışan bir yerleşimi bozmaktan kötüdür.
        self.assertEqual(
            g.clamp_dialog_to_monitor(2000, 400, 700, 500, []), (2000, 400))

    def test_the_window_layer_applies_the_clamp(self):
        # `centered_dialog_geometry` SAF kalır (testler onu doğrudan çağırıyor
        # ve negatif monitör desteği oraya kilitli); kırpma gerçek pencerenin
        # kurulduğu yerde yapılır.
        self.assertNotIn("clamp_dialog_to_monitor",
                         inspect.getsource(g.centered_dialog_geometry))
        self.assertIn("clamp_dialog_to_monitor",
                      inspect.getsource(g.App._present_preflight_dialog))

    def test_the_real_monitors_can_be_enumerated(self):
        areas = g.enumerate_monitor_work_areas()
        self.assertIsInstance(areas, list)
        for area in areas:
            self.assertEqual(len(area), 4)
            self.assertGreater(area[2], 0)
            self.assertGreater(area[3], 0)


class TheModalDialogStaysInFrontTest(unittest.TestCase):
    """`-topmost` 250 ms sonra bırakılıyor ama `grab_set` açık kalıyor: ana
    pencereye tıklamak onu öne alıyor, diyalog arkaya düşüyor ve tıklamalar
    kilit yüzünden yutuluyor."""

    def test_the_parent_focus_lifts_the_dialog_again(self):
        source = inspect.getsource(g.App._present_preflight_dialog)
        self.assertIn('bind("<FocusIn>"', source)
        self.assertIn("lift()", source)
        self.assertIn("focus_force()", source)

    def test_the_binding_is_released_with_the_dialog(self):
        source = inspect.getsource(g.App._present_preflight_dialog)
        self.assertIn('bind("<Destroy>"', source)
        self.assertIn("unbind", source)


if __name__ == "__main__":
    unittest.main()
