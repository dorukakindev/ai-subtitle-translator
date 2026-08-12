import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hybrid_translate as ht
import subtitle_translator_gui as gui


class QualityReportOnlyModeTest(unittest.TestCase):
    @staticmethod
    def _openai_module(payload):
        class FakeCompletions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    usage=None,
                    choices=[SimpleNamespace(message=SimpleNamespace(
                        content=gui.json.dumps(payload, ensure_ascii=False)))],
                )

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=FakeCompletions())

        return SimpleNamespace(OpenAI=FakeOpenAI)

    def test_critic_report_only_keeps_original_and_logs_candidate(self):
        cue = SimpleNamespace(index=1, text="This metaphor works.",
                              start_ms=0, end_ms=1000)
        blocks = [(1, "00:00:00,000 --> 00:00:01,000", "Bu metafoor işe yarıyor.")]
        changes = []
        logs = []
        status = {}

        with patch.dict(sys.modules, {"openai": self._openai_module([])}):
            result = ht.critic_pass_with_helper(
                [cue], blocks, "key", change_log=changes,
                log_fn=lambda message, level="info": logs.append(message),
                status_out=status, apply_changes=False)

        self.assertEqual(result, blocks)
        self.assertTrue(changes)
        self.assertEqual(status["changed"], 0)
        self.assertGreaterEqual(status["suggested"], 1)
        self.assertTrue(status["report_only"])
        self.assertTrue(any("yalnız rapor" in message for message in logs))

    def test_term_normalization_report_only_keeps_original_and_logs_candidate(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000", "Troy kuşatması başladı."),
            ("2", "00:00:01,000 --> 00:00:02,000", "Sonra Troy yıkıldı."),
            ("3", "00:00:02,000 --> 00:00:03,000", "Truva'nın kalıntıları bulundu."),
            ("4", "00:00:03,000 --> 00:00:04,000", "Ama Troy hâlâ tartışmalı."),
            ("5", "00:00:04,000 --> 00:00:05,000", "Truva'ya dair kanıt var."),
        ]
        src = {str(i): "Troy" for i in range(1, 6)}
        fixes = [
            {"id": "1", "tr": "Truva kuşatması başladı."},
            {"id": "2", "tr": "Sonra Truva yıkıldı."},
            {"id": "4", "tr": "Ama Truva hâlâ tartışmalı."},
        ]
        logs = []
        status = {}

        with patch.dict(sys.modules, {"openai": self._openai_module(fixes)}):
            result, changed = gui._normalize_mixed_terms(
                blocks, src, "key", "url", "model",
                locked_terms={"Troy": "Truva"},
                log_fn=lambda message, level="info": logs.append(message),
                status_out=status, apply_changes=False)

        self.assertEqual(result, blocks)
        self.assertEqual(changed, 0)
        self.assertEqual(status["changed"], 0)
        self.assertEqual(status["suggested"], 3)
        self.assertTrue(status["report_only"])
        self.assertTrue(any("yalnız rapor #1" in message for message in logs))

    def test_consistency_report_only_keeps_minority_translation(self):
        cues = [
            SimpleNamespace(index=i, text="Please come with me.")
            for i in range(1, 4)
        ]
        blocks = [
            (1, "00:00:00,000 --> 00:00:01,000", "Lütfen benimle gel."),
            (2, "00:00:01,000 --> 00:00:02,000", "Lütfen benimle gel."),
            (3, "00:00:02,000 --> 00:00:03,000", "Lütfen bana eşlik et."),
        ]
        logs = []
        with patch("hybrid_translate.validate_polish_candidate",
                   return_value=(True, "")):
            result, suggested = ht.consistency_sweep(
                cues, blocks,
                log_fn=lambda message, level="info": logs.append(message),
                apply_changes=False)

        self.assertEqual(result, blocks)
        self.assertEqual(suggested, 1)
        self.assertTrue(any("Tutarlılık yalnız rapor #3" in item for item in logs))

    def test_critic_report_labels_suggestions_as_not_applied(self):
        app = gui.App.__new__(gui.App)
        app._log = lambda *args, **kwargs: None
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "film.srt"
            gui.App._write_critic_change_report(
                app, output,
                [{"id": "7", "reason": "test", "source": "Hello",
                  "before": "Merhaba", "after": "Selam"}],
                report_only=True)
            report = output.parent / "Raporlar" / "film.critic_degisiklikler.txt"
            text = report.read_text(encoding="utf-8")
        self.assertIn("YALNIZ RAPORLANAN ÖNERİLER", text)
        self.assertIn("altyazıya uygulanmadı", text)
        self.assertNotIn("UYGULANAN DÜZELTMELER", text)

    def test_all_workflow_profiles_default_to_report_only(self):
        self.assertTrue(gui.QUALITY_PROFILE_DEFAULTS["quality_report_only"])
        for profile in gui.WORKFLOW_PROFILES.values():
            self.assertTrue(profile["quality_report_only_var"])


if __name__ == "__main__":
    unittest.main()
