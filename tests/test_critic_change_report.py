"""Critic değişiklik raporu — <dosya>.critic_degisiklikler.txt (2026-07-21).

Neden: Critic Pass 150-200 satır değiştirebiliyor (bkz. QC değişiklik raporu,
test_qc_change_report.py — aynı motivasyon) ama hangi satırın NEDEN (hangi
validator sebebiyle) değiştiğini kimse göremiyordu. ht.critic_pass_with_helper
artık isteğe bağlı bir change_log listesi dolduruyor; gui bunu tek bir txt
raporuna yazıyor.
"""
import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class _StubApp:
    def __init__(self):
        self.logs = []

    def _log(self, msg, level=""):
        self.logs.append((level, msg))

    def _log_exc(self, msg, exc):
        self.logs.append(("err", f"{msg}: {exc}"))

    def _write_critic_change_report(self, fp, records):
        return gui.App._write_critic_change_report(self, fp, records)


class WriteCriticChangeReportTest(unittest.TestCase):
    def test_no_records_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            app = _StubApp()
            gui.App._write_critic_change_report(app, fp, [])
            self.assertFalse((Path(td) / "episode.critic_degisiklikler.txt").exists())

    def test_records_written_with_source_before_after_reason(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            app = _StubApp()
            records = [
                {"id": "12", "source": "He's brainless.", "before": "O beyinsiz.",
                 "after": "Beyinsizin teki.", "reason": "EARLY_VERB_CLOSURE"},
                {"id": "40", "source": "You do?", "before": "Yapıyor musun?",
                 "after": "Öyle mi?", "reason": "GARBLE_TOKEN(musun)"},
            ]
            gui.App._write_critic_change_report(app, fp, records)
            report_path = Path(td) / "episode.critic_degisiklikler.txt"
            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("#12", text)
            self.assertIn("EARLY_VERB_CLOSURE", text)
            self.assertIn("He's brainless.", text)
            self.assertIn("O beyinsiz.", text)
            self.assertIn("Beyinsizin teki.", text)
            self.assertIn("#40", text)
            self.assertIn("Öyle mi?", text)
            self.assertIn("Toplam: 2 satır", text)
            self.assertTrue(any("Critic değişiklik raporu" in msg for _, msg in app.logs))


if __name__ == "__main__":
    unittest.main()
