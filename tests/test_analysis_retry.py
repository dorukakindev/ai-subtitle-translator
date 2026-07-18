import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class AnalyzeWithHelperRetryTest(unittest.TestCase):
    def test_invalid_json_analysis_response_is_retried(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class ContextMemory:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_models.ContextMemory = ContextMemory

        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models

        memory = SimpleNamespace(
            source_language="en",
            summary="ok",
            setting="",
            tone="documentary",
            characters=[],
            recurring_terms={},
            scene_notes=[],
        )
        logs = []

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }):
            with patch.object(ht, "_ensure_path", lambda: None), \
                    patch.object(ht, "_analyze_context_openai_compatible",
                                 side_effect=[RuntimeError("context analysis returned invalid JSON"), memory]) as analyze_mock, \
                    patch.object(ht, "_generate_character_examples", return_value=({}, {})), \
                    patch.object(ht, "_generate_pronoun_map", return_value={}), \
                    patch.object(ht, "_extract_emotional_arc", return_value=[]), \
                    patch.object(ht, "_generate_idiom_map", return_value={}), \
                    patch.object(ht, "_generate_cultural_refs", return_value=[]), \
                    patch.object(ht.time, "sleep", lambda _seconds: None):
                result = ht.analyze_with_helper(
                    cues=[SimpleNamespace(index=1, text="hello")],
                    helper_api_key="key",
                    helper_url="https://147ai.online/v1/messages",
                    helper_model="claude-haiku-4-5-20251001",
                    log_fn=lambda msg, level="info": logs.append((level, msg)),
                )

        self.assertIsNotNone(result)
        self.assertEqual(analyze_mock.call_count, 2)
        self.assertTrue(any("JSON degil" in msg for _level, msg in logs))

    def test_invalid_json_after_retries_uses_fallback_context(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class ContextMemory:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class CharacterVoice:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_models.ContextMemory = ContextMemory
        fake_models.CharacterVoice = CharacterVoice

        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models
        logs = []

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }):
            with patch.object(ht, "_ensure_path", lambda: None), \
                    patch.object(ht, "_analyze_context_openai_compatible",
                                 side_effect=RuntimeError("context analysis returned invalid JSON")) as analyze_mock, \
                    patch.object(ht, "_generate_character_examples", return_value=({}, {})), \
                    patch.object(ht, "_generate_pronoun_map", return_value={}), \
                    patch.object(ht, "_extract_emotional_arc", return_value=[]), \
                    patch.object(ht, "_generate_idiom_map", return_value={}), \
                    patch.object(ht, "_generate_cultural_refs", return_value=[]), \
                    patch.object(ht.time, "sleep", lambda _seconds: None):
                result = ht.analyze_with_helper(
                    cues=[
                        SimpleNamespace(index=1, text="[GEORGE] Hello"),
                        SimpleNamespace(index=2, text="NARRATOR: A documentary line"),
                    ],
                    helper_api_key="key",
                    helper_url="https://147ai.online/v1/messages",
                    helper_model="gpt-5.4-mini",
                    log_fn=lambda msg, level="info": logs.append((level, msg)),
                )

        self.assertIsNotNone(result)
        merged, *_ = result
        self.assertEqual(analyze_mock.call_count, 3)
        self.assertEqual(merged.tone, "fallback")
        self.assertTrue(any("fallback_context" in note for note in merged.scene_notes))
        self.assertTrue(any("guvenli bos baglamla devam" in msg for _level, msg in logs))


if __name__ == "__main__":
    unittest.main()
