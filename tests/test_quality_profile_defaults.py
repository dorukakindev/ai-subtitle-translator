import re
import unittest
from pathlib import Path

from subtitle_translator_gui import (
    QUALITY_PROFILE_DEFAULTS,
    QUALITY_PROFILE_VERSION,
    _apply_quality_profile_defaults,
)


SOURCE = Path(__file__).resolve().parents[1] / "subtitle_translator_gui.py"


class QualityProfileDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_context_and_request_defaults(self):
        expected = {
            "CHUNK": "25",
            "CONTEXT_LINES": "20",
            "LOOKAHEAD_LINES": "10",
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
            "self.semantic_reconcile_var = ctk.BooleanVar(value=True)",
            "self.backup_raw_var = ctk.BooleanVar(value=True)",
            "self.linebreak_var = ctk.BooleanVar(value=False)",
            "self.hybrid_var = ctk.BooleanVar(value=True)",
            "self.chain_ctx_var = ctk.BooleanVar(value=True)",
            'self.analysis_depth_var = ctk.StringVar(value="Maksimum")',
            '"GPT-5.4 (Reseller)" if role == "critic"',
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
                "analysis_depth": "Maksimum",
                "chunk_size": 25,
                "context_lines": 20,
                "lookahead_lines": 10,
                "scene_gap_seconds": 3.0,
                "temperature": 0.2,
                "critic": True,
                "helper_model_critic": "GPT-5.4 (Reseller)",
                "semantic_reconcile": True,
                "clean_sdh": True,
                "backup_raw": True,
                "linebreak": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
