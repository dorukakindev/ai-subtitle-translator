# -*- coding: utf-8 -*-
"""plans/acik-passler-iyilestirme-brief-2026-08-20.md maddelerinin testleri."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hybrid_translate as ht
import prompt_constants as pc
import provider_retry as pr
import subtitle_translator_gui as g


class IdentityGlossaryGuardTest(unittest.TestCase):
    """P1-B: analiz modelinin kendi kimlik eşlemeleri de filtrelenmeli."""

    def _clean(self, raw):
        return ht.sanitize_glossary_for_turkish(raw, target_language="Turkish")

    def test_translatable_identity_entries_are_dropped(self):
        cleaned = self._clean({
            "French": "French", "Jesus": "Jesus", "King": "King",
            "Voiceover": "Voiceover", "Holy Ghost": "Holy Ghost",
            "China": "China",
        })
        self.assertEqual(cleaned, {})

    def test_proper_noun_identity_entries_survive(self):
        raw = {"Barthou": "Barthou", "Schumann": "Schumann",
               "Loch Ness": "Loch Ness", "West Block": "West Block"}
        self.assertEqual(self._clean(raw), raw)

    def test_real_translations_are_untouched(self):
        raw = {"other world": "öte dünya", "Great Pyramid": "Büyük Piramit"}
        self.assertEqual(self._clean(raw), raw)

    def test_guard_only_applies_to_identity_mappings(self):
        # 'Jesus' -> 'İsa' bir kimlik eşlemesi DEĞİL, kalmalı.
        self.assertEqual(self._clean({"Jesus": "İsa"}), {"Jesus": "İsa"})


class ProportionalDistributionRuleTest(unittest.TestCase):
    """P1-C: frag grubunda uzunluk dengesi kuralı iki prompt'ta da olmalı."""

    def test_rule_is_in_the_shared_instruction(self):
        self.assertIn("LENGTH BALANCE", pc.JSON_INSTRUCTION)

    def test_sync_prompt_carries_it(self):
        prompt = g._build_sync_system_prompt("English", "Turkish")
        self.assertIn("LENGTH BALANCE", prompt)

    def test_hybrid_path_carries_it(self):
        self.assertIn("LENGTH BALANCE", ht.JSON_INSTRUCTION)


class DeliveryScanSuspectFeedTest(unittest.TestCase):
    """P1-D: deterministik tarama bulguları derin taramaya şüpheli olarak gider."""

    def _cue(self, index, timestamp, text):
        cue = type("Cue", (), {})()
        cue.index, cue.timestamp, cue.text = index, timestamp, text
        cue.start, cue.end = [part.strip() for part in timestamp.split("-->")]
        return cue

    def test_cue_fill_pair_becomes_a_suspect(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:08,000", "Kısa bir giriş cümlesi."),
            ("2", "00:00:08,000 --> 00:00:08,400",
             "Bu cue çok kısa ama içine bütün cümlenin metni yığılmış durumda "
             "ve okunması imkânsız."),
        ]
        cues = [
            self._cue(1, "00:00:01,000 --> 00:00:08,000",
                      "A fairly long English sentence that sets the scene here."),
            self._cue(2, "00:00:08,000 --> 00:00:08,400", "elements."),
        ]
        suspects = dict(g._delivery_scan_suspect_ids(blocks, cues))
        self.assertEqual(suspects.get("2"), "SCAN_CUE_FILL")

    def test_bad_input_returns_empty_instead_of_raising(self):
        self.assertEqual(g._delivery_scan_suspect_ids([], None), [])
        self.assertEqual(g._delivery_scan_suspect_ids(None, None), [])


class TermNormalizeApplyGateTest(unittest.TestCase):
    """P1-A: terim normalizasyonu artık teslim-rapor kapısına bağlı değil."""

    def test_default_is_on(self):
        self.assertTrue(g.QUALITY_PROFILE_DEFAULTS["term_normalize_apply"])

    def test_all_profiles_enable_it(self):
        for name, profile in g.WORKFLOW_PROFILES.items():
            with self.subTest(profile=name):
                self.assertTrue(profile["term_normalize_apply_var"])

    def test_it_is_a_boundary_quality_var(self):
        self.assertIn("term_normalize_apply", g._BOUNDARY_QUALITY_VARS)

    def test_migration_turns_it_on_for_existing_users(self):
        settings = {"quality_profile_version": 10}
        self.assertTrue(g._apply_quality_profile_defaults(settings))
        self.assertTrue(settings["term_normalize_apply"])


class RetryDefaultTest(unittest.TestCase):
    """P2-G: ana çeviri yeniden deneme turu 1 → 2."""

    def test_default_is_two(self):
        self.assertEqual(g.QUALITY_PROFILE_DEFAULTS["max_retry"], 2)
        self.assertEqual(g.ADVANCED_SETTINGS_RECOMMENDED["_max_retry"], 2)

    def test_migration_raises_one_but_keeps_a_custom_value(self):
        migrated = {"quality_profile_version": 10, "max_retry": 1}
        g._apply_quality_profile_defaults(migrated)
        self.assertEqual(migrated["max_retry"], 2)
        custom = {"quality_profile_version": 10, "max_retry": 5}
        g._apply_quality_profile_defaults(custom)
        self.assertEqual(custom["max_retry"], 5)


class CanonicalNameTest(unittest.TestCase):
    """P3: yerleşik Türkçe yazımı olan adlar doğru hedefle kilitlenir."""

    def test_map_is_shared(self):
        self.assertEqual(pc.CANONICAL_TURKISH_NAMES["sisyphus"], "Sisifos")

    def test_autolock_uses_the_turkish_target(self):
        source = ("Sisyphus rolled the rock uphill. Each dawn Sisyphus began "
                  "again, and Sisyphus never finished the task.")
        self.assertEqual(
            g.auto_locked_proper_nouns(source).get("Sisyphus"), "Sisifos")


class DisplayFileNameTest(unittest.TestCase):
    """UI: dosya adları büyük ekranda ayırt edilebilmeli."""

    EPISODES = [
        "Sex.Death.And.The.Meaning.Of.Life.S01E01.Part.1.Sin.1080p.AMZN."
        "WEB-DL.DDP2.0.H.264-MRCS.vtt",
        "Sex.Death.And.The.Meaning.Of.Life.S01E02.Part.2.Life.After.Death."
        "1080p.AMZN.WEB-DL.DDP2.0.H.264-MRCS.srt",
        "Sex.Death.And.The.Meaning.Of.Life.S01E03.Part.3.The.Meaning.Of.Life."
        "1080p.AMZN.WEB-DL.DDP2.0.H.264-MRCS.srt",
    ]

    def test_episodes_are_distinguishable(self):
        shown = [g.display_file_name(name) for name in self.EPISODES]
        self.assertEqual(len(set(shown)), 3)
        self.assertIn("S01E01", shown[0])
        self.assertIn("S01E02", shown[1])

    def test_release_tokens_are_dropped(self):
        shown = g.display_file_name(self.EPISODES[0])
        for token in ("1080p", "AMZN", "WEB-DL", "MRCS"):
            with self.subTest(token=token):
                self.assertNotIn(token, shown)

    def test_short_names_are_untouched(self):
        self.assertEqual(g.display_file_name("Death Scenes (1989).srt"),
                         "Death Scenes (1989).srt")

    def test_extension_is_kept(self):
        for name in self.EPISODES:
            with self.subTest(name=name[:20]):
                self.assertTrue(g.display_file_name(name).endswith(name[-4:]))

    def test_middle_ellipsis_keeps_both_ends(self):
        long_name = "A" * 60 + "MIDDLE" + "B" * 60 + ".srt"
        shown = g._shorten_middle(long_name)
        self.assertTrue(shown.startswith("A"))
        self.assertTrue(shown.endswith(".srt"))
        self.assertLessEqual(len(shown), 70)


class ShuaiRouteLogTest(unittest.TestCase):
    """UI: aynı rota için tekrar tekrar log basılmamalı."""

    def test_announce_state_exists_and_resets(self):
        self.assertIn("main", pr._SHUAI_ANNOUNCED_ROUTES)
        self.assertIn("main", pr._SHUAI_ANNOUNCE_COUNTS)

    def test_reset_clears_announcements(self):
        with pr._SHUAI_FAILOVER_LOCK:
            pr._SHUAI_ANNOUNCED_ROUTES["main"] = "https://api.oai.sb/v1"
            pr._SHUAI_ANNOUNCE_COUNTS["main"] = 7
        pr.reset_shuai_route_metrics()
        self.assertEqual(pr._SHUAI_ANNOUNCED_ROUTES["main"], "")
        self.assertEqual(pr._SHUAI_ANNOUNCE_COUNTS["main"], 0)


if __name__ == "__main__":
    unittest.main()
