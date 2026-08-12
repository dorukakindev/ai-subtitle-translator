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
            source.count("_partition_quality_blocks("), 3)
        self.assertGreaterEqual(
            source.count("_restore_quality_failure_blocks("), 3)
        self.assertNotIn(
            "eksik çeviri kaldığı için Critic/Polish/Native/",
            source,
        )

    def test_hybrid_batch_runs_quality_on_healthy_cues_before_partial_delivery(self):
        source = inspect.getsource(gui.App._run_hybrid)
        partition = source.index("_partition_quality_blocks(_final_blocks)")
        critic = source.index("ht.critic_pass_with_helper(", partition)
        restore = source.index("_restore_quality_failure_blocks(", critic)
        partial_delivery = source.index("if _has_missing:", restore)

        self.assertLess(partition, critic)
        self.assertLess(critic, restore)
        self.assertLess(restore, partial_delivery)
        self.assertNotIn("Critic/Polish atlandı", source)
        self.assertIn('"pass_status": _pass_status', source[partial_delivery:])
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
