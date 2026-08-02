import unittest
from types import SimpleNamespace

import subtitle_translator_gui as gui


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Progress:
    def __init__(self):
        self.values = []
        self.configured = []

    def set(self, value):
        self.values.append(value)

    def configure(self, **kwargs):
        self.configured.append(kwargs)


class _Widget:
    def __init__(self):
        self.configured = []

    def configure(self, **kwargs):
        self.configured.append(kwargs)


class UiMotionTest(unittest.TestCase):
    def test_color_mix_is_bounded_and_deterministic(self):
        self.assertEqual(gui._mix_hex_color("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(gui._mix_hex_color("#112233", "#ffffff", -1), "#112233")
        self.assertEqual(gui._mix_hex_color("#112233", "#ffffff", 2), "#ffffff")

    def test_progress_animation_schedules_only_one_shared_tick(self):
        scheduled = []
        progress = _Progress()
        app = SimpleNamespace(
            light_animations_var=_Var(True),
            progress=progress,
            _is_running=True,
            _is_shutting_down=False,
            _motion_after_id=None,
            _motion_progress_target=0.0,
            _motion_progress_value=0.0,
            after=lambda delay, callback: scheduled.append((delay, callback)) or "tick-1",
        )

        gui.App._set_progress(app, 40)
        gui.App._set_progress(app, 70)

        self.assertEqual(app._motion_progress_target, 0.7)
        self.assertEqual(progress.values, [])
        self.assertEqual(len(scheduled), 1)
        self.assertEqual(app._motion_after_id, "tick-1")

    def test_disabled_motion_updates_progress_immediately(self):
        progress = _Progress()
        app = SimpleNamespace(
            light_animations_var=_Var(False),
            progress=progress,
            _is_running=True,
            _is_shutting_down=False,
            _motion_progress_target=0.0,
            _motion_progress_value=0.0,
        )

        gui.App._set_progress(app, 55)

        self.assertEqual(progress.values, [0.55])
        self.assertEqual(app._motion_progress_value, 0.55)

    def test_window_move_sets_short_motion_pause(self):
        app = SimpleNamespace(_motion_pause_until=0.0)
        event = SimpleNamespace(widget=app)

        gui.App._on_window_motion(app, event)

        self.assertGreater(app._motion_pause_until, gui.time.monotonic())

    def test_motion_tick_shows_visible_activity_signal(self):
        scheduled = []
        dot = _Widget()
        activity = _Widget()
        card = _Widget()
        progress = _Progress()
        app = SimpleNamespace(
            light_animations_var=_Var(True),
            _is_running=True,
            _is_shutting_down=False,
            _motion_after_id=None,
            _motion_pause_until=0.0,
            _motion_step=0,
            _motion_phase_color=gui.INFO_BLUE,
            _motion_activity_text="ÇALIŞIYOR",
            _motion_progress_value=0.4,
            _motion_progress_target=0.4,
            _motion_active_filepath=None,
            _job_rows={},
            _phase_dot=dot,
            _phase_activity_lbl=activity,
            _phase_card=card,
            progress=progress,
            after=lambda delay, callback: scheduled.append((delay, callback)) or "tick-2",
        )

        gui.App._motion_tick(app)

        self.assertIn(dot.configured[-1]["text"], {"●", "◉", "◎"})
        self.assertTrue(activity.configured[-1]["text"].startswith("ÇALIŞIYOR"))
        self.assertEqual(card.configured[-1]["border_width"], 1)
        self.assertIn("progress_color", progress.configured[-1])
        self.assertEqual(scheduled[0][0], 110)


if __name__ == "__main__":
    unittest.main()
