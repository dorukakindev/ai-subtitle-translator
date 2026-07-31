import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht


class NativeSceneFragmentGuardTest(unittest.TestCase):
    def test_scene_gap_does_not_create_cross_scene_fragment_group(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bunu yapacağım"),
            ("2", "00:00:08,000 --> 00:00:09,000", "başka bir sahnede."),
        ]
        source = {"1": "I will do this", "2": "in another scene."}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))], usage=None)
        client = MagicMock()
        with patch("openai.OpenAI", return_value=client), patch.object(
                ht, "_safe_chat_create", return_value=response) as create:
            ht.native_reader_pass(blocks, "key", src_map=source)

        prompt = create.call_args.kwargs["messages"][0]["content"]
        payload = json.loads(prompt.split("Altyazılar:\n", 1)[1].split("\n\nJSON array", 1)[0])
        self.assertNotIn("frag", payload["tr"][0])
        self.assertNotIn("frag", payload["tr"][1])

    def test_scene_gap_does_not_leak_lookahead_into_previous_chunk(self):
        blocks = []
        for i in range(1, 151):
            blocks.append((str(i), f"00:00:{i:02d},000 --> 00:00:{i:02d},500", "Tamam."))
        blocks.append(("151", "00:03:00,000 --> 00:03:01,000", "Yeni sahne."))
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))], usage=None)
        client = MagicMock()
        with patch("openai.OpenAI", return_value=client), patch.object(
                ht, "_safe_chat_create", return_value=response) as create:
            ht.native_reader_pass(blocks, "key")

        first_prompt = create.call_args_list[0].kwargs["messages"][0]["content"]
        first_payload = json.loads(first_prompt.split("Altyazılar:\n", 1)[1].split("\n\nJSON array", 1)[0])
        self.assertNotIn("next_ctx", first_payload)


if __name__ == "__main__":
    unittest.main()
