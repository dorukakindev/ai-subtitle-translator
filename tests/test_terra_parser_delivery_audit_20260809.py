import tempfile
import unittest
from pathlib import Path

import sdh_cleaner
import subtitle_formats


class LegacyEncodingSelectionTests(unittest.TestCase):
    def _assert_round_trip(self, encoding, unit, repetitions=8):
        expected = unit * repetitions
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, f"{encoding}.srt")
            path.write_bytes(expected.encode(encoding))
            self.assertEqual(subtitle_formats.read_subtitle_text(path), expected)

    def test_long_cp1253_is_not_misdecoded_as_cyrillic(self):
        unit = (
            "1\n00:00:00,000 --> 00:00:03,000\n"
            "Αυτή είναι μια μεγάλη ελληνική πρόταση για τη ζωή και τον άνθρωπο.\n\n"
        )
        self._assert_round_trip("cp1253", unit)

    def test_long_cp1255_is_not_misdecoded_as_cyrillic(self):
        unit = (
            "1\n00:00:00,000 --> 00:00:03,000\n"
            "זהו משפט ארוך בעברית על החיים והאדם בעולם.\n\n"
        )
        self._assert_round_trip("cp1255", unit)

    def test_long_cp1250_preserves_central_european_letters(self):
        unit = (
            "1\n00:00:00,000 --> 00:00:03,000\n"
            "To jest długie polskie zdanie o życiu człowieka na tym świecie.\n\n"
        )
        self._assert_round_trip("cp1250", unit)

    def test_short_cp1252_smart_quote_does_not_force_mac_roman(self):
        unit = (
            "1\n00:00:00,000 --> 00:00:03,000\n"
            "C’est une phrase française.\n\n"
        )
        self._assert_round_trip("cp1252", unit, repetitions=1)

    def test_utf32_bom_is_not_misread_as_utf16(self):
        unit = "1\n00:00:00,000 --> 00:00:03,000\nHello Ω\n\n"
        self._assert_round_trip("utf-32", unit, repetitions=1)

    def test_bomless_utf32_endianness_is_detected_before_utf16(self):
        unit = "1\n00:00:00,000 --> 00:00:03,000\nHello Ω\n\n"
        for encoding in ("utf-32-le", "utf-32-be"):
            with self.subTest(encoding=encoding):
                self._assert_round_trip(encoding, unit, repetitions=1)


class AssMetadataSafetyTests(unittest.TestCase):
    def _parse(self, dialogue, language=None):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            f"{dialogue}\n"
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "sample.ass")
            path.write_text(content, encoding="utf-8")
            return subtitle_formats.parse_ass(path, lyric_language=language)

    def test_numeric_actor_placeholder_is_not_added_as_speaker(self):
        blocks = self._parse(
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,0,0,0,0,,Hello"
        )
        self.assertEqual(blocks[0][2], "Hello")

    def test_non_japanese_source_prefers_english_duplicate_lyrics(self):
        blocks = self._parse(
            "Dialogue: 0,0:00:01.00,0:00:02.00,OPEN,John,0,0,0,,Hello\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,OPJP,,0,0,0,,日本語\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,OPEN,,0,0,0,,English",
            language="Arabic",
        )
        self.assertEqual([text for _idx, _ts, text in blocks], ["John: Hello", "English"])


class VttLosslessBoundaryTests(unittest.TestCase):
    def _parse(self, content):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "sample.vtt")
            path.write_text(content, encoding="utf-8")
            return subtitle_formats.parse_vtt(path)

    def test_id_on_previous_cue_does_not_drop_final_text_before_bare_timing(self):
        blocks = self._parse(
            "WEBVTT\n\ncue-a\n00:00:01.000 --> 00:00:02.000\n"
            "First line\nFinal line\n00:00:03.000 --> 00:00:04.000\nSecond cue"
        )
        self.assertEqual(
            [text for _idx, _ts, text in blocks],
            ["First line\nFinal line", "Second cue"],
        )

    def test_related_arbitrary_ids_still_separate_blankless_cues(self):
        blocks = self._parse(
            "WEBVTT\n\nfirst-cue\n00:00:01.000 --> 00:00:02.000\nFirst\n"
            "second-cue\n00:00:03.000 --> 00:00:04.000\nSecond"
        )
        self.assertEqual([text for _idx, _ts, text in blocks], ["First", "Second"])

    def test_alphanumeric_dialogue_before_timing_is_not_mistaken_for_id(self):
        blocks = self._parse(
            "WEBVTT\n\ncue-a\n00:00:01.000 --> 00:00:02.000\n"
            "It was COVID19\n00:00:03.000 --> 00:00:04.000\nSecond cue"
        )
        self.assertEqual(
            [text for _idx, _ts, text in blocks],
            ["It was COVID19", "Second cue"],
        )


class SourceDrivenSdhSafetyTests(unittest.TestCase):
    def test_punctuated_one_word_dialogue_is_not_plain_sdh(self):
        self.assertFalse(sdh_cleaner.is_sdh_only("Whisper."))
        self.assertFalse(sdh_cleaner.is_sdh_only("Laugh!"))
        self.assertTrue(sdh_cleaner.is_sdh_only("WHISPERING"))
        self.assertTrue(sdh_cleaner.is_sdh_only("APPLAUSE!"))

    def test_dropped_source_sdh_does_not_delete_new_grammatical_aside(self):
        self.assertEqual(
            sdh_cleaner.strip_labels_by_source(
                "Eve gitti (sanırım).", "[soft music] He went home."
            ),
            "Eve gitti (sanırım).",
        )

    def test_translated_descriptor_is_still_removed_after_delimiter_change(self):
        self.assertEqual(
            sdh_cleaner.strip_labels_by_source(
                "(müzik) Eve gitti.", "[music] He went home."
            ),
            "Eve gitti.",
        )


if __name__ == "__main__":
    unittest.main()
