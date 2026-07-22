import unittest
from unittest.mock import MagicMock, patch
import inspect
import subtitle_translator_gui as gui


class PipelinePassParityTest(unittest.TestCase):

    def test_post_process_flow_includes_fill_hata_tag_restore_and_tm(self):
        """Verify _run_post_process includes fill_hata, tag restore, and TM store."""
        src = inspect.getsource(gui.App._run_post_process)
        self.assertIn("_fill_hata_with_source", src, "_run_post_process must call _fill_hata_with_source!")
        self.assertIn("_restore_tags_blocks", src, "_run_post_process must call _restore_tags_blocks!")
        self.assertIn("_store_tm_pairs", src, "_run_post_process must call _store_tm_pairs!")
        self.assertIn("source_driven=True", src, "_run_post_process must use source-driven SDH clean!")

    def test_write_results_condense_order(self):
        """Verify _maybe_condense runs after critic/polish/native in _write_results."""
        src = inspect.getsource(gui.App._write_results)
        condense_pos = src.find("_maybe_condense")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertGreater(condense_pos, critic_pos, "In _write_results, _maybe_condense must run after critic_pass_with_helper!")

    def test_hata_unresolved_check_before_pre_pass_and_quality_passes(self):
        """Verify [HATA] missing check is performed before quality passes start in _run_hybrid."""
        src = inspect.getsource(gui.App._run_hybrid)
        unresolved_pos = src.find("_unresolved_missing = sum(")
        critic_pos = src.find("ht.critic_pass_with_helper")
        self.assertLess(unresolved_pos, critic_pos, "_unresolved_missing must be checked before ht.critic_pass_with_helper!")

    def test_qc_counters_record_applied_diffs(self):
        """Verify QC counters use _record_pass_change rather than issue count."""
        src_sh = inspect.getsource(gui.App._run_sync_hybrid)
        src_rh = inspect.getsource(gui.App._run_hybrid)
        
        self.assertIn("_n_auto = _record_pass_change", src_sh, "_run_sync_hybrid must record actual QC auto changes!")
        self.assertIn("_n_auto = _record_pass_change", src_rh, "_run_hybrid must record actual QC auto changes!")


if __name__ == "__main__":
    unittest.main()
