"""Minimal CustomTkinter stub for dependency-light unit tests.

The real desktop app still requires customtkinter at runtime. This module is
only picked up when running `python -m unittest discover -s tests`, where the
tests directory is on sys.path.
"""


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        self._value = ""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def delete(self, *args, **kwargs):
        self._value = ""

    def get(self):
        return self._value

    def insert(self, index, value):
        self._value = str(value)


class _DummyVar:
    def __init__(self, value=None, *args, **kwargs):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        return None


CTk = _DummyWidget
CTkFrame = _DummyWidget
CTkLabel = _DummyWidget
CTkButton = _DummyWidget
CTkEntry = _DummyWidget
CTkTextbox = _DummyWidget
CTkOptionMenu = _DummyWidget
CTkCheckBox = _DummyWidget
CTkComboBox = _DummyWidget
CTkProgressBar = _DummyWidget
CTkScrollableFrame = _DummyWidget
CTkTabview = _DummyWidget
CTkToplevel = _DummyWidget
CTkFont = _DummyWidget
StringVar = _DummyVar
BooleanVar = _DummyVar
IntVar = _DummyVar
DoubleVar = _DummyVar


def set_appearance_mode(*args, **kwargs):
    return None


def set_default_color_theme(*args, **kwargs):
    return None


def __getattr__(name):
    if name.startswith("CTk"):
        return _DummyWidget
    return lambda *args, **kwargs: None
