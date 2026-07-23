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

if __name__ == '__main__':
    unittest.main()
