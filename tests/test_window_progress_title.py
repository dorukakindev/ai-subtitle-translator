import unittest

import subtitle_translator_gui as gui


class ProgressWindowTitleTest(unittest.TestCase):
    def test_ready_state_keeps_plain_application_title(self):
        self.assertEqual(
            gui._progress_window_title("Hazır", "Dosya ekleyin", 0.0, False),
            gui.APP_WINDOW_TITLE,
        )

    def test_running_title_exposes_phase_percent_and_current_file(self):
        self.assertEqual(
            gui._progress_window_title(
                "Native Okuyucu",
                "Malmkrog English.srt  —  Paket 2/6 · yanıt bekleniyor",
                0.64,
                True,
            ),
            "Native Okuyucu · %64 · Malmkrog English.srt — Subtitle Translator",
        )

    def test_terminal_state_stays_visible_without_stale_progress(self):
        self.assertEqual(
            gui._progress_window_title("Tamamlandı", "14 dosya", 1.0, False),
            "Tamamlandı — Subtitle Translator",
        )

    def test_long_detail_is_compacted_for_taskbar(self):
        title = gui._progress_window_title(
            "Critic Pass", "x" * 80, 0.125, True)
        self.assertIn("Critic Pass · %12 · ", title)
        self.assertIn("… — Subtitle Translator", title)
        self.assertLessEqual(len(title), 90)


if __name__ == "__main__":
    unittest.main()
