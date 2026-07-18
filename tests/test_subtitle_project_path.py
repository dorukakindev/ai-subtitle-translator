import sys
import unittest
from pathlib import Path

import hybrid_translate as ht


class SubtitleProjectPathTest(unittest.TestCase):
    def test_invalid_external_path_falls_back_to_installed_subtitle_localizer(self):
        bad_path = str(Path.home() / "Downloads")

        resolved = ht.resolve_subtitle_project_path(bad_path)

        self.assertTrue((Path(resolved) / "subtitle_localizer").is_dir())

    def test_ensure_path_recovers_after_bad_external_path(self):
        bad_path = str(Path.home() / "Downloads")

        ht.set_project_path(bad_path)
        ht._ensure_path()

        self.assertTrue(any((Path(p) / "subtitle_localizer").is_dir() for p in sys.path))


if __name__ == "__main__":
    unittest.main()
