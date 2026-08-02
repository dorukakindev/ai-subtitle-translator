import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import subtitle_translator_gui as gui


class ResumeSeriesMemoryTest(unittest.TestCase):
    def test_complete_cached_analysis_is_persisted(self):
        context = SimpleNamespace(_analysis_degraded=False)
        pronouns = {"A-B": "sen"}
        analysis = (context, {}, pronouns, {}, [], {}, [])
        app = SimpleNamespace(
            _update_series_memory_from_analysis=MagicMock())
        status = {}

        gui.App._update_resumed_series_memory(
            app, "episode.srt", analysis, "Turkish", status)

        app._update_series_memory_from_analysis.assert_called_once_with(
            "episode.srt", context, pronouns, "Turkish",
            status_out=status)

    def test_incomplete_cached_analysis_is_not_persisted(self):
        context = SimpleNamespace(_analysis_degraded=True)
        analysis = (context, {}, {}, {}, [], {}, [])
        app = SimpleNamespace(
            _update_series_memory_from_analysis=MagicMock())
        status = {}

        gui.App._update_resumed_series_memory(
            app, "episode.srt", analysis, "Turkish", status)

        app._update_series_memory_from_analysis.assert_not_called()
        self.assertEqual(status, {
            "status": "skipped", "reason": "analysis_incomplete",
            "changed": 0,
        })


if __name__ == "__main__":
    unittest.main()
