import unittest
from unittest.mock import patch, MagicMock
from helper_models import call_bedrock_converse


class TestBedrockConverse(unittest.TestCase):
    def test_call_bedrock_converse_builds_arguments_correctly(self):
        # Setup mocks
        mock_boto3 = MagicMock()
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock converse return response
        mock_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Düzeltilmiş altyazı metni"}]
                }
            },
            "usage": {
                "inputTokens": 10,
                "outputTokens": 5,
                "totalTokens": 15
            }
        }
        mock_client.converse.return_value = mock_response
        
        # Run function with mocked sys.modules for boto3
        messages = [
            {"role": "system", "content": "Sistem komutu"},
            {"role": "user", "content": "Kullanıcı girdisi"}
        ]
        
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            resp = call_bedrock_converse(
                model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                messages=messages,
                temperature=0.4,
                max_tokens=100,
                api_key_str="fake_key_id:fake_secret_key:us-east-1",
                base_url="https://bedrock.dummy"
            )
        
        # Assertions
        mock_boto3.Session.assert_called_once_with(
            aws_access_key_id="fake_key_id",
            aws_secret_access_key="fake_secret_key",
            region_name="us-east-1"
        )
        
        mock_client.converse.assert_called_once_with(
            modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
            messages=[
                {"role": "user", "content": [{"text": "Kullanıcı girdisi"}]}
            ],
            system=[
                {"text": "Sistem komutu"}
            ],
            inferenceConfig={
                "temperature": 0.4,
                "maxTokens": 100
            }
        )
        
        self.assertEqual(resp.choices[0].message.content, "Düzeltilmiş altyazı metni")
        self.assertEqual(resp.usage.total_tokens, 15)


if __name__ == "__main__":
    unittest.main()
