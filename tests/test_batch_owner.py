import unittest
from unittest.mock import patch, MagicMock
import threading
import os
import subtitle_translator_gui as gui

class TestBatchOwner(unittest.TestCase):
    def test_concurrent_register_unregister(self):
        app = gui.App.__new__(gui.App)
        app._batch_lock = threading.RLock()
        app._active_batches = {}
        
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as td:
            def mock_state_path(*args):
                return Path(td) / "batch_owner_123.json"
                
            with patch("subtitle_translator_gui.state_path", side_effect=mock_state_path), \
                 patch("os.getpid", return_value=123):
                
                app._register_batch("b1", "key1")
                self.assertTrue((Path(td) / "batch_owner_123.json").exists())
                app._unregister_batch("b1")
                self.assertFalse((Path(td) / "batch_owner_123.json").exists())

                # Simulate concurrent register
                def thread_func():
                    app._register_batch("b2", "key2")
                
                t = threading.Thread(target=thread_func)
                t.start()
                t.join()
                
                self.assertTrue((Path(td) / "batch_owner_123.json").exists())
                import json
                with open(Path(td) / "batch_owner_123.json") as f:
                    data = json.load(f)
                    self.assertEqual(data["batch_ids"], ["b2"])

if __name__ == '__main__':
    unittest.main()
