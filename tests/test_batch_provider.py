import unittest
from unittest.mock import patch, MagicMock
import subtitle_translator_gui as gui

class TestBatchProvider(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_fetch_batch_statuses_empty_url(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_batch = MagicMock()
        mock_batch.status = "completed"
        mock_client.batches.retrieve.return_value = mock_batch
        
        res = gui._fetch_batch_statuses("key", ["b1"])
        self.assertEqual(res, {"b1": "completed"})
        mock_openai.assert_called_once_with(api_key="key")

    @patch("openai.OpenAI")
    def test_fetch_batch_statuses_custom_url(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_batch = MagicMock()
        mock_batch.status = "in_progress"
        mock_client.batches.retrieve.return_value = mock_batch
        
        res = gui._fetch_batch_statuses("key", ["b1"], base_url="http://custom")
        self.assertEqual(res, {"b1": "in_progress"})
        mock_openai.assert_called_once_with(api_key="key", base_url="http://custom")

    @patch("openai.OpenAI")
    def test_fetch_batch_statuses_positional_log_fn(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_batch = MagicMock()
        mock_batch.status = "completed"
        mock_client.batches.retrieve.return_value = mock_batch

        logger = MagicMock()
        res = gui._fetch_batch_statuses("key", ["b1"], logger)
        self.assertEqual(res, {"b1": "completed"})
        mock_openai.assert_called_once_with(api_key="key")

    @patch("openai.OpenAI")
    def test_fetch_batch_statuses_keyword_base_url(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_batch = MagicMock()
        mock_batch.status = "in_progress"
        mock_client.batches.retrieve.return_value = mock_batch

        logger = MagicMock()
        res = gui._fetch_batch_statuses(api_key="key", batch_ids=["b1"], log_fn=logger, base_url="http://custom")
        self.assertEqual(res, {"b1": "in_progress"})
        mock_openai.assert_called_once_with(api_key="key", base_url="http://custom")

    @patch("subtitle_translator_gui._fetch_batch_statuses")
    def test_pending_batches_dialog_passes_correct_kwargs(self, mock_fetch):
        mock_fetch.return_value = {"b1": "completed"}
        captured_kwargs = {}

        def mock_fetch_impl(**kwargs):
            nonlocal captured_kwargs
            captured_kwargs = kwargs
            return {"b1": "completed"}

        mock_fetch.side_effect = mock_fetch_impl

        stub_log = MagicMock()
        stub_app = type("StubApp", (), {
            "_main_api_key": lambda s: "sk-custom-123",
            "_main_api_base_url": lambda s: "https://custom.provider.com/v1",
            "_log": stub_log,
        })()

        import inspect
        src = inspect.getsource(gui.App._show_pending_batches_dialog)
        self.assertIn("fetched = _fetch_batch_statuses(", src)
        self.assertIn("api_key=api_key", src)
        self.assertIn("batch_ids=batch_ids", src)
        self.assertIn("log_fn=self._log", src)
        self.assertIn("base_url=base_url", src)

        api_key = stub_app._main_api_key()
        base_url = stub_app._main_api_base_url()
        batch_ids = ["b1"]

        gui._fetch_batch_statuses(
            api_key=api_key,
            batch_ids=batch_ids,
            log_fn=stub_app._log,
            base_url=base_url,
        )

        self.assertEqual(captured_kwargs["api_key"], "sk-custom-123")
        self.assertEqual(captured_kwargs["base_url"], "https://custom.provider.com/v1")
        self.assertIs(captured_kwargs["log_fn"], stub_log)
        self.assertTrue(callable(captured_kwargs["log_fn"]))
        self.assertIsInstance(captured_kwargs["base_url"], str)

if __name__ == '__main__':
    unittest.main()
