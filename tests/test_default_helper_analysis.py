import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht
from request_cancellation import RequestCancelled


class DefaultHelperAnalysisHardeningTest(unittest.TestCase):
    def test_auxiliary_analysis_preserves_request_cancellation(self):
        cue = SimpleNamespace(text="Source line.", index=1)
        scene_cue = SimpleNamespace(
            text="Source line.", index=1,
            start="00:00:01,000", end="00:00:02,000")
        character = SimpleNamespace(name="Alice", speaking_style="calm")
        context = SimpleNamespace(
            characters=[character, SimpleNamespace(name="Bob", speaking_style="formal")],
            setting="",
            summary="",
        )
        calls = [
            lambda: ht._generate_character_examples(
                [character], "Turkish", "key", "https://example.test/v1", "gpt-5.4"),
            lambda: ht._generate_pronoun_map(
                context, "Turkish", "key", "https://example.test/v1", "gpt-5.4"),
            lambda: ht._generate_idiom_map(
                [cue], "Turkish", "key", "https://example.test/v1", "gpt-5.4"),
            lambda: ht._generate_cultural_refs(
                [cue], {"name": "Film"}, "Turkish",
                "key", "https://example.test/v1", "gpt-5.4"),
            lambda: ht._extract_emotional_arc(
                [scene_cue], "Turkish", "key",
                "https://example.test/v1", "gpt-5.4"),
        ]
        with patch("openai.OpenAI"), patch.object(
                ht, "_safe_chat_create", side_effect=RequestCancelled("stopped")):
            for call in calls:
                with self.subTest(call=call):
                    with self.assertRaises(RequestCancelled):
                        call()

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

    def test_character_and_pronoun_auxiliary_data_is_bound_to_known_characters(self):
        characters = [
            SimpleNamespace(name="Alice", speaking_style="calm"),
            SimpleNamespace(name="Bob", speaking_style="formal"),
        ]
        examples_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "examples": {
                    "alice": ["Merhaba."],
                    "Ghost": ["Ben yokum."],
                },
                "styles": {
                    "Alice": {"register": "neutral", "dialect": "standard"},
                    "Ghost": {"register": "street", "dialect": "urban_slang"},
                },
            })))],
        )
        pronoun_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "pronoun_map": {
                    "alice-bob": "sen",
                    "Ghost-Bob": "siz",
                },
            })))],
        )
        context = SimpleNamespace(
            characters=characters,
            setting="",
            summary="",
        )

        with patch("openai.OpenAI"), \
             patch.object(
                 ht, "_safe_chat_create",
                 side_effect=[examples_response, pronoun_response],
             ):
            examples, styles = ht._generate_character_examples(
                characters, "Turkish", "key", "https://example.test/v1", "gpt-5.4")
            pronouns = ht._generate_pronoun_map(
                context, "Turkish", "key", "https://example.test/v1", "gpt-5.4")

        self.assertEqual(examples, {"Alice": ["Merhaba."]})
        self.assertEqual(
            styles,
            {"Alice": {"register": "neutral", "dialect": "standard"}},
        )
        self.assertEqual(pronouns, {"Alice-Bob": "sen"})

    def test_auxiliary_maps_keep_turkish_dotted_character_names(self):
        characters = [
            SimpleNamespace(name="İpek", speaking_style="formal"),
            SimpleNamespace(name="Ali", speaking_style="neutral"),
        ]
        context = SimpleNamespace(characters=characters, setting="", summary="")
        examples_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "examples": {"ipek": ["Merhaba."]},
                "styles": {"ipek": {"register": "formal", "dialect": "standard"}},
            })))],
        )
        pronoun_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "pronoun_map": {"ipek-ali": "siz"},
            })))],
        )

        with patch("openai.OpenAI"), patch.object(
                ht, "_safe_chat_create",
                side_effect=[examples_response, pronoun_response]):
            examples, styles = ht._generate_character_examples(
                characters, "Turkish", "key", "https://example.test/v1", "gpt-5.4")
            pronouns = ht._generate_pronoun_map(
                context, "Turkish", "key", "https://example.test/v1", "gpt-5.4")

        self.assertEqual(examples, {"İpek": ["Merhaba."]})
        self.assertEqual(
            styles, {"İpek": {"register": "formal", "dialect": "standard"}})
        self.assertEqual(pronouns, {"İpek-Ali": "siz"})

    def test_idiom_and_cultural_refs_must_exist_in_source_text(self):
        cues = [
            SimpleNamespace(
                text="He will spill the beans after the Yankees game.",
                index=1,
            )
        ]
        idiom_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "idioms": {
                    "spill the beans": "ağzındaki baklayı çıkarmak",
                    "kick the bucket": "nalları dikmek",
                },
            })))],
        )
        refs_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "refs": [
                    {"src": "Yankees", "action": "keep"},
                    {"src": "White House", "action": "localize",
                     "target": "Beyaz Saray"},
                ],
            })))],
        )

        with patch("openai.OpenAI"), \
             patch.object(
                 ht, "_safe_chat_create",
                 side_effect=[idiom_response, refs_response],
             ):
            idioms = ht._generate_idiom_map(
                cues, "Turkish", "key", "https://example.test/v1", "gpt-5.4")
            refs = ht._generate_cultural_refs(
                cues, {"name": "Film"}, "Turkish",
                "key", "https://example.test/v1", "gpt-5.4")

        self.assertEqual(
            idioms,
            {"spill the beans": "ağzındaki baklayı çıkarmak"},
        )
        self.assertEqual(refs, [{"src": "Yankees", "action": "keep"}])

    def test_long_file_analysis_samples_include_final_cue(self):
        idiom_cues = [
            SimpleNamespace(text=f"Ordinary line {i}.", index=i)
            for i in range(1, 301)
        ]
        idiom_cues.append(
            SimpleNamespace(text="At last, spill the beans.", index=301))
        ref_cues = [
            SimpleNamespace(text=f"Ordinary line {i}.", index=i)
            for i in range(1, 201)
        ]
        ref_cues.append(
            SimpleNamespace(text="The White House responded.", index=201))
        idiom_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "idioms": {"spill the beans": "ağzındaki baklayı çıkar"},
            })))],
        )
        refs_response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "refs": [{
                    "src": "White House", "action": "localize",
                    "target": "Beyaz Saray",
                }],
            })))],
        )

        with patch("openai.OpenAI"), \
             patch.object(
                 ht, "_safe_chat_create",
                 side_effect=[idiom_response, refs_response],
             ) as chat:
            idioms = ht._generate_idiom_map(
                idiom_cues, "Turkish", "key",
                "https://example.test/v1", "gpt-5.4")
            refs = ht._generate_cultural_refs(
                ref_cues, {"name": "Film"}, "Turkish",
                "key", "https://example.test/v1", "gpt-5.4")

        self.assertEqual(
            idioms, {"spill the beans": "ağzındaki baklayı çıkar"})
        self.assertEqual(
            refs, [{
                "src": "White House", "action": "localize",
                "target": "Beyaz Saray",
            }])
        self.assertIn(
            "spill the beans",
            chat.call_args_list[0].kwargs["messages"][0]["content"])
        self.assertIn(
            "White House",
            chat.call_args_list[1].kwargs["messages"][0]["content"])

    def test_main_analysis_recurring_terms_must_exist_in_source_text(self):
        cues = [
            SimpleNamespace(
                text="The Osprey landed safely.",
                index=1,
            )
        ]
        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "source_language": "en",
                "summary": "An aircraft lands.",
                "setting": "airfield",
                "tone": "calm",
                "characters": [],
                "recurring_terms": {
                    "Osprey": "Osprey",
                    "Black Hawk": "Kara Şahin",
                },
                "scene_notes": [],
            })))],
        )

        with patch("openai.OpenAI"), \
             patch.object(ht, "_safe_chat_create", return_value=response):
            memory = ht._analyze_context_openai_compatible(
                cues,
                api_key="key",
                api_url="https://example.test/v1",
                model="gpt-5.4",
                glossary={},
                style="natural",
                source_language="en",
                target_language="tr",
            )

        self.assertEqual(memory.recurring_terms, {"Osprey": "Osprey"})

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
