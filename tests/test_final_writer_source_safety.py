import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class FinalWriterSourceSafetyTests(unittest.TestCase):
    def test_writer_does_not_apply_historical_corpus_rewrites(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Rat ve Client, Macabre Collection'da."),
            ("2", "00:00:02,100 --> 00:00:03,000", "Bu azap ne zaman bitecek?"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "final.srt"
            gui.write_srt(path, blocks, target_language="Turkish")
            parsed = gui.parse_srt(path)
        self.assertEqual(parsed[0][2], blocks[0][2])
        self.assertEqual(parsed[1][2], blocks[1][2])


if __name__ == "__main__":
    unittest.main()
