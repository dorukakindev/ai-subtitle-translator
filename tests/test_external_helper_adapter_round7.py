import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import helper_models as helpers
import hybrid_translate as ht


class BedrockContentDeliveryTest(unittest.TestCase):
    def test_all_text_blocks_are_preserved_and_system_list_is_normalized(self):
        boto3 = MagicMock()
        client = MagicMock()
        boto3.Session.return_value.client.return_value = client
        client.converse.return_value = {
            "output": {"message": {"content": [
                {"reasoningContent": {"reasoningText": {"text": "hidden"}}},
                {"text": "ilk "}, {"text": "ikinci"},
            ]}},
            "usage": {"inputTokens": 2, "outputTokens": 3},
        }

        with patch.dict("sys.modules", {"boto3": boto3}):
            response = helpers.call_bedrock_converse("model", [
                {"role": "system", "content": [{"type": "text", "text": "kural"}]},
                {"role": "user", "content": "istek"},
            ])

        self.assertEqual(response.choices[0].message.content, "ilk ikinci")
        self.assertEqual(
            client.converse.call_args.kwargs["system"], [{"text": "kural"}])

    def test_missing_bedrock_text_content_is_explicit_adapter_error(self):
        boto3 = MagicMock()
        client = MagicMock()
        boto3.Session.return_value.client.return_value = client
        client.converse.return_value = {
            "output": {"message": {"content": [{"toolUse": {"name": "x"}}]}},
        }

        with patch.dict("sys.modules", {"boto3": boto3}), \
             self.assertRaisesRegex(helpers.ProviderAdapterError, "metin içeriği yok"):
            helpers.call_bedrock_converse("model", [{"role": "user", "content": "x"}])


class AnthropicAdapterShapeTest(unittest.TestCase):
    def _response(self, payload):
        response = MagicMock()
        response.read.return_value = __import__("json").dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

    def test_ignores_non_text_content_and_clamps_temperature(self):
        with patch("urllib.request.urlopen", return_value=self._response({
                "content": [
                    {"type": "thinking", "thinking": "hidden"},
                    {"type": "text", "text": "sonuç"},
                ],
            })) as urlopen:
            response = helpers.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}], temperature=9)

        import json
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["temperature"], 1.0)
        self.assertEqual(response.choices[0].message.content, "sonuç")


class SubtitleProjectPathValidationTest(unittest.TestCase):
    def test_rejects_same_named_incomplete_external_package(self):
        with tempfile.TemporaryDirectory() as root:
            external = Path(root) / "wrong-project" / "subtitle_localizer"
            external.mkdir(parents=True)
            (external / "__init__.py").write_text("", encoding="utf-8")

            resolved = ht.resolve_subtitle_project_path(str(external.parent))

        self.assertEqual(Path(resolved), Path(ht.__file__).resolve().parent)


if __name__ == "__main__":
    unittest.main()
