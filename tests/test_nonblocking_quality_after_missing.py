import inspect
import unittest

import subtitle_translator_gui as gui


_TS = "00:00:01,000 --> 00:00:02,000"


class NonblockingQualityAfterMissingTest(unittest.TestCase):
    def test_missing_cue_is_isolated_and_restored_in_original_order(self):
        blocks = [
            ("1", _TS, "Sağlam bir."),
            ("2", _TS, "[ÇEVİRİ EKSİK]"),
            ("3", _TS, "Sağlam üç."),
        ]

        healthy, failed, order = gui._partition_quality_blocks(blocks)
        self.assertEqual([block[0] for block in healthy], ["1", "3"])
        self.assertEqual(set(failed), {"2"})

        processed = [("1", _TS, "Düzeltilmiş bir.")]
        restored = gui._restore_quality_failure_blocks(
            processed, failed, order)

        self.assertEqual(restored, [
            ("1", _TS, "Düzeltilmiş bir."),
            ("2", _TS, "[ÇEVİRİ EKSİK]"),
        ])

    def test_both_main_postprocess_flows_continue_on_healthy_cues(self):
        source = inspect.getsource(gui.App)
        self.assertGreaterEqual(
            source.count("_partition_quality_blocks(sorted_blocks)"), 2)
        self.assertGreaterEqual(
            source.count("_restore_quality_failure_blocks("), 2)
        self.assertNotIn(
            "eksik çeviri kaldığı için Critic/Polish/Native/",
            source,
        )
        self.assertNotIn(
            "eksik çeviri kaldığı için model tabanlı kalite "
            "geçişleri atlandı",
            source,
        )

    def test_quality_report_contains_exact_repair_advisory(self):
        report = gui.build_quality_report_text(
            [{
                "name": "film.srt",
                "total": 1,
                "pass_trace": {"__repair_advisories__": [{
                    "id": "4",
                    "reason": "locked_term_violation",
                    "source": "John arrived.",
                    "candidate": "Mary geldi.",
                }]},
            }],
            "gpt-5.4", "Turkish", "sync", 0,
        )

        self.assertIn("Onarım sonrası elle incelenecek : 1 cue", report)
        self.assertIn("#4: locked_term_violation", report)
        self.assertIn("kaynak='John arrived.'", report)
        self.assertIn("aday='Mary geldi.'", report)


if __name__ == "__main__":
    unittest.main()
