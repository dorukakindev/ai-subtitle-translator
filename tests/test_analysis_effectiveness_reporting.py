import unittest
from types import SimpleNamespace

import hybrid_translate as ht
import subtitle_translator_gui as gui


class AnalysisEffectivenessReportingTest(unittest.TestCase):
    def test_metrics_measure_depth_scene_coverage_and_analysis_outputs(self):
        context = SimpleNamespace(
            recurring_terms={"faith": "inanç", "church": "kilise"},
            characters=[SimpleNamespace(name="Hazel"), SimpleNamespace(name="Enoch")],
            _analysis_degraded=False,
            _analysis_term_conflicts=["faith"],
            _analysis_character_conflicts=["Hazel"],
        )
        scenes = [
            {"start": 1, "end": 2, "referents": {"he": "Hazel"}},
            {"start": 3, "end": 4, "speaker_goals": {"Hazel": "leave"}},
        ]
        result = (
            context, {"Hazel": "example"}, {"Hazel-Enoch": "sen"}, {},
            scenes, {"wise blood": "kötü kan"}, [{"source": "Church"}],
        )
        cues = [(str(i), "00:00:00,000 --> 00:00:01,000", "x")
                for i in range(1, 6)]

        metrics = ht.analysis_effectiveness_metrics(
            result, cues, "Gelişmiş", complete=True)

        self.assertEqual(metrics["depth"], "advanced")
        self.assertEqual(metrics["analysis_chunks"], 1)
        self.assertEqual(metrics["terms"], 2)
        self.assertEqual(metrics["characters"], 2)
        self.assertEqual(metrics["pronoun_pairs"], 1)
        self.assertEqual(metrics["scenes"], 2)
        self.assertEqual(metrics["scene_coverage_pct"], 80.0)
        self.assertEqual(metrics["scene_uncovered_cues"], 1)
        self.assertEqual(metrics["scene_uncovered_ranges"], ["5"])
        self.assertEqual(metrics["referent_scenes"], 1)
        self.assertEqual(metrics["goal_scenes"], 1)
        self.assertEqual(metrics["idioms"], 1)
        self.assertEqual(metrics["cultural_refs"], 1)
        self.assertEqual(metrics["term_conflicts"], ["faith"])
        self.assertEqual(metrics["character_style_conflicts"], ["Hazel"])
        self.assertIn(
            "Analiz verim ozeti [Gelismis]: tamam | 1 analiz chunk",
            ht.analysis_effectiveness_log_line(metrics),
        )
        self.assertIn(
            "prompt disi birakilan catismalar: 1 terim/1 karakter",
            ht.analysis_effectiveness_log_line(metrics),
        )
        self.assertIn(
            "sahne plani disinda 1 cue [5]",
            ht.analysis_effectiveness_log_line(metrics),
        )

    def test_quality_report_includes_comparable_output_load(self):
        lines = gui._quality_feature_audit({
            "helper_analysis": True,
            "analysis_status": "tamam",
            "analysis_metrics": {
                "depth": "maximum", "analysis_chunks": 3, "terms": 67,
                "characters": 7, "pronoun_pairs": 4, "scenes": 144,
                "scene_coverage_pct": 98.5, "referent_scenes": 82,
                "scene_uncovered_cues": 3,
                "scene_uncovered_ranges": ["101-103"],
                "goal_scenes": 43, "idioms": 8, "cultural_refs": 5,
                "term_conflicts": ["faith", "church"],
                "character_style_conflicts": ["Hazel"],
            },
            "pass_trace": {"Critic": 16},
            "pass_fix": 16,
            "warn": 2,
            "hata": 0,
        }, {"hybrid_mode": True})

        self.assertTrue(any(
            "Analiz kapsam ölçümü [Maksimum]" in line
            and "cue kapsamı %98.5" in line for line in lines))
        self.assertIn(
            "Analiz sonrası karşılaştırma ölçümü: Critic 16 düzeltme, "
            "tüm pass'ler 16 değişik cue, 2 nihai uyarı, 0 eksik/hata",
            lines,
        )
        self.assertIn(
            "Analiz çatışmaları (prompt/cache dışında bırakıldı): "
            "terim [faith,church]; karakter üslubu [Hazel]",
            lines,
        )
        self.assertIn(
            "Sahne planı kapsam boşluğu: 3 cue [101-103] — "
            "bu cue'larda genel/canlı bağlam kullanıldı",
            lines,
        )


if __name__ == "__main__":
    unittest.main()
