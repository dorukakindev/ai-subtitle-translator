"""Parser and source-driven SDH regressions from the delivery audit."""
import os
import tempfile
import unittest
from pathlib import Path

import subtitle_formats as sf
import sdh_cleaner as sdh


def _write(directory, name, text, encoding="utf-8"):
    path = Path(directory) / name
    path.write_text(text, encoding=encoding)
    return str(path)


class LegacyEncodingRegressionTest(unittest.TestCase):
    def _read_encoded(self, encoding, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.srt"
            path.write_bytes(("1\n00:00:01,000 --> 00:00:02,000\n" + text + "\n").encode(encoding))
            return sf.read_subtitle_text(path)

    def test_short_cp1253_is_not_forced_through_cp1251(self):
        self.assertIn("Καλημέρα", self._read_encoded("cp1253", "Καλημέρα κόσμε"))

    def test_short_cp1256_is_not_forced_through_cp1251(self):
        self.assertIn("مرحبا", self._read_encoded("cp1256", "مرحبا بالعالم"))


class VttBoundaryRegressionTest(unittest.TestCase):
    def test_note_without_blank_separator_does_not_consume_next_cue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "note.vtt", (
                "WEBVTT\n\nNOTE encoder metadata\ncontinued metadata\n"
                "cue:any-arbitrary-id\n00:00:01.000 --> 00:00:02.000\nHello\n"
            ))
            self.assertEqual(sf.parse_vtt(path), [
                ("1", "00:00:01,000 --> 00:00:02,000", "Hello"),
            ])

    def test_final_cue_survives_without_blank_separator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "last.vtt", (
                "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nFirst\n"
                "00:00:02.000 --> 00:00:03.000\nLast line"
            ))
            self.assertEqual([cue[2] for cue in sf.parse_vtt(path)], ["First", "Last line"])


class AssMeaningRegressionTest(unittest.TestCase):
    ASS_HEADER = (
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    def test_fx_style_with_visible_text_is_not_dropped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "fx.ass", self.ASS_HEADER +
                          "Dialogue: 0,0:00:01.00,0:00:02.00,FX,,0,0,0,,EMERGENCY EXIT\n")
            self.assertEqual(sf.parse_ass(path)[0][2], "EMERGENCY EXIT")

    def test_fx_style_drops_only_known_override_driven_decorative_word(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "fx-decorative.ass", self.ASS_HEADER +
                          "Dialogue: 0,0:00:01.00,0:00:02.00,FX,,0,0,0,,{\\blur5}spark\n"
                          "Dialogue: 0,0:00:03.00,0:00:04.00,FX,,0,0,0,,EXIT\n")
            self.assertEqual([cue[2] for cue in sf.parse_ass(path)], ["EXIT"])

    def test_ass_name_is_preserved_for_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "name.ass", self.ASS_HEADER +
                          "Dialogue: 0,0:00:01.00,0:00:02.00,Default,John,0,0,0,,Run!\n")
            self.assertEqual(sf.parse_ass(path)[0][2], "John: Run!")

    def test_requested_lyric_language_wins_for_same_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, "song.ass", self.ASS_HEADER +
                          "Dialogue: 0,0:00:01.00,0:00:02.00,OP-EN,,0,0,0,,English lyric\n"
                          "Dialogue: 0,0:00:01.00,0:00:02.00,OP-JP,,0,0,0,,Japanese lyric\n")
            self.assertEqual([cue[2] for cue in sf.parse_ass(path, lyric_language="Japanese")],
                             ["Japanese lyric"])


class SourceDrivenSdhRegressionTest(unittest.TestCase):
    def test_one_word_dialogue_is_not_dropped_when_source_is_dialogue(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Koş!")]
        self.assertEqual(sdh.clean_sdh_blocks(
            blocks, src_map={"1": "Running!"}, source_driven=True), blocks)

    def test_real_target_parenthesis_survives_source_sdh_cleanup(self):
        self.assertEqual(
            sdh.strip_labels_by_source("(f(x)) değerini hesapla. [KAPI KAPANIR]",
                                       "[door closes] Calculate f(x)."),
            "(f(x)) değerini hesapla.")


if __name__ == "__main__":
    unittest.main()
