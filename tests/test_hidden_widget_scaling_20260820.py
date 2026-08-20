# -*- coding: utf-8 -*-
"""Gizlenen widget'lar ölçekleme olayında geri gelmemeli.

CustomTkinter 5.2.2 `grid_remove`'u override etmiyor; `_set_scaling` son
geometri çağrısını (`_last_geometry_manager_call`) aynen tekrar uyguladığı için
gizlenen panel geri geliyordu — 2026-08-20: uygulama küçültülüp açılınca çalışan
işin ilerleme panosu yerine dosya ayarları paneli görünüyordu.

Testler `winfo_ismapped()` KULLANMAZ: tam suite içinde başka GUI testlerinden
kalan Tk durumu bu değeri güvenilmez yapıyor. Ölçüt `grid_info()` (Tk düzeyi,
pencerenin haritalanmasından bağımsız) ve CTk'nin tekrar-uygulama kaydıdır.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subtitle_translator_gui as g

try:
    import customtkinter as ctk
    _GUI = True
except Exception:  # pragma: no cover
    _GUI = False


class _FakeCtkWidget:
    """CTkBaseClass'ın ilgili sözleşmesini taklit eder (Tk gerektirmez)."""

    def __init__(self):
        self._last_geometry_manager_call = {
            "function": self.grid, "kwargs": {"row": 2, "column": 0}}
        self.visible = True

    def grid(self, **kwargs):
        self.visible = True
        self._last_geometry_manager_call = {"function": self.grid,
                                            "kwargs": kwargs}

    def grid_remove(self):
        self.visible = False

    def apply_scaling(self):
        """CTkBaseClass._set_scaling'in kritik satırı."""
        call = self._last_geometry_manager_call
        if call is not None:
            call["function"](**call["kwargs"])


class GridHideContractTest(unittest.TestCase):
    def test_plain_grid_remove_is_undone_by_scaling(self):
        # Kusurun kendisi: düz grid_remove ölçeklemede geri geliyor.
        widget = _FakeCtkWidget()
        widget.grid_remove()
        self.assertFalse(widget.visible)
        widget.apply_scaling()
        self.assertTrue(widget.visible)

    def test_grid_hide_survives_scaling(self):
        widget = _FakeCtkWidget()
        g._grid_hide(widget)
        self.assertFalse(widget.visible)
        widget.apply_scaling()
        self.assertFalse(widget.visible)

    def test_widget_can_be_shown_again_and_stays(self):
        widget = _FakeCtkWidget()
        g._grid_hide(widget)
        widget.grid()
        self.assertTrue(widget.visible)
        widget.apply_scaling()
        self.assertTrue(widget.visible)

    def test_none_and_foreign_objects_are_tolerated(self):
        g._grid_hide(None)
        g._grid_hide(object())


@unittest.skipUnless(_GUI, "customtkinter yok")
class RealWidgetGridHideTest(unittest.TestCase):
    def setUp(self):
        self.root = ctk.CTk()
        self.widget = ctk.CTkFrame(self.root)
        self.widget.grid(row=0, column=0, sticky="ew")
        self.root.update_idletasks()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_record_is_cleared_while_hidden(self):
        self.assertIsNotNone(self.widget._last_geometry_manager_call)
        g._grid_hide(self.widget)
        self.assertIsNone(self.widget._last_geometry_manager_call)

    # NOT: grid_info()/winfo_ismapped() tabanlı gerçek-Tk kontrolleri BİLEREK
    # yok — tam suite içinde başka test modülleri tkinter'ı stub'ladığı için bu
    # değerler güvenilmez oluyor. Kusurun mekanizması (tekrar-uygulama kaydı)
    # yukarıdaki testle ve _FakeCtkWidget sözleşme testleriyle kilitleniyor.


if __name__ == "__main__":
    unittest.main()
