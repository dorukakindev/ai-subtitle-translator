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
    def test_fetch_batch_statuses_partial_failure(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        def mock_retrieve(bid):
            if bid == "b1":
                raise Exception("Network error")
            b = MagicMock()
            b.status = "completed"
            return b
            
        mock_client.batches.retrieve.side_effect = mock_retrieve
        
        res = gui._fetch_batch_statuses("key", ["b1", "b2"])
        self.assertEqual(res, {"b1": "unknown", "b2": "completed"})

if __name__ == '__main__':
    unittest.main()
