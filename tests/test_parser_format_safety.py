import tempfile
import unittest
from pathlib import Path

from subtitle_formats import parse_ass, parse_vtt, read_subtitle_text
from subtitle_localizer.srt import parse_srt


class ParserFormatSafetyTest(unittest.TestCase):
    def test_utf16_bom_is_consumed_before_ass_section_matching(self):
        content = (
            "[Events]\n"
            "Format: Start, End, Text, Style\n"
            "Dialogue: 0:00:01.00,0:00:03.00,Hello [there],Default\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.ass"
            path.write_bytes(content.encode("utf-16"))

            self.assertFalse(read_subtitle_text(path).startswith("\ufeff"))
            self.assertEqual(parse_ass(path), [
                ("1", "00:00:01,000 --> 00:00:03,000", "Hello [there]")
            ])

    def test_karaoke_style_lyrics_are_not_silently_dropped(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:03.00,Karaoke,,0,0,0,,Sing this line\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lyrics.ass"
            path.write_text(content, encoding="utf-8")

            self.assertEqual(parse_ass(path), [
                ("1", "00:00:01,000 --> 00:00:03,000", "Sing this line")
            ])

    def test_vtt_short_milliseconds_reach_timestamp_normalizer(self):
        content = (
            "WEBVTT\n\n"
            "00:00:01.5 --> 00:00:03.25\n"
            "Short fraction\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short-ms.vtt"
            path.write_text(content, encoding="utf-8")

            self.assertEqual(parse_vtt(path), [
                ("1", "00:00:01,500 --> 00:00:03,250", "Short fraction")
            ])

    def test_srt_short_milliseconds_reach_localizer_parser(self):
        content = (
            "1\n"
            "00;00;01.5 --> 00;00;03,25\n"
            "Short fraction\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short-ms.srt"
            path.write_text(content, encoding="utf-8")

            normalized = read_subtitle_text(path)
            self.assertIn("00:00:01,500 --> 00:00:03,250", normalized)
            self.assertEqual(
                [(cue.start, cue.end, cue.text) for cue in parse_srt(normalized)],
                [("00:00:01,500", "00:00:03,250", "Short fraction")],
            )


if __name__ == "__main__":
    unittest.main()
