"""Minimal tkinter stub for headless unittest discovery."""

from types import SimpleNamespace


class _DummyWidget:
    def __init__(self, *args, **kwargs):
        self._value = ""
        self._last_child_ids = {}

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def pack(self, *args, **kwargs):
        return None

    def grid(self, *args, **kwargs):
        return None

    def place(self, *args, **kwargs):
        return None

    def configure(self, *args, **kwargs):
        return None

    config = configure

    def delete(self, *args, **kwargs):
        self._value = ""

    def get(self, *args, **kwargs):
        return self._value

    def insert(self, *args, **kwargs):
        if args:
            self._value = str(args[-1])

    def create_rectangle(self, *args, **kwargs):
        return 1

    def create_text(self, *args, **kwargs):
        return 1

    def itemconfig(self, *args, **kwargs):
        return None


class _DummyVar:
    def __init__(self, value=None, *args, **kwargs):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value

    def trace_add(self, *args, **kwargs):
        return None


Tk = _DummyWidget
Toplevel = _DummyWidget
Frame = _DummyWidget
Label = _DummyWidget
Button = _DummyWidget
Entry = _DummyWidget
Text = _DummyWidget
Canvas = _DummyWidget
Scrollbar = _DummyWidget
Listbox = _DummyWidget
StringVar = _DummyVar
BooleanVar = _DummyVar
IntVar = _DummyVar
DoubleVar = _DummyVar
END = "end"
BOTH = "both"
LEFT = "left"
RIGHT = "right"
TOP = "top"
BOTTOM = "bottom"
X = "x"
Y = "y"

filedialog = SimpleNamespace(
    askopenfilename=lambda *args, **kwargs: "",
    askopenfilenames=lambda *args, **kwargs: (),
    askdirectory=lambda *args, **kwargs: "",
    asksaveasfilename=lambda *args, **kwargs: "",
)
messagebox = SimpleNamespace(
    showinfo=lambda *args, **kwargs: None,
    showwarning=lambda *args, **kwargs: None,
    showerror=lambda *args, **kwargs: None,
    askyesno=lambda *args, **kwargs: False,
)


def __getattr__(name):
    return _DummyWidget
