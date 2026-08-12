import hashlib
import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class DeliverySourceArchiveTest(unittest.TestCase):
    def test_source_is_archived_beside_output_reports(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input" / "movie English.ass"
            output = root / "output" / "movie" / "movie.srt"
            reports = root / "output" / "Raporlar"
            source.parent.mkdir()
            output.parent.mkdir(parents=True)
            source.write_bytes(b"[Script Info]\r\nTitle: Original\r\n")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            self.assertTrue(gui._write_output_source_fingerprint(
                reports, output, digest, source_path=source))

            archived = output.parent / "Raporlar" / "Kaynak" / source.name
            self.assertEqual(archived.read_bytes(), source.read_bytes())
            self.assertTrue(gui._output_source_fingerprint_path(
                reports, output).is_file())

    def test_different_same_named_sources_are_both_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "output" / "movie.srt"
            first = root / "one" / "source.srt"
            second = root / "two" / "source.srt"
            first.parent.mkdir()
            second.parent.mkdir()
            output.parent.mkdir()
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            one = gui._archive_delivery_source(first, output)
            two = gui._archive_delivery_source(second, output)

            self.assertNotEqual(one, two)
            self.assertEqual(one.read_bytes(), b"first")
            self.assertEqual(two.read_bytes(), b"second")

    def test_source_drift_fails_closed_without_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.vtt"
            output = root / "output" / "movie.srt"
            reports = root / "reports"
            source.write_bytes(b"changed")

            self.assertFalse(gui._write_output_source_fingerprint(
                reports, output, hashlib.sha256(b"original").hexdigest(),
                source_path=source))
            self.assertFalse((output.parent / "Raporlar" / "Kaynak").exists())
            self.assertFalse(gui._output_source_fingerprint_path(
                reports, output).exists())

    def test_partial_output_archives_source_at_delivery_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "input" / "source.srt"
            partial = (root / "delivery" / "Raporlar" / "Kurtarma"
                       / "movie.partial.srt")
            source.parent.mkdir()
            source.write_bytes(b"source")

            archived = gui._archive_delivery_source(source, partial)

            self.assertEqual(
                archived,
                root / "delivery" / "Raporlar" / "Kaynak" / "source.srt")
            self.assertFalse(
                (partial.parent / "Raporlar" / "Kaynak").exists())


if __name__ == "__main__":
    unittest.main()
