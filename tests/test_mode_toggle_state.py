import unittest

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Widget:
    def __init__(self):
        self.state = None
        self.visible = False

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def configure(self, **kwargs):
        self.state = kwargs.get("state", self.state)


class _Stub:
    _toggle_hybrid = gui.App._toggle_hybrid

    def __init__(self):
        self.mode_var = _Var("sync")
        self.hybrid_var = _Var(False)
        self.precontext_var = _Var(True)
        self.hybrid_frame = _Widget()
        self.precontext_switch = _Widget()
        self.synced = 0

    def _sync_helper_role_controls(self):
        self.synced += 1


class ModeToggleStateTest(unittest.TestCase):
    def test_sync_forced_hybrid_uses_full_toggle_transition(self):
        stub = _Stub()
        gui.App._on_mode_change(stub)
        self.assertTrue(stub.hybrid_var.get())
        self.assertTrue(stub.hybrid_frame.visible)
        self.assertFalse(stub.precontext_var.get())
        self.assertEqual(stub.precontext_switch.state, "disabled")
        self.assertEqual(stub.synced, 1)


if __name__ == "__main__":
    unittest.main()
