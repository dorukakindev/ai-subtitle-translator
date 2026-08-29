import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


class Cue:
    def __init__(self, index: int, text: str = None):
        self.index = index
        self.text = text or f"Line {index}."
        self.start = f"00:00:{index % 50:02d},000"
        self.end = f"00:00:{index % 50:02d},500"


class AnalysisDepthSamplingTest(unittest.TestCase):
    def test_standard_depth_spreads_its_sample_across_the_file(self):
        """Standart artik ilk 250 cue'yu DEGIL, yayilmis 250 cue'yu okur.

        Eski davranis (`first 250`) bir maliyet takasi degildi: derinlik
        farki ORNEK SAYISIDIR (standart 250, gelismis 900, maksimum 550).
        250 cue'yu bastan mi yoksa dosyaya yayarak mi sectigimiz jeton
        maliyetini degistirmez — yani eski davranisin tek gerekcesi
        tarihseldi, ve 2000'lik bir chunk'in %87,5'i analize hic
        girmiyordu.

        Bu test eskiden `keeps_legacy_first_250_sample` adiyla eski
        davranisi kilitliyordu; degistirilmesi bilinclidir.
        """
        cues = [Cue(i) for i in range(1, 2001)]

        sample = ht._analysis_sample_for_depth(cues, "Standart")
        ids = [item["id"] for item in sample]

        self.assertEqual(len(sample), 250)
        self.assertEqual(ids[0], 1)
        self.assertGreater(ids[-1], 1900, "orneklem dosyanin sonunu gormuyor")
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_standard_depth_takes_everything_when_file_is_small(self):
        cues = [Cue(i) for i in range(1, 101)]
        sample = ht._analysis_sample_for_depth(cues, "Standart")
        self.assertEqual(len(sample), 100)

    def test_deeper_depth_samples_start_middle_and_tail(self):
        cues = [Cue(i, f"Regular dialogue line number {i}.") for i in range(1, 1001)]

        sample = ht._analysis_sample_for_depth(cues, "Gelismis")
        ids = [item["id"] for item in sample]

        self.assertIn(1, ids)
        self.assertIn(1000, ids)
        self.assertTrue(any(450 <= cue_id <= 550 for cue_id in ids))


class AnalysisDepthCacheTest(unittest.TestCase):
    def test_cache_is_invalidated_when_expected_depth_differs(self):
        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextMemory:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class CharacterVoice:
            def __init__(self, name, speaking_style):
                self.name = name
                self.speaking_style = speaking_style

        fake_models.ContextMemory = ContextMemory
        fake_models.CharacterVoice = CharacterVoice

        fake_pkg = types.ModuleType("subtitle_localizer")
        fake_pkg.models = fake_models

        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "sample.srt"
            fp.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")
            context = SimpleNamespace(
                source_language="en",
                summary="summary",
                setting="setting",
                tone="tone",
                characters=[SimpleNamespace(name="Alex", speaking_style="casual")],
                recurring_terms={"hello": "merhaba"},
                scene_notes=["note"],
            )

            with patch.object(ht, "_ensure_path", lambda: None):
                ht.save_context_cache(context, str(fp), target_language="tr", analysis_depth="Maksimum")
                with patch.dict(sys.modules, {
                    "subtitle_localizer": fake_pkg,
                    "subtitle_localizer.models": fake_models,
                }):
                    self.assertIsNotNone(
                        ht.load_context_cache(str(fp), expected_target="tr", expected_analysis_depth="Maksimum")
                    )
                    self.assertIsNone(
                        ht.load_context_cache(str(fp), expected_target="tr", expected_analysis_depth="Standart")
                    )


class AnalyzeWithHelperDepthTest(unittest.TestCase):
    def test_maximum_depth_uses_smaller_chunks_and_passes_depth(self):
        fake_models = types.ModuleType("subtitle_localizer.models")

        class ContextAnalysisRequest:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        fake_models.ContextAnalysisRequest = ContextAnalysisRequest
        fake_models.ContextMemory = lambda **kwargs: SimpleNamespace(**kwargs)
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

        with patch.dict(sys.modules, {
            "subtitle_localizer": fake_pkg,
            "subtitle_localizer.models": fake_models,
        }):
            with patch.object(ht, "_ensure_path", lambda: None), \
                    patch.object(ht, "_analyze_context_openai_compatible", return_value=memory) as analyze_mock, \
                    patch.object(ht, "_generate_character_examples", return_value=({}, {})), \
                    patch.object(ht, "_generate_pronoun_map", return_value={}), \
                    patch.object(ht, "_extract_emotional_arc", return_value=[]), \
                    patch.object(ht, "_generate_idiom_map", return_value={}), \
                    patch.object(ht, "_generate_cultural_refs", return_value=[]):
                result = ht.analyze_with_helper(
                    cues=[Cue(i) for i in range(1, 1201)],
                    helper_api_key="key",
                    helper_url="https://api.openai.com/v1",
                    helper_model="gpt-5.4-mini",
                    analysis_depth="Maksimum",
                )

        self.assertIsNotNone(result)
        self.assertEqual(analyze_mock.call_count, 3)
        self.assertEqual(
            sorted(len(call.args[0]) for call in analyze_mock.call_args_list),
            [100, 550, 550],
        )
        self.assertTrue(
            all(call.kwargs["analysis_depth"] == "maximum" for call in analyze_mock.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
