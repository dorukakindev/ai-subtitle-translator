import unittest
from unittest.mock import MagicMock, patch
import inspect
import subtitle_translator_gui as gui


class PipelinePassParityTest(unittest.TestCase):

    def test_post_process_flow_is_explicitly_source_less(self):
        """Existing translated SRT must not be reused as its own source."""
        src = inspect.getsource(gui.App._run_post_process)
        self.assertNotIn("_store_tm_pairs", src, "post-process must not store translation-to-translation TM pairs")
        self.assertIn("orig_cues = None", src)
        self.assertIn("analysis_result = None", src)
        self.assertNotIn("ht.load_subtitle(fp)", src)
        self.assertNotIn("ht.load_context_cache(", src)
        self.assertIn("source_driven=False", src)
        self.assertIn("if do_qc and orig_cues:", src)
        self.assertIn("QC atlandı: post-işlemde gerçek kaynak altyazı seçilmedi.", src)

    def test_write_results_condense_order(self):
        """Verify _maybe_condense runs after critic/polish/native in _write_results."""
        src = inspect.getsource(gui.App._write_results)
        condense_pos = src.find("_maybe_condense")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertGreater(condense_pos, critic_pos, "In _write_results, _maybe_condense must run after critic_pass_with_helper!")

    def test_hata_unresolved_check_before_pre_pass_and_quality_passes(self):
        """[HATA] count must run before it is converted to a visible marker."""
        src = inspect.getsource(gui.App._run_hybrid)
        unresolved_pos = src.find("_unresolved_missing = sum(")
        fill_pos = src.find("_fill_hata_with_source")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertGreater(fill_pos, unresolved_pos, "_fill_hata_with_source must not hide unresolved markers")
        self.assertLess(unresolved_pos, critic_pos, "_unresolved_missing must be checked before ht.critic_pass_with_helper!")

    def test_write_results_uses_canonical_tail_order_and_review_gate(self):
        src = inspect.getsource(gui.App._write_results)
        condense_pos = src.find("_maybe_condense")
        sdh_pos = src.find("clean_sdh")
        linebreak_pos = src.find("apply_line_breaks")
        qc_pos = src.find("_run_quality_check_inline")
        fill_pos = src.find("_fill_hata_with_source")
        restore_pos = src.find("_restore_tags_blocks")
        self.assertTrue(condense_pos < sdh_pos < linebreak_pos < qc_pos < fill_pos < restore_pos)
        self.assertNotIn("ht.qc_auto_fix", src, "plain batch QC must retain severity split and user review")

    def test_resume_qc_counters_record_applied_diffs(self):
        src = inspect.getsource(gui.App._wait_batch_hybrid)
        self.assertNotIn("_qc_fixes += len(", src)
        self.assertNotIn("_qc_auto_fixes += len(", src)

    def test_qc_counters_record_applied_diffs(self):
        """Verify QC counters use _record_pass_change rather than issue count."""
        src_sh = inspect.getsource(gui.App._run_sync_hybrid)
        src_rh = inspect.getsource(gui.App._run_hybrid)
        
        self.assertIn("_n_auto = _record_pass_change", src_sh, "_run_sync_hybrid must record actual QC auto changes!")
        self.assertIn("_n_auto = _record_pass_change", src_rh, "_run_hybrid must record actual QC auto changes!")

    def test_plain_report_records_actual_pass_and_qc_changes(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("_pass_fix = sum(", src)
        self.assertIn('stats=_qc_stats', src)
        self.assertIn('"pass_fix": _pass_fix', src)
        self.assertIn('"qc_auto": _qc_stats["qc_auto"]', src)
        self.assertIn('"qc": _qc_stats["qc"]', src)

    def test_final_semantic_checks_have_four_flow_parity(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                semantic_pos = src.rfind("_run_final_semantic_checks(")
                fill_pos = src.rfind("_fill_hata_with_source(")
                restore_pos = src.rfind("_restore_tags_blocks(")
                self.assertGreaterEqual(semantic_pos, 0)
                self.assertTrue(semantic_pos < fill_pos < restore_pos)
                self.assertIn('changed_ids=_pass_history.keys()', src)

    def test_term_normalize_precedes_canonical_tail_in_all_four_flows(self):
        flows = [
            gui.App._run_sync_hybrid,
            gui.App._wait_batch_hybrid,
            gui.App._write_results,
            gui.App._run_hybrid,
        ]
        for flow in flows:
            with self.subTest(flow=flow.__name__):
                src = inspect.getsource(flow)
                normalize_pos = src.rfind("_normalize_mixed_terms(")
                fill_pos = src.rfind("_fill_hata_with_source(")
                restore_pos = src.rfind("_restore_tags_blocks(")
                self.assertTrue(normalize_pos < fill_pos < restore_pos)

    def test_plain_sync_without_chain_can_run_opt_in_review(self):
        src = inspect.getsource(gui.App._write_results)
        self.assertIn("or not self.chain_ctx_var.get()", src)
        self.assertIn("ek API maliyeti", src)

    def test_hybrid_final_tail_reuses_single_raw_map(self):
        src = inspect.getsource(gui.App._run_hybrid)
        tail = src[src.rfind("_run_final_semantic_checks("):src.find(
            "write_srt(", src.rfind("_run_final_semantic_checks(")
        )]
        self.assertEqual(tail.count("_raw_src_map_from_cues(cues)"), 1)


if __name__ == "__main__":
    unittest.main()
