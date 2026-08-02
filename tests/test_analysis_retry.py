import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class AnalyzeWithHelperRetryTest(unittest.TestCase):
    def test_conflicting_chunk_terms_are_dropped_and_not_cacheable(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextMemory:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextMemory = ContextMemory
        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models
        memories = [
            SimpleNamespace(
                source_language="en", summary="one", setting="", tone="",
                characters=[], recurring_terms={"The Order": "Tarikat"},
                scene_notes=[]),
            SimpleNamespace(
                source_language="en", summary="two", setting="", tone="",
                characters=[], recurring_terms={"the order": "Düzen"},
                scene_notes=[]),
        ]
        logs = []

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }), patch.object(ht, "_ensure_path", lambda: None):
            merged = ht._merge_memories(
                memories, target_language="tr",
                log_fn=lambda message, level="info": logs.append((level, message)))

        self.assertEqual(merged.recurring_terms, {})
        self.assertTrue(getattr(merged, "_analysis_degraded", False))
        self.assertTrue(any("The Order" in message for _level, message in logs))

    def test_failed_auxiliary_component_is_retried_once(self):
        import hybrid_translate as ht

        status = {}
        calls = []

        def call():
            calls.append(True)
            status["scene_plan"] = len(calls) > 1
            return ["recovered"] if status["scene_plan"] else []

        result = ht._retry_failed_analysis_aux(
            "scene_plan", "Sahne planı", status, None, call)

        self.assertEqual(result, ["recovered"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(status["scene_plan"])

    def test_stop_before_analysis_prevents_any_helper_request(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }), patch.object(ht, "_ensure_path", lambda: None), \
             patch.object(ht, "_analyze_context_openai_compatible") as analyze:
            result = ht.analyze_with_helper(
                cues=[SimpleNamespace(index=i, text=f"line {i}") for i in range(5)],
                helper_api_key="key",
                chunk_size=1,
                max_workers=2,
                stop_flag_fn=lambda: True,
            )

        self.assertIsNone(result)
        analyze.assert_not_called()

    def test_auxiliary_failure_marks_analysis_degraded(self):
        import hybrid_translate as ht

        memory = SimpleNamespace(
            source_language="en", summary="ok", setting="", tone="documentary",
            characters=[], recurring_terms={}, scene_notes=[],
        )

        def ok_value(value, key):
            def _call(*_args, status=None, **_kwargs):
                status[key] = True
                return value
            return _call

        def failed_idioms(*_args, status=None, **_kwargs):
            status["idiom_map"] = False
            return {}

        with patch.object(ht, "_analyze_context_openai_compatible",
                          return_value=memory), \
             patch.object(ht, "_generate_character_examples",
                          side_effect=ok_value(({}, {}), "character_examples")), \
             patch.object(ht, "_generate_pronoun_map",
                          side_effect=ok_value({}, "pronoun_map")), \
             patch.object(ht, "_extract_emotional_arc",
                          side_effect=ok_value([], "scene_plan")), \
             patch.object(ht, "_generate_idiom_map", side_effect=failed_idioms), \
             patch.object(ht, "_generate_cultural_refs",
                          side_effect=ok_value([], "cultural_refs")):
            result = ht.analyze_with_helper(
                cues=[SimpleNamespace(index=1, text="hello")],
                helper_api_key="key",
            )

        self.assertTrue(ht.analysis_result_is_degraded(result))

    def test_truncated_analysis_json_is_salvaged_only_as_degraded(self):
        import hybrid_translate as ht

        response = SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=(
                '{"source_language":"en","summary":"Plot",'
                '"setting":"Room","tone":"tense","characters":['
            )))],
        )
        with patch("openai.OpenAI"), \
             patch.object(ht, "_safe_chat_create", return_value=response):
            memory = ht._analyze_context_openai_compatible(
                [SimpleNamespace(index=1, text="Hello")],
                api_key="key", api_url="https://example.test/v1",
                model="gpt-5.4", glossary={}, style="natural",
                source_language="en", target_language="tr",
                allow_partial=True,
            )

        self.assertEqual(memory.summary, "Plot")
        self.assertTrue(getattr(memory, "_analysis_degraded", False))

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

    def test_provider_503_is_not_retried_again_above_central_retry_layer(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class TemporaryError(RuntimeError):
            status_code = 503

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }), patch.object(ht, "_ensure_path", lambda: None), \
             patch.object(
                 ht, "_analyze_context_openai_compatible",
                 side_effect=TemporaryError("temporarily unavailable"),
             ) as analyze_mock, patch.object(ht.time, "sleep") as sleep_mock:
            result = ht.analyze_with_helper(
                cues=[SimpleNamespace(index=1, text="hello")],
                helper_api_key="key",
                helper_url="https://reseller.example/v1",
                helper_model="gpt-5.4",
            )

        self.assertIsNone(result)
        self.assertEqual(analyze_mock.call_count, 1)
        sleep_mock.assert_not_called()

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
        self.assertTrue(ht.analysis_result_is_degraded(result))
        self.assertTrue(any("fallback_context" in note for note in merged.scene_notes))
        self.assertTrue(any("guvenli bos baglamla devam" in msg for _level, msg in logs))

    def test_stop_after_main_analysis_prevents_remaining_helper_calls(self):
        import hybrid_translate as ht

        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_models.ContextMemory = SimpleNamespace
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
        stopped = {"value": False}

        def finish_character_step(*_args, **_kwargs):
            stopped["value"] = True
            return {}, {}

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }), patch.object(ht, "_ensure_path", lambda: None), \
             patch.object(ht, "_analyze_context_openai_compatible", return_value=memory), \
             patch.object(ht, "_generate_character_examples",
                          side_effect=finish_character_step), \
             patch.object(ht, "_generate_pronoun_map") as pronoun:
            result = ht.analyze_with_helper(
                cues=[SimpleNamespace(index=1, text="hello")],
                helper_api_key="key",
                stop_flag_fn=lambda: stopped["value"],
            )

        self.assertIsNone(result)
        pronoun.assert_not_called()


if __name__ == "__main__":
    unittest.main()
