"""Semantik sahne planı — eski tek-satırlık "duygusal yay" (arc) yerine her sahne için
summary/speakers/speaker_goals/referents/tone çıkaran zenginleştirilmiş bağlam.

Kapsam:
- _sanitize_scene_plan_entry: LLM'den dönen ham JSON'u güvenli/sınırlı şekle sokan
  saf fonksiyon (ağ çağrısı yok, testable).
- _scene_plan_payload_entry: sahne planını payload'a enjekte edilecek kompakt hâle
  getiren saf fonksiyon (start/end'i düşürür, boş alanları atar, eski 'arc'ı 'tone'a
  düşürür — geriye dönük uyumluluk).
- _scene_context_for_chunk: bir chunk'la örtüşen TÜM sahneleri döndürür (eskiden
  yalnız ilki dönüyordu — chunk 2 sahneye yayılınca ikincisi sessizce kayboluyordu).
- _scene_plan_cache_is_stale: eski-şekilli (yalnız 'arc') önbellek girdilerini tespit
  edip zorla yeniden-analiz tetikler.
"""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht


def _fake_subtitle_localizer_models():
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
    return fake_pkg, fake_models


class SanitizeScenePlanEntryTest(unittest.TestCase):
    def test_valid_entry_passes_through(self):
        raw = {
            "start": 5, "end": 12, "summary": "Mike explains the device to a customer.",
            "speakers": ["Mike", "Customer"],
            "speaker_goals": {"Mike": "sell the device", "Customer": "verify it's real"},
            "referents": {"it": "the medical device", "this": "the metal attachment"},
            "tone": "playful but explanatory",
        }
        entry = ht._sanitize_scene_plan_entry(raw)
        self.assertEqual(entry["start"], 5)
        self.assertEqual(entry["end"], 12)
        self.assertEqual(entry["summary"], "Mike explains the device to a customer.")
        self.assertEqual(entry["speakers"], ["Mike", "Customer"])
        self.assertEqual(entry["speaker_goals"]["Mike"], "sell the device")
        self.assertEqual(entry["referents"]["it"], "the medical device")
        self.assertEqual(entry["tone"], "playful but explanatory")

    def test_string_start_end_coerced(self):
        entry = ht._sanitize_scene_plan_entry({"start": "5", "end": "12", "summary": "x"})
        self.assertEqual(entry["start"], 5)
        self.assertEqual(entry["end"], 12)

    def test_missing_start_or_end_returns_none(self):
        self.assertIsNone(ht._sanitize_scene_plan_entry({"end": 12, "summary": "x"}))
        self.assertIsNone(ht._sanitize_scene_plan_entry({"start": 5, "summary": "x"}))

    def test_non_dict_returns_none(self):
        self.assertIsNone(ht._sanitize_scene_plan_entry("not a dict"))
        self.assertIsNone(ht._sanitize_scene_plan_entry(None))
        self.assertIsNone(ht._sanitize_scene_plan_entry([1, 2, 3]))

    def test_malformed_field_types_degrade_gracefully(self):
        # speakers bir string (liste değil), referents bir liste (dict değil) — patlamamalı.
        entry = ht._sanitize_scene_plan_entry({
            "start": 1, "end": 2, "speakers": "Mike", "referents": ["it"], "speaker_goals": "goal",
        })
        self.assertEqual(entry["speakers"], [])
        self.assertEqual(entry["referents"], {})
        self.assertEqual(entry["speaker_goals"], {})

    def test_fields_are_length_bounded(self):
        entry = ht._sanitize_scene_plan_entry({
            "start": 1, "end": 2,
            "summary": "x" * 5000,
            "speakers": [f"Speaker{i}" for i in range(50)],
            "speaker_goals": {f"S{i}": "y" * 5000 for i in range(50)},
            "referents": {f"r{i}": "z" * 5000 for i in range(50)},
            "tone": "t" * 5000,
        })
        self.assertLessEqual(len(entry["summary"]), 220)
        self.assertLessEqual(len(entry["tone"]), 120)
        self.assertLessEqual(len(entry["speakers"]), 6)
        self.assertLessEqual(len(entry["speaker_goals"]), 6)
        self.assertLessEqual(len(entry["referents"]), 8)
        for v in entry["speaker_goals"].values():
            self.assertLessEqual(len(v), 100)
        for v in entry["referents"].values():
            self.assertLessEqual(len(v), 100)

    def test_empty_optional_fields_default_safely(self):
        entry = ht._sanitize_scene_plan_entry({"start": 1, "end": 2})
        self.assertEqual(entry["summary"], "")
        self.assertEqual(entry["speakers"], [])
        self.assertEqual(entry["speaker_goals"], {})
        self.assertEqual(entry["referents"], {})
        self.assertEqual(entry["tone"], "")


class ScenePlanPayloadEntryTest(unittest.TestCase):
    def test_drops_start_end_bookkeeping(self):
        entry = ht._scene_plan_payload_entry({
            "start": 1, "end": 2, "summary": "x", "tone": "y",
        })
        self.assertNotIn("start", entry)
        self.assertNotIn("end", entry)
        self.assertEqual(entry["summary"], "x")
        self.assertEqual(entry["tone"], "y")

    def test_drops_empty_fields(self):
        entry = ht._scene_plan_payload_entry({
            "start": 1, "end": 2, "summary": "x",
            "speakers": [], "speaker_goals": {}, "referents": {}, "tone": "",
        })
        self.assertEqual(entry, {"summary": "x"})

    def test_legacy_arc_falls_back_to_tone_when_tone_absent(self):
        entry = ht._scene_plan_payload_entry({
            "start": 1, "end": 2, "arc": "tension rising",
        })
        self.assertEqual(entry, {"tone": "tension rising"})

    def test_tone_present_wins_over_legacy_arc(self):
        entry = ht._scene_plan_payload_entry({
            "start": 1, "end": 2, "tone": "calm", "arc": "tension rising",
        })
        self.assertEqual(entry["tone"], "calm")

    def test_all_fields_empty_returns_none(self):
        self.assertIsNone(ht._scene_plan_payload_entry({"start": 1, "end": 2}))
        self.assertIsNone(ht._scene_plan_payload_entry({}))

    def test_non_dict_returns_none(self):
        self.assertIsNone(ht._scene_plan_payload_entry("nope"))
        self.assertIsNone(ht._scene_plan_payload_entry(None))


class SceneContextForChunkMultiSceneTest(unittest.TestCase):
    def test_returns_all_overlapping_scenes_not_just_first(self):
        # Chunk #8-#14 iki sahneye yayılıyor: sahne A (#5-#10) ve sahne B (#11-#16).
        # Eski davranış yalnız İLK örtüşen sahneyi (A) döndürüp B'yi sessizce
        # kaybediyordu — bu tam da bu özelliğin çözdüğü problem.
        scene_emotions = [
            {"start": 5, "end": 10, "summary": "Scene A", "tone": "calm"},
            {"start": 11, "end": 16, "summary": "Scene B", "tone": "tense"},
        ]
        result = ht._scene_context_for_chunk(scene_emotions, 8, 14)
        self.assertEqual(len(result), 2)
        self.assertEqual({e["summary"] for e in result}, {"Scene A", "Scene B"})

    def test_single_scene_overlap_returns_one(self):
        scene_emotions = [
            {"start": 1, "end": 5, "summary": "Scene A"},
            {"start": 20, "end": 25, "summary": "Scene Z"},
        ]
        result = ht._scene_context_for_chunk(scene_emotions, 2, 4)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["summary"], "Scene A")

    def test_no_overlap_returns_empty_list(self):
        scene_emotions = [{"start": 1, "end": 5, "summary": "Scene A"}]
        self.assertEqual(ht._scene_context_for_chunk(scene_emotions, 100, 105), [])

    def test_empty_scene_emotions_returns_empty_list(self):
        self.assertEqual(ht._scene_context_for_chunk([], 1, 5), [])
        self.assertEqual(ht._scene_context_for_chunk(None, 1, 5), [])

    def test_string_chunk_indices_do_not_crash(self):
        # gui.py'nin sync akışında chunk cue index'leri string olabilir
        # (ör. "8") — regresyon: _scene_context_for_chunk_gui kopyası
        # kaldırılırken bu int-coercion kaybolmuştu, burada geri eklendi.
        scene_emotions = [{"start": "5", "end": "10", "summary": "Scene A"}]
        result = ht._scene_context_for_chunk(scene_emotions, "8", "9")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["summary"], "Scene A")

    def test_legacy_shape_scene_still_yields_tone(self):
        scene_emotions = [{"start": 1, "end": 5, "arc": "growing frustration"}]
        result = ht._scene_context_for_chunk(scene_emotions, 2, 3)
        self.assertEqual(result, [{"tone": "growing frustration"}])


class ScenePlanCacheStaleDetectionTest(unittest.TestCase):
    def test_old_arc_only_shape_is_stale(self):
        self.assertTrue(ht._scene_plan_cache_is_stale(
            [{"start": 1, "end": 5, "arc": "tension rising"}]))

    def test_new_shape_with_summary_is_not_stale(self):
        self.assertFalse(ht._scene_plan_cache_is_stale(
            [{"start": 1, "end": 5, "summary": "x", "tone": "calm"}]))

    def test_empty_list_is_not_stale(self):
        self.assertFalse(ht._scene_plan_cache_is_stale([]))
        self.assertFalse(ht._scene_plan_cache_is_stale(None))

    def test_mixed_shapes_not_stale_if_any_has_summary(self):
        self.assertFalse(ht._scene_plan_cache_is_stale([
            {"start": 1, "end": 5, "arc": "old one"},
            {"start": 6, "end": 10, "summary": "new one"},
        ]))


class LoadContextCacheStaleSceneShapeTest(unittest.TestCase):
    def _context(self):
        return SimpleNamespace(
            source_language="en", summary="s", setting="set", tone="t",
            characters=[SimpleNamespace(name="Alex", speaking_style="casual")],
            recurring_terms={}, scene_notes=[],
        )

    def test_old_shape_scene_emotions_loaded_as_empty(self):
        fake_pkg, fake_models = _fake_subtitle_localizer_models()
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "sample.srt"
            fp.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")
            with patch.object(ht, "_ensure_path", lambda: None):
                ht.save_context_cache(
                    self._context(), str(fp), target_language="tr",
                    scene_emotions=[{"start": 1, "end": 5, "arc": "tension rising"}],
                )
                with patch.dict(sys.modules, {
                    "subtitle_localizer": fake_pkg, "subtitle_localizer.models": fake_models,
                }):
                    cached = ht.load_context_cache(str(fp), expected_target="tr")
                    self.assertIsNotNone(cached)
                    self.assertEqual(cached[4], [])  # scene_emotions position — stale shape wiped

    def test_new_shape_scene_emotions_survives_round_trip(self):
        fake_pkg, fake_models = _fake_subtitle_localizer_models()
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "sample.srt"
            fp.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")
            scenes = [{"start": 1, "end": 5, "summary": "Mike explains.", "tone": "calm"}]
            with patch.object(ht, "_ensure_path", lambda: None):
                ht.save_context_cache(
                    self._context(), str(fp), target_language="tr", scene_emotions=scenes,
                )
                with patch.dict(sys.modules, {
                    "subtitle_localizer": fake_pkg, "subtitle_localizer.models": fake_models,
                }):
                    cached = ht.load_context_cache(str(fp), expected_target="tr")
                    self.assertEqual(cached[4], scenes)


if __name__ == "__main__":
    unittest.main()
