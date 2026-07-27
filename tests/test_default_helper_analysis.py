import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class DefaultHelperAnalysisHardeningTest(unittest.TestCase):
    def test_auxiliary_shapes_are_sanitized(self):
        examples, pronouns, styles, idioms, refs = ht._sanitize_analysis_aux(
            character_examples={"A": ["Bir.", 3], "bad": "not-a-list"},
            pronoun_map={"A-B": "SİZ", "X-Y": "maybe"},
            character_styles={
                "A": {"register": "street", "dialect": "urban_slang"},
                "B": "street",
            },
            idiom_map={"spill the beans": "ağzındaki baklayı çıkar", "bad": None},
            cultural_refs=[
                {"src": "White House", "action": "localize", "target": "Beyaz Saray"},
                {"action": "keep"},
                {"src": "Yankees", "action": "localize"},
            ],
        )

        self.assertEqual(examples, {"A": ["Bir."]})
        self.assertEqual(pronouns, {"A-B": "siz"})
        self.assertEqual(
            styles,
            {"A": {"register": "street", "dialect": "urban_slang"}},
        )
        self.assertEqual(idioms, {"spill the beans": "ağzındaki baklayı çıkar"})
        self.assertEqual(
            refs,
            [{"src": "White House", "action": "localize", "target": "Beyaz Saray"}],
        )

    def test_prompt_builder_fails_closed_on_malformed_auxiliary_data(self):
        context = SimpleNamespace(
            tone="documentary",
            summary="",
            setting="",
            characters=[SimpleNamespace(name="A", speaking_style="calm")],
            scene_notes=[],
        )

        prompt = ht.build_system_prompt(
            context,
            "Italian",
            "Turkish",
            character_examples=["bad"],
            pronoun_map=["sen"],
            character_styles={"A": "street"},
            cultural_refs=[{"action": "keep"}],
        )

        self.assertIn("Italian", prompt)
        self.assertNotIn("Sample line", prompt)

    def test_malformed_signed_cache_auxiliary_data_is_sanitized(self):
        with tempfile.TemporaryDirectory() as root:
            fp = Path(root, "sample.srt")
            fp.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
            context = SimpleNamespace(
                source_language="en",
                summary="summary",
                setting="",
                tone="documentary",
                characters=[],
                recurring_terms={},
                scene_notes=[],
            )
            ht.save_context_cache(context, str(fp), target_language="tr")
            cache_path = ht._cache_path(str(fp))
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            data.update({
                "character_examples": ["bad"],
                "pronoun_map": ["bad"],
                "character_styles": {"A": "street"},
                "idiom_map": ["bad"],
                "cultural_refs": [{"action": "keep"}],
            })
            cache_path.write_text(json.dumps(data), encoding="utf-8")

            loaded = ht.load_context_cache(str(fp), expected_target="tr")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded[1], {})
        self.assertEqual(loaded[2], {})
        self.assertEqual(loaded[3], {})
        self.assertEqual(loaded[5], {})
        self.assertEqual(loaded[6], [])

    def test_idiom_prompt_uses_actual_source_language(self):
        cue = SimpleNamespace(text="Non vedo l'ora.", index=1)
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"idioms": {}}'))],
        )
        with patch("openai.OpenAI"), \
             patch.object(ht, "_safe_chat_create", return_value=response) as chat:
            result = ht._generate_idiom_map(
                [cue], "Turkish", "key", "https://example.test/v1", "gpt-5.4",
                source_language="Italian",
            )

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertEqual(result, {})
        self.assertIn("source language (Italian)", prompt)
        self.assertNotIn("English idiomatic expressions", prompt)

    def test_cultural_reference_prompt_forbids_factual_substitution(self):
        cue = SimpleNamespace(text="The Yankees won.", index=1)
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"refs": []}'))],
        )
        with patch("openai.OpenAI"), \
             patch.object(ht, "_safe_chat_create", return_value=response) as chat:
            result = ht._generate_cultural_refs(
                [cue], {"name": "Documentary"}, "Turkish",
                "key", "https://example.test/v1", "gpt-5.4",
            )

        prompt = chat.call_args.kwargs["messages"][0]["content"]
        self.assertEqual(result, [])
        self.assertIn("Never replace a real person, place, institution, team", prompt)
        self.assertIn("Default: keep", prompt)
        self.assertNotIn("US baseball team", prompt)

    def test_auxiliary_usage_is_reported(self):
        seen = []
        response = SimpleNamespace(
            usage=SimpleNamespace(
                total_tokens=321,
                prompt_tokens_details=SimpleNamespace(cached_tokens=12),
            )
        )

        ht._report_helper_usage(
            response, lambda total, cached=0: seen.append((total, cached))
        )

        self.assertEqual(seen, [(321, 12)])


if __name__ == "__main__":
    unittest.main()
