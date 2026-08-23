# -*- coding: utf-8 -*-
import types
import unittest
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as g


TS1 = "00:00:00,000 --> 00:00:01,000"
TS2 = "00:00:01,000 --> 00:00:04,000"


class SourceBoundSegmentationTest(unittest.TestCase):
    def test_source_sentence_boundary_excludes_ai_window(self):
        blocks = [("1", TS1, "Noktası düşmüş cümle"),
                  ("2", TS2, "Başka bir cümle")]
        source = [("1", TS1, "Complete sentence."),
                  ("2", TS2, "Another sentence.")]
        permissions = g._source_merge_permissions(source)
        self.assertEqual(
            g._segmentation_candidates(
                blocks, source_permissions=permissions), [])

    def test_ai_cannot_merge_across_source_sentence_boundary(self):
        blocks = [("1", TS1, "Noktası düşmüş cümle"),
                  ("2", TS2, "Başka bir cümle")]
        source = [("1", TS1, "Complete sentence."),
                  ("2", TS2, "Another sentence.")]
        with patch.object(ht, "_safe_chat_create") as api:
            out = g.ai_resegment_cues(
                blocks, "fake-key", source_cues=source)
        api.assert_not_called()
        self.assertEqual(len(out), 2)

    def test_malformed_source_fails_closed(self):
        blocks = [("1", TS1, "devam eden"),
                  ("2", TS2, "cümle")]
        source = [("1", "bozuk", "continuing"),
                  ("2", TS2, "sentence")]
        self.assertEqual(
            g.merge_fragmented_cues(blocks, source_cues=source), blocks)

    def test_ambiguous_layer_timestamps_fail_closed(self):
        blocks = [("1", TS1, "devam eden"),
                  ("2", TS2, "cümle")]
        source = [("1", TS1, "continuing"),
                  ("x", TS1, "another subtitle layer"),
                  ("2", TS2, "sentence.")]
        self.assertEqual(
            g.merge_fragmented_cues(blocks, source_cues=source), blocks)


class LineRewriteSafetyTest(unittest.TestCase):
    def test_font_tag_attributes_are_not_split_or_reordered(self):
        value = ('<font color="#ffffff" size="20">Bu satır etiketli ve '
                 'gerçekten çok uzun bir satır</font>\nkısa')
        out = g._redistribute_two_lines(value)
        self.assertEqual(out.replace("\n", " ").split(),
                         value.replace("\n", " ").split())
        self.assertEqual(out.count("<font "), 1)
        self.assertEqual(out.count("</font>"), 1)
        self.assertTrue(all(g._visible_len(line) <= g._LINE_THRESHOLD
                            for line in out.split("\n")))

    def test_rebalance_does_not_create_single_character_remainder(self):
        for value in ("Uzun cümle\niçin o", "O ve\nsonra devam eder"):
            with self.subTest(value=value):
                self.assertEqual(g._rebalance_line_break(value), value)

    def test_preexisting_single_character_line_is_repaired(self):
        self.assertEqual(
            g._rebalance_line_break("O\nbir edebiyat eleştirmeniydi."),
            "O bir\nedebiyat eleştirmeniydi.")

    def test_rebalance_does_not_tokenize_font_attributes(self):
        value = ('<font color="#fff" size="20">Uzun bir anlatım ve</font>\n'
                 'sonra devam eder.')
        self.assertEqual(g._rebalance_line_break(value), value)


class DeliveryNormalizationSafetyTest(unittest.TestCase):
    def test_mixed_case_file_preserves_deliberate_caps_cue(self):
        blocks = [("1", TS1, "PATLAMA")]
        src_map = {"1": "EXPLOSION"}
        src_map.update({str(i): "Ordinary sentence." for i in range(2, 12)})
        out, changed = g._normalize_all_caps_delivery(blocks, src_map)
        self.assertEqual(out, blocks)
        self.assertEqual(changed, 0)

    def test_all_caps_file_is_still_normalized(self):
        blocks = [(str(i), TS1, "BU BIR CÜMLEDIR") for i in range(1, 11)]
        src_map = {str(i): "THIS IS A SENTENCE" for i in range(1, 11)}
        out, changed = g._normalize_all_caps_delivery(blocks, src_map)
        self.assertEqual(changed, 10)
        self.assertTrue(all(text == "Bu bir cümledir" for _i, _ts, text in out))

    def test_measurement_primes_are_preserved(self):
        self.assertEqual(
            g._normalize_delivery_typography("5′ 6″ ve “ölçü”"),
            '5′ 6″ ve "ölçü"')


class CondenseOrderingTest(unittest.TestCase):
    BLOCKS = [
        ("1", TS1, "Bu satır tek başına gereğinden hızlıdır"),
        ("2", TS2, "ama birleşince okunur."),
    ]
    SOURCE = [
        ("1", TS1, "This source sentence continues"),
        ("2", TS2, "into this fragment."),
    ]

    def test_visible_cps_ignores_format_tags(self):
        blocks = [("1", TS1, '<font color="#fff">Kısa metin</font>')]
        self.assertEqual(ht.find_fast_lines(blocks, 21.0), [])

    def test_skip_ids_are_not_sent_to_condense(self):
        self.assertEqual(
            ht.find_fast_lines(self.BLOCKS, 21.0, skip_ids={"1"}), [])

    def test_guaranteed_merge_resolves_fast_cue(self):
        self.assertEqual(
            g._merge_resolved_fast_ids(self.BLOCKS, self.SOURCE), {"1"})

    def test_report_only_does_not_call_condense_api(self):
        logs = []
        app = types.SimpleNamespace(
            condense_var=types.SimpleNamespace(get=lambda: True),
            _active_snapshot={"quality_report_only": True},
            _log=lambda *args: logs.append(args),
        )
        with patch.object(ht, "condense_fast_lines") as condense:
            out = g.App._maybe_condense(
                app, self.BLOCKS, "key", "url", "model", "Turkish")
        condense.assert_not_called()
        self.assertEqual(out, self.BLOCKS)
        self.assertTrue(logs)


class CueFillReportOnlyTest(unittest.TestCase):
    BLOCKS = [
        ("368", "00:30:00,000 --> 00:30:07,000", "Cümlenin ilk yarısı"),
        ("369", "00:30:07,000 --> 00:30:07,400",
         "yani bu ikinci parça çok kısa bir cue içine sıkıştırılmış durumda ve okunamaz."),
    ]
    SOURCE = [
        ("368", "00:30:00,000 --> 00:30:07,000",
         "A fairly long English narration sentence with room here"),
        ("369", "00:30:07,000 --> 00:30:07,400", "elements."),
    ]

    def test_report_only_logs_candidate_without_moving_text(self):
        logs = []
        app = types.SimpleNamespace(
            _active_snapshot={
                "quality_report_only": True,
                "cue_fill_move": True,
                "linebreak": True,
            },
            _log=lambda *args: logs.append(args),
        )
        out = g.App._maybe_rebalance_cue_fill(
            app, self.BLOCKS, self.SOURCE)
        self.assertEqual(out, self.BLOCKS)
        self.assertTrue(any("yalnız raporlandı" in row[0] for row in logs))


if __name__ == "__main__":
    unittest.main()
