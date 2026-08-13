import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class _StubApp:
    def __init__(self):
        self.logs = []

    def _log(self, message, level=""):
        self.logs.append((level, message))

    def _log_exc(self, message, exc):
        self.logs.append(("err", f"{message}: {exc}"))


class TermNormalizeReportTest(unittest.TestCase):
    def test_writes_all_decisions_response_issues_and_neighbor_context(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "film.srt"
            cues = [
                (1, "00:00:01,000 --> 00:00:02,000", "We reached Troy."),
                (2, "00:00:02,000 --> 00:00:03,000", "Troy fell."),
                (3, "00:00:03,000 --> 00:00:04,000", "We left."),
            ]
            blocks = [
                (1, cues[0][1], "Troy'a ulaştık."),
                (2, cues[1][1], "Troy düştü."),
                (3, cues[2][1], "Ayrıldık."),
            ]
            status = {
                "status": "partial", "report_only": True,
                "safe_candidates": [{
                    "id": "2", "source": "Troy fell.",
                    "before": "Troy düştü.", "candidate": "Truva düştü.",
                    "fixes": [("Troy", "Truva")],
                }],
                "rejected_candidates": [{
                    "id": "1", "reason": "suffix_harmony",
                    "source": "We reached Troy.",
                    "before": "Troy'a ulaştık.",
                    "candidate": "Truva'a ulaştık.",
                    "fixes": [("Troy", "Truva")],
                }],
                "response_issues": [{"id": "9", "reason": "missing_id"}],
            }
            app = _StubApp()

            gui.App._write_term_normalize_report(
                app, output, status, source_cues=cues,
                translation_blocks=blocks)

            report = (Path(td) / "Raporlar"
                      / "film.terim_normalizasyonu.txt").read_text(
                          encoding="utf-8")
            self.assertIn("Güvenli öneri: 1 (altyazıya uygulanmadı)", report)
            self.assertIn("#2  [Troy->Truva]", report)
            self.assertIn("#1  [suffix_harmony]", report)
            self.assertIn("#9: missing_id", report)
            self.assertIn("önce #1 | Kaynak: We reached Troy.", report)
            self.assertIn("sonra #3 | Kaynak: We left.", report)

    def test_empty_status_removes_stale_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "film.srt"
            report = (Path(td) / "Raporlar"
                      / "film.terim_normalizasyonu.txt")
            report.parent.mkdir()
            report.write_text("stale", encoding="utf-8")

            gui.App._write_term_normalize_report(_StubApp(), output, {})

            self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
