"""QC değişiklik raporu — <dosya>.qc_degisiklikler.txt (2026-07-20).

Neden: QC dialog'u "Öneri" metnini gösteriyor ama onaylanan her satır
qc_auto_fix içinde kaynak+hata+öneri eşliğinde YENİDEN çevriliyor -- gerçekten
uygulanan metin dialogdaki önerinin AYNISI olmayabilir (yalnızca yeniden-çeviri
başarısız/güvenlik-filtresinden dönerse öneri aynen uygulanır). Log da sadece
"X/Y satır yeniden çevrildi" özeti veriyordu, hangi satırın neye dönüştüğünü
göstermiyordu. Kullanıcı bunu paylaşıp kontrol ettirebilsin diye tek bir txt
raporu (kaynak/öncesi/sonrası) eklendi.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import subtitle_translator_gui as gui


class _StubApp:
    """_write_qc_change_report yalnızca self._log ve self._log_exc kullanıyor —
    tam App/Tk kurmaya gerek yok. _write_qc_change_report'un kendisi gerçek
    App metodundan (unbound) alınıyor ki test, üretim koduyla aynı mantığı
    çalıştırsın."""
    def __init__(self):
        self.logs = []

    def _log(self, msg, level=""):
        self.logs.append((level, msg))

    def _log_exc(self, msg, exc):
        self.logs.append(("err", f"{msg}: {exc}"))

    def _write_qc_change_report(self, fp, records):
        return gui.App._write_qc_change_report(self, fp, records)


class WriteQcChangeReportTest(unittest.TestCase):
    def test_no_records_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            app = _StubApp()
            gui.App._write_qc_change_report(app, fp, [])
            self.assertFalse((Path(td) / "episode.qc_degisiklikler.txt").exists())

    def test_records_written_with_source_before_after(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            app = _StubApp()
            records = [
                {"id": "12", "source": "He's brainless.", "before": "O beyinsiz.",
                 "after": "Beyinsizin teki.", "problem": "Unnatural Phrasing"},
                {"id": "40", "source": "You do?", "before": "Yapıyor musun?",
                 "after": "Öyle mi?", "problem": "Meaning Shift"},
            ]
            gui.App._write_qc_change_report(app, fp, records)
            report_path = Path(td) / "episode.qc_degisiklikler.txt"
            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("#12", text)
            self.assertIn("He's brainless.", text)
            self.assertIn("O beyinsiz.", text)
            self.assertIn("Beyinsizin teki.", text)
            self.assertIn("#40", text)
            self.assertIn("Öyle mi?", text)
            self.assertIn("Toplam: 2 satır", text)
            self.assertTrue(any("QC değişiklik raporu" in msg for _, msg in app.logs))


class RunQualityCheckInlineReportTest(unittest.TestCase):
    """_run_quality_check_inline: auto_issues yolu (dialog gerektirmez) --
    _write_qc_change_report'a gerçekten NE UYGULANDIYSA (öneri değil, qc_auto_fix'in
    sonucu) onun gittiğini kilitler."""

    def test_auto_fix_report_reflects_actual_applied_text_not_suggestion(self):
        app = _StubApp()
        app._main_api_key = lambda: "sk-test"
        app._main_model_name = lambda: "gpt-5.4"
        app._helper_api_base_url = lambda role: "https://api.example.com/v1"
        app._stop_flag = False

        blocks = [("12", "00:00:01,000 --> 00:00:02,000", "O beyinsiz.")]
        issue = {
            "id": "12", "original": "He's brainless.", "current": "O beyinsiz.",
            "problem": "Unnatural Phrasing", "suggestion": "Beyinsizin teki (öneri).",
        }

        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            with mock.patch("hybrid_translate.quality_check_with_helper", return_value=[issue]), \
                 mock.patch("hybrid_translate.split_qc_issues_for_review", return_value=([issue], [])), \
                 mock.patch("hybrid_translate.qc_auto_fix",
                             return_value=[("12", "00:00:01,000 --> 00:00:02,000", "Beyinsizin teki (gerçek çeviri).")]):
                result = gui.App._run_quality_check_inline(
                    app, fp, orig_cues=[], blocks=blocks,
                    mm_key="sk-mm", mm_url="https://api.example.com/v1", mm_model="gpt-5.4-mini",
                    tgt="Turkish",
                )

            self.assertEqual(result[0][2], "Beyinsizin teki (gerçek çeviri).")
            report_path = Path(td) / "episode.qc_degisiklikler.txt"
            self.assertTrue(report_path.exists())
            text = report_path.read_text(encoding="utf-8")
            # Rapor GERÇEKTEN uygulanan metni göstermeli, dialogdaki öneriyi değil.
            self.assertIn("Beyinsizin teki (gerçek çeviri).", text)
            self.assertNotIn("Beyinsizin teki (öneri).", text)

    def test_no_issues_writes_no_report(self):
        app = _StubApp()
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            with mock.patch("hybrid_translate.quality_check_with_helper", return_value=[]):
                gui.App._run_quality_check_inline(
                    app, fp, orig_cues=[], blocks=[("1", "ts", "text")],
                    mm_key="k", mm_url="u", mm_model="m", tgt="Turkish",
                )
            self.assertFalse((Path(td) / "episode.qc_degisiklikler.txt").exists())

    def test_unchanged_text_not_recorded(self):
        # qc_auto_fix satırı değiştirmezse (ör. re-translate başarısız oldu ve
        # fallback da orijinaliyle aynıysa) rapora girmemeli.
        app = _StubApp()
        app._main_api_key = lambda: "sk-test"
        app._main_model_name = lambda: "gpt-5.4"
        app._helper_api_base_url = lambda role: "https://api.example.com/v1"
        app._stop_flag = False

        blocks = [("12", "ts", "Değişmeyen metin.")]
        issue = {"id": "12", "original": "Src", "current": "Değişmeyen metin.",
                  "problem": "X", "suggestion": "Y"}

        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "episode.srt")
            with mock.patch("hybrid_translate.quality_check_with_helper", return_value=[issue]), \
                 mock.patch("hybrid_translate.split_qc_issues_for_review", return_value=([issue], [])), \
                 mock.patch("hybrid_translate.qc_auto_fix", return_value=blocks):
                gui.App._run_quality_check_inline(
                    app, fp, orig_cues=[], blocks=blocks,
                    mm_key="k", mm_url="u", mm_model="m", tgt="Turkish",
                )
            self.assertFalse((Path(td) / "episode.qc_degisiklikler.txt").exists())


if __name__ == "__main__":
    unittest.main()
