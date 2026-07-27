import re
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
