import inspect
import unittest

import subtitle_translator_gui as gui


class ContextCacheLifecycleTest(unittest.TestCase):
    def test_successful_hybrid_flows_do_not_delete_valid_analysis_cache(self):
        sync_source = inspect.getsource(gui.App._run_sync_hybrid)
        batch_source = inspect.getsource(gui.App._run_hybrid)

        self.assertNotIn("clear_context_cache(filepath)", sync_source)
        self.assertNotIn("clear_context_cache(filepath)", batch_source)


if __name__ == "__main__":
    unittest.main()
