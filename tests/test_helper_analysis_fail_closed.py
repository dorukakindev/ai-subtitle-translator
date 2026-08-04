import inspect
import unittest

import subtitle_translator_gui as gui


class HelperAnalysisFailClosedTest(unittest.TestCase):
    def test_sync_hybrid_does_not_translate_after_total_analysis_failure(self):
        source = inspect.getsource(gui.App._run_sync_hybrid)
        analysis = source.index("result = ht.analyze_with_helper(")
        translation = source.index("batch_reqs, fmap = ht.build_batch_requests(")
        fresh_block = source[analysis:translation]

        self.assertIn("dosya boş bağlamla çevrilmedi", fresh_block)
        self.assertNotIn("ht.empty_analysis_result", fresh_block)

    def test_fresh_hybrid_batch_is_not_submitted_after_total_analysis_failure(self):
        source = inspect.getsource(gui.App._run_hybrid)
        analysis = source.index("result = ht.analyze_with_helper(")
        submit = source.index("batch_id = ht.submit_batch(", analysis)
        fresh_block = source[analysis:submit]

        self.assertIn("batch boş bağlamla gönderilmedi", fresh_block)
        self.assertNotIn("ht.empty_analysis_result", fresh_block)

    def test_paid_submitted_batch_reconnect_still_skips_reanalysis(self):
        source = inspect.getsource(gui.App._run_hybrid)
        reconnect = source.index(
            'file_status == "submitted" and sess_entry.get("batch_id")')
        analysis = source.index("result = ht.analyze_with_helper(")
        reconnect_block = source[reconnect:analysis]

        self.assertIn("ht.empty_analysis_result", reconnect_block)


if __name__ == "__main__":
    unittest.main()
