# -*- coding: utf-8 -*-
"""Boş sahne kaydı "kapsandı" sayılmasın.

Yalnız `start/end` taşıyan bir sahne kaydı modele HİÇBİR ŞEY göndermiyor:
`_scene_plan_payload_entry` onu atıyor (bu davranış doğru ve
`tests/test_scene_plan.py` ile kilitli). Buna karşılık kapsam metriği
ham aralıktan sayıyordu, dolayısıyla o cue'lar sahne bağlamı almadığı
hâlde koşu logu "cue kapsami %100.0" diyebiliyordu.

Kararı artık payload üreticisinin kendisi veriyor; iki taraf ayrışamaz.
"""
import unittest

import hybrid_translate as ht


class Ctx:
    pass


def _metrics(scenes, cue_count=10):
    cues = [(i, "", "x") for i in range(1, cue_count + 1)]
    result = (Ctx(), {}, {}, None, scenes, {}, [])
    return ht.analysis_effectiveness_metrics(result, cues, "standart")


class EmptySceneCoverageTest(unittest.TestCase):
    def test_empty_scene_does_not_count_as_covered(self):
        m = _metrics([
            {"start": 1, "end": 5, "summary": "", "speakers": [],
             "referents": {}},
            {"start": 6, "end": 10, "summary": "Kapalı oda", "tone": "gergin"},
        ])
        self.assertEqual(m["scenes"], 2)
        self.assertEqual(m["empty_scenes"], 1)
        self.assertEqual(m["scene_raw_covered_cues"], 10)
        self.assertEqual(m["scene_covered_cues"], 5)
        self.assertEqual(m["scene_coverage_pct"], 50.0)
        self.assertEqual(m["scene_uncovered_ranges"], ["1-5"])

    def test_scene_with_only_speakers_still_counts(self):
        m = _metrics([{"start": 1, "end": 10, "speakers": ["Ali"]}])
        self.assertEqual(m["empty_scenes"], 0)
        self.assertEqual(m["scene_covered_cues"], 10)

    def test_full_content_still_reports_full_coverage(self):
        m = _metrics([{"start": 1, "end": 10, "summary": "Tümü",
                       "tone": "sakin"}])
        self.assertEqual(m["empty_scenes"], 0)
        self.assertEqual(m["scene_coverage_pct"], 100.0)

    def test_metric_agrees_with_the_payload_builder(self):
        # Ayrisma bir daha olmasin: metrik ile payload ureticisi ayni
        # kayitlar icin ayni karari vermeli.
        scenes = [
            {"start": 1, "end": 3},
            {"start": 4, "end": 6, "arc": "eski surum tonu"},
            {"start": 7, "end": 10, "summary": "  "},
        ]
        m = _metrics(scenes)
        dropped = sum(1 for s in scenes
                      if ht._scene_plan_payload_entry(s) is None)
        self.assertEqual(m["empty_scenes"], dropped)

    def test_log_line_names_the_empty_scenes(self):
        m = _metrics([{"start": 1, "end": 10, "summary": ""}])
        line = ht.analysis_effectiveness_log_line(m)
        self.assertIn("icerigi bos sahne: 1", line)


if __name__ == "__main__":
    unittest.main()
