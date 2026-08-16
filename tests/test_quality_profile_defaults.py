import re
import unittest
from pathlib import Path

from subtitle_translator_gui import (
    DEEP_DELIVERY_COVERAGE_DEFAULT,
    MEDIA_MODE_DEFAULTS,
    QUALITY_PROFILE_DEFAULTS,
    QUALITY_PROFILE_VERSION,
    WORKFLOW_PROFILES,
    _apply_quality_profile_defaults,
    _deep_delivery_coverage_label,
    _deep_delivery_coverage_value,
)


SOURCE = Path(__file__).resolve().parents[1] / "subtitle_translator_gui.py"


class QualityProfileDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_context_and_request_defaults(self):
        expected = {
            "CHUNK": "25",
            "CONTEXT_LINES": "30",
            "LOOKAHEAD_LINES": "15",
            "SCENE_GAP_SEC": "3.0",
        }
        for name, value in expected.items():
            self.assertRegex(
                self.source,
                rf"(?m)^{name}\s*=\s*{re.escape(value)}\b",
            )
        self.assertIn("self._temperature       = 0.2", self.source)

    def test_ui_quality_profile_defaults(self):
        expected = [
            'self.limit_class_var = ctk.StringVar(value="250K")',
            'self.model_var = ctk.StringVar(value="gpt-5.4")',
            'self.mode_var = ctk.StringVar(value="sync")',
            "self.clean_sdh_var = ctk.BooleanVar(value=True)",
            "self.critic_var = ctk.BooleanVar(value=True)",
            "self.native_var = ctk.BooleanVar(value=False)",
            "self.semantic_reconcile_var = ctk.BooleanVar(value=False)",
            "self.deep_delivery_semantic_var = ctk.BooleanVar(value=True)",
            "value=DEEP_DELIVERY_COVERAGE_DEFAULT",
            "self.term_normalize_var = ctk.BooleanVar(value=True)",
            "self.season_canon_var = ctk.BooleanVar(value=False)",
            'self.media_mode_var = ctk.StringVar(value="Dizi")',
            "self.backup_raw_var = ctk.BooleanVar(value=True)",
            "self.linebreak_var = ctk.BooleanVar(value=False)",
            "self.hybrid_var = ctk.BooleanVar(value=True)",
            "self.chain_ctx_var = ctk.BooleanVar(value=True)",
            'self.analysis_depth_var = ctk.StringVar(value="Gelişmiş")',
            'default_helper_model = "GPT-5.4 (Reseller)"',
            "self.main_custom_var = ctk.BooleanVar(value=True)",
        ]
        for snippet in expected:
            self.assertIn(snippet, self.source)

    def test_existing_settings_receive_profile_once(self):
        settings = {
            "mode": "batch",
            "analysis_depth": "Gelismis",
            "chunk_size": 30,
            "linebreak": True,
            "unrelated": "kept",
        }
        self.assertTrue(_apply_quality_profile_defaults(settings))
        self.assertEqual(settings["quality_profile_version"], QUALITY_PROFILE_VERSION)
        self.assertEqual(settings["mode"], "sync")
        self.assertEqual(settings["media_mode"], "Dizi")
        self.assertEqual(settings["content_type"], "Otomatik")
        self.assertTrue(settings["series_memory"])
        self.assertFalse(settings["season_canon"])
        self.assertFalse(settings["linebreak"])
        self.assertEqual(settings["unrelated"], "kept")

        settings["mode"] = "batch"
        self.assertFalse(_apply_quality_profile_defaults(settings))
        self.assertEqual(settings["mode"], "batch")

    def test_partial_settings_are_not_forced(self):
        settings = {"mode": "batch", "linebreak": True}
        self.assertFalse(_apply_quality_profile_defaults(settings))
        self.assertEqual(settings, {"mode": "batch", "linebreak": True})

    def test_migration_profile_matches_requested_values(self):
        self.assertEqual(
            QUALITY_PROFILE_DEFAULTS,
            {
                "model": "gpt-5.4",
                "mode": "sync",
                "hybrid": True,
                "analysis_depth": "Gelişmiş",
                "chunk_size": 25,
                "context_lines": 30,
                "lookahead_lines": 15,
                "scene_gap_seconds": 3.0,
                "temperature": 0.2,
                "max_retry": 1,
                "critic": True,
                "main_custom": True,
                "main_custom_model": "gpt-5.4",
                "main_custom_url": "https://api.shuaiapi.com/v1",
                "helper_model_analysis": "GPT-5.4 (Reseller)",
                "helper_model_critic": "GPT-5.4 (Reseller)",
                "helper_model_polish": "GPT-5.4 (Reseller)",
                "helper_model_qc": "GPT-5.4 (Reseller)",
                "polish": False,
                "native": False,
                "qc": False,
                "backtrans": False,
                "semantic_reconcile": False,
                "deep_delivery_semantic": True,
                "deep_delivery_coverage": 0.35,
                "review_pass": False,
                "chain_ctx": True,
                "clean_sdh": True,
                "backup_raw": True,
                "term_normalize": True,
                "quality_report_only": True,
                "repair_missing": False,
                "media_mode": "Dizi",
                "content_type": "Otomatik",
                "series_memory": True,
                "season_canon": False,
                "linebreak": False,
            },
        )

    def test_v5_migration_preserves_media_kind_and_applies_balanced_defaults(self):
        settings = {
            "quality_profile_version": 5,
            "media_mode": "Film",
            "content_type": "Sanat / Festival Filmi",
            "series_memory": False,
            "season_canon": False,
            "helper_model_polish": "gpt-5.4-mini",
            "helper_model_qc": "gpt-5.4-mini",
        }

        self.assertTrue(_apply_quality_profile_defaults(settings))
        self.assertEqual(settings["quality_profile_version"], QUALITY_PROFILE_VERSION)
        self.assertEqual(settings["media_mode"], "Film")
        self.assertEqual(settings["content_type"], "Sanat / Festival Filmi")
        self.assertFalse(settings["series_memory"])
        self.assertFalse(settings["season_canon"])
        self.assertEqual(settings["analysis_depth"], "Gelişmiş")
        self.assertTrue(settings["critic"])
        self.assertTrue(settings["term_normalize"])
        self.assertTrue(settings["chain_ctx"])
        for key in ("polish", "native", "qc", "backtrans",
                    "semantic_reconcile", "review_pass"):
            self.assertFalse(settings[key])
        self.assertTrue(settings["deep_delivery_semantic"])
        self.assertEqual(settings["deep_delivery_coverage"], 0.35)
        self.assertTrue(settings["main_custom"])
        for role in ("analysis", "critic", "polish", "qc"):
            self.assertEqual(
                settings[f"helper_model_{role}"], "GPT-5.4 (Reseller)")

    def test_v6_migration_keeps_media_mode_and_updates_pass_defaults(self):
        settings = {
            "quality_profile_version": 6,
            "media_mode": "Dizi",
            "content_type": "Anime",
            "polish": True,
            "native": True,
            "semantic_reconcile": True,
            "season_canon": True,
            "unrelated": "kept",
        }

        self.assertTrue(_apply_quality_profile_defaults(settings))
        self.assertEqual(settings["quality_profile_version"], QUALITY_PROFILE_VERSION)
        self.assertEqual(settings["media_mode"], "Dizi")
        self.assertEqual(settings["content_type"], "Anime")
        self.assertTrue(settings["series_memory"])
        self.assertFalse(settings["season_canon"])
        self.assertFalse(settings["polish"])
        self.assertFalse(settings["native"])
        self.assertFalse(settings["semantic_reconcile"])
        self.assertEqual(settings["unrelated"], "kept")

    def test_film_and_series_profiles_do_not_override_reseller_routing(self):
        for mode in ("Film", "Dizi"):
            self.assertEqual(
                set(MEDIA_MODE_DEFAULTS[mode]),
                {"series_memory", "season_canon"},
            )
        self.assertEqual(
            MEDIA_MODE_DEFAULTS["Dizi"],
            {"series_memory": True, "season_canon": False},
        )
        self.assertEqual(
            MEDIA_MODE_DEFAULTS["Film"],
            {"series_memory": False, "season_canon": False},
        )

    def test_normal_workflow_is_cost_balanced_for_film_and_series(self):
        profile = WORKFLOW_PROFILES["Normal"]
        self.assertTrue(profile["hybrid_var"])
        self.assertEqual(profile["analysis_depth_var"], "Gelişmiş")
        self.assertTrue(profile["critic_var"])
        self.assertTrue(profile["term_normalize_var"])
        self.assertTrue(profile["quality_report_only_var"])
        self.assertTrue(profile["deep_delivery_semantic_var"])
        self.assertEqual(
            profile["deep_delivery_coverage_var"],
            DEEP_DELIVERY_COVERAGE_DEFAULT)
        self.assertTrue(profile["chain_ctx_var"])
        for key in ("polish_var", "native_var", "backtrans_var",
                    "semantic_reconcile_var", "review_pass_var", "qc_var",
                    "season_canon_var"):
            self.assertFalse(profile[key])

    def test_maximum_workflow_only_deepens_analysis(self):
        normal = WORKFLOW_PROFILES["Normal"]
        maximum = WORKFLOW_PROFILES["Maksimum kalite"]
        self.assertEqual(normal["analysis_depth_var"], "Gelişmiş")
        self.assertEqual(maximum["analysis_depth_var"], "Maksimum")
        for key in (
            "critic_var", "polish_var", "native_var", "backtrans_var",
            "semantic_reconcile_var", "review_pass_var",
            "deep_delivery_semantic_var",
            "deep_delivery_coverage_var",
            "term_normalize_var", "quality_report_only_var",
            "repair_missing_var", "chain_ctx_var", "clean_sdh_var",
            "linebreak_var", "qc_var",
        ):
            self.assertEqual(maximum[key], normal[key], key)

    def test_deep_delivery_coverage_defaults_to_economical_and_allows_full(self):
        self.assertEqual(_deep_delivery_coverage_value(None), 0.35)
        self.assertEqual(_deep_delivery_coverage_value("Ekonomik (%35)"), 0.35)
        self.assertEqual(_deep_delivery_coverage_value("Tam (%100)"), 1.0)
        self.assertEqual(_deep_delivery_coverage_label(1.0), "Tam (%100)")

    def test_v8_migration_adds_economical_coverage_without_overriding_toggle(self):
        settings = {
            "quality_profile_version": 8,
            "deep_delivery_semantic": False,
            "critic": True,
        }
        self.assertTrue(_apply_quality_profile_defaults(settings))
        self.assertFalse(settings["deep_delivery_semantic"])
        self.assertEqual(settings["deep_delivery_coverage"], 0.35)
        self.assertEqual(settings["quality_profile_version"], QUALITY_PROFILE_VERSION)


if __name__ == "__main__":
    unittest.main()
