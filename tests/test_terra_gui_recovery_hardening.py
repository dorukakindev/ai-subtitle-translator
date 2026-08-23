import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import subtitle_translator_gui as gui


class TerraGuiRecoveryHardeningTest(unittest.TestCase):
    def test_merge_keeps_missing_marker_as_own_recovery_boundary(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bu cümle"),
            ("2", "00:00:02,050 --> 00:00:03,000", "[ÇEVİRİ EKSİK]"),
            ("3", "00:00:03,050 --> 00:00:04,000", "devam ediyor."),
        ]
        merged = gui.merge_fragmented_cues(blocks, max_gap_ms=100)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[1][2], "[ÇEVİRİ EKSİK]")

    def test_credit_is_not_sent_to_missing_cue_recovery(self):
        items = [
            {"i": "1", "t": "Translation: ExampleGroup"},
            {"i": "2", "t": "Real dialogue."},
        ]
        raw = json.dumps([{"i": "2", "t": "Gerçek diyalog."}])
        self.assertEqual(gui._missing_block_items(items, raw), [])

    def test_existing_english_dialogue_is_not_complete(self):
        source = [("1", "00:00:01,000 --> 00:00:02,000", "Where are you?")]
        output = [("1", "00:00:01,000 --> 00:00:02,000", "Where are you?")]
        self.assertFalse(gui._existing_output_is_complete(output, source))

    def test_proper_name_echo_does_not_trigger_untranslated_guard(self):
        source = [("1", "00:00:01,000 --> 00:00:02,000", "Penicillium camemberti")]
        output = [("1", "00:00:01,000 --> 00:00:02,000", "Penicillium camemberti")]
        self.assertTrue(gui._existing_output_is_complete(output, source))

    def test_delivery_quote_cleanup_does_not_turn_cause_into_quote(self):
        blocks = [("1", "00:00:02,000 --> 00:00:03,000", "Çünkü çok geç.")]
        source = [("1", "00:00:02,000 --> 00:00:03,000", "'Cause it's late.")]
        result, _count = gui._normalize_delivery_ocr_quote_markers(
            blocks, gui._delivery_source_map(blocks, source))
        self.assertEqual(result[0][2], "Çünkü çok geç.")

    def test_csharp_is_not_an_ocr_quote_marker(self):
        blocks = [("1", "00:00:02,000 --> 00:00:03,000", "C# biliyorum.")]
        source = [("1", "00:00:02,000 --> 00:00:03,000", "I know C#")]
        result, _count = gui._normalize_delivery_ocr_quote_markers(
            blocks, gui._delivery_source_map(blocks, source))
        self.assertEqual(result[0][2], "C# biliyorum.")

    def test_continued_ocr_quote_is_not_reopened_in_every_cue(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bence hükümet,"),
            ("2", "00:00:02,000 --> 00:00:03,000", "ama siyaset açısından'"),
            ("3", "00:00:03,000 --> 00:00:04,000", "kaygı duyuyor."),
        ]
        source = {
            "1": "TRANSLATOR: 'I think the Government wants to",
            "2": "'but in terms of politics",
            "3": "'they are worried.''",
        }
        result, _count = gui._normalize_delivery_ocr_quote_markers(blocks, source)
        self.assertEqual([text for _idx, _ts, text in result], [
            '"Bence hükümet,',
            "ama siyaset açısından",
            'kaygı duyuyor."',
        ])

    def test_single_apostrophe_ocr_quote_closes_as_double_quote(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Anne, kan!'"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Bu ilk satır,"),
            ("3", "00:00:04,000 --> 00:00:05,000", "ve bu son satır.'"),
        ]
        source = {
            "1": "'Mother, blood!'",
            "2": "'This is the first line,",
            "3": "'and this is the last line.'",
        }
        result, _count = gui._normalize_delivery_ocr_quote_markers(blocks, source)
        self.assertEqual([text for _idx, _ts, text in result], [
            '"Anne, kan!"',
            '"Bu ilk satır,',
            've bu son satır."',
        ])

    def test_non_turkish_writer_does_not_latinize_cyrillic(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "ru.srt"
            gui.write_srt(output, [("1", "00:00:01,000 --> 00:00:02,000", "СОК")], "Russian")
            self.assertIn("СОК", output.read_text(encoding="utf-8"))

    def test_delivery_audit_rejects_reversed_and_signature_overlap(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source.srt"
            output = Path(root) / "output.srt"
            gui.write_srt(source, [("1", "00:00:00,000 --> 00:00:02,000", "Hello")], "English")
            output.write_text(
                "0\n00:00:00,500 --> 00:00:01,500\ndiscord: ceviri2\n\n"
                "1\n00:00:00,000 --> 00:00:02,000\nMerhaba\n\n"
                "2\n00:00:04,000 --> 00:00:03,000\nTers\n",
                encoding="utf-8")
            audit = gui._subtitle_delivery_audit(source, output)
        self.assertEqual(audit["status"], "review")
        self.assertEqual(audit["reversed_timestamp_ids"], ["2"])
        self.assertEqual(audit["signature_overlap_ids"], ["0"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_pass_history_records_partial_pass_changes_after_guard(self):
        before = [("1", "00:00:01,000 --> 00:00:02,000", "Eski.")]
        after = [("1", "00:00:01,000 --> 00:00:02,000", "Yeni.")]
        trace, history = {}, {}
        self.assertEqual(gui._record_pass_change(trace, "Critic", before, after, history), 1)
        self.assertEqual(history["1"][0]["after"], "Yeni.")

    def test_ass_parser_receives_per_file_source_language(self):
        with patch.object(gui, "parse_ass", return_value=[]) as parse_ass:
            gui.parse_subtitle("episode.ass", "Japanese")
        parse_ass.assert_called_once_with("episode.ass", lyric_language="ja")

    def test_bare_english_sdh_is_expected_removed_in_delivery_audit(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source.srt"
            output = Path(root) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n[Muffled speaking]\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\n[Frog croaks]\n\n"
                "3\n00:00:05,000 --> 00:00:06,000\n-[ <i>Muffled speaking</i>]\n\n"
                "4\n00:00:07,000 --> 00:00:08,000\n-[ <i>Conversing in\n"
                "foreign language]</i>\n\n"
                "5\n00:00:09,000 --> 00:00:10,000\n<i>(Rooster crows)</i>\n\n"
                "6\n00:00:11,000 --> 00:00:12,000\nNeigh!\n\n"
                "7\n00:00:13,000 --> 00:00:14,000\nTHUNDER RUMBLES\n\n"
                "8\n00:00:15,000 --> 00:00:16,000\nSEAGULLS CRY\n\n"
                "9\n00:00:17,000 --> 00:00:18,000\nMEN SHOUT\n",
                encoding="utf-8")
            output.write_text("", encoding="utf-8")
            audit = gui._subtitle_delivery_audit(source, output)
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(
            audit["expected_removed_ids"],
            ["1", "2", "3", "4", "5", "6", "7", "8", "9"])


if __name__ == "__main__":
    unittest.main()
