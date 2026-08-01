import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import hybrid_translate as ht


class NativeSceneFragmentGuardTest(unittest.TestCase):
    def test_fragment_group_crossing_chunk_boundary_is_kept_together(self):
        blocks = [
            (str(i), f"00:00:{i:02d},000 --> 00:00:{i:02d},500", f"Satır {i}.")
            for i in range(1, 152)
        ]
        source = {str(i): f"Standalone {i}." for i in range(1, 152)}
        source.update({
            "149": "A sentence that",
            "150": "continues across",
            "151": "the boundary.",
        })
        calls = []

        def create(_client, **kwargs):
            prompt = kwargs["messages"][0]["content"]
            payload, _ = json.JSONDecoder().raw_decode(
                prompt.split("Altyazılar:\n", 1)[1])
            ids = {item["id"] for item in payload["tr"]}
            calls.append(ids)
            fixes = [
                {"id": sid, "fixed": f"Düzeltilmiş {sid}."}
                for sid in ("149", "150", "151") if sid in ids
            ]
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(fixes)))],
                usage=None,
            )

        client = MagicMock()
        with patch("openai.OpenAI", return_value=client), \
             patch.object(ht, "_safe_chat_create", side_effect=create), \
             patch.object(ht, "validate_polish_candidate", return_value=(True, "")), \
             patch.object(ht, "_verify_native_candidates",
                          return_value={"149", "150", "151"}):
            result = ht.native_reader_pass(
                blocks, "key", src_map=source)

        containing = [ids for ids in calls if ids & {"149", "150", "151"}]
        self.assertEqual(len(containing), 1)
        self.assertTrue({"149", "150", "151"}.issubset(containing[0]))
        self.assertEqual([result[i - 1][2] for i in (149, 150, 151)], [
            "Düzeltilmiş 149.", "Düzeltilmiş 150.", "Düzeltilmiş 151.",
        ])

    def test_scene_plan_is_attached_to_matching_cue(self):
        blocks = [("7", "00:00:01,000 --> 00:00:02,000", "Onu geri ver.")]
        source = {"7": "Give it back."}
        context = SimpleNamespace(
            tone="tense", setting="room", summary="An argument.", characters=[])
        analysis = (
            context, {}, {}, {},
            [{"start": 5, "end": 9, "summary": "Ayla demands the key back.",
              "speakers": ["Ayla"], "speaker_goals": {"Ayla": "recover the key"},
              "referents": {"it": "the key"}, "tone": "angry"}],
            {}, [],
        )
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))], usage=None)
        client = MagicMock()
        with patch("openai.OpenAI", return_value=client), patch.object(
                ht, "_safe_chat_create", return_value=response) as create:
            ht.native_reader_pass(
                blocks, "key", src_map=source, analysis_result=analysis)

        prompt = create.call_args.kwargs["messages"][0]["content"]
        payload = json.loads(prompt.split("Altyazılar:\n", 1)[1].split("\n\nJSON array", 1)[0])
        self.assertEqual(payload["tr"][0]["scene"][0]["referents"]["it"], "the key")

    def test_scene_gap_does_not_create_cross_scene_fragment_group(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Bunu yapacağım"),
            ("2", "00:00:04,000 --> 00:00:05,000", "başka bir sahnede."),
        ]
        source = {"1": "I will do this", "2": "in another scene."}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))], usage=None)
        client = MagicMock()
        with patch("openai.OpenAI", return_value=client), patch.object(
                ht, "_safe_chat_create", return_value=response) as create:
            ht.native_reader_pass(
                blocks, "key", src_map=source, scene_gap_sec=1.0)

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
