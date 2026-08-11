import unittest

import subtitle_translator_gui as gui


class PhaseActivityIndicatorTest(unittest.TestCase):
    def test_recent_activity_keeps_animated_working_label(self):
        self.assertEqual(
            gui._phase_activity_indicator("ÇALIŞIYOR", 3, 4),
            "ÇALIŞIYOR ··",
        )

    def test_long_request_shows_visible_wait_duration(self):
        self.assertEqual(
            gui._phase_activity_indicator("API", 12, 0),
            "BEKLİYOR · 0:12",
        )
        self.assertEqual(
            gui._phase_activity_indicator("ÇALIŞIYOR", 72, 0),
            "BEKLİYOR · 1:12",
        )

    def test_invalid_age_is_safe(self):
        self.assertEqual(
            gui._phase_activity_indicator("", "bilinmiyor", 0),
            "ÇALIŞIYOR ·",
        )


if __name__ == "__main__":
    unittest.main()
