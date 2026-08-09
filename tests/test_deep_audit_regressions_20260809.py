import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import helper_models
import hybrid_translate
import subtitle_translator_gui as gui


class CueOwnershipGuardTest(unittest.TestCase):
    def test_correct_ids_with_swapped_named_content_are_retried(self):
        request = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [
                {"i": 1, "t": "John arrived."},
                {"i": 2, "t": "Mary left."},
            ]
        })}]}}
        raw = json.dumps([
            {"i": 1, "t": "Mary ayrıldı."},
            {"i": 2, "t": "John geldi."},
        ])
        self.assertEqual(
            gui._chunk_response_retry_reason(raw, request),
            "cue_content_owner_mismatch")

    def test_sentence_initial_stopwords_do_not_create_false_owner(self):
        request = {"body": {"messages": [{}, {"role": "user", "content": json.dumps({
            "tr": [
                {"i": 1, "t": "The door opened."},
                {"i": 2, "t": "This was strange."},
            ]
        })}]}}
        raw = json.dumps([
            {"i": 1, "t": "Kapı açıldı."},
            {"i": 2, "t": "Bu tuhaftı."},
        ])
        self.assertEqual(gui._chunk_response_retry_reason(raw, request), "")


class DeliveryHardeningTest(unittest.TestCase):
    def test_dialogue_with_translation_or_timing_label_is_not_credit(self):
        self.assertFalse(gui._is_delivery_credit("Translation: impossible."))
        self.assertFalse(gui._is_delivery_credit("Timing: perfect."))
        self.assertTrue(gui._is_delivery_credit("Translation: M_I_S"))

    def test_residual_delivery_artifacts_are_hard_errors(self):
        for field in (
                "residual_credit_cues", "residual_sdh_cues",
                "residual_position_tags", "hatted_letters",
                "signature_mismatch"):
            with self.subTest(field=field):
                value = True if field == "signature_mismatch" else ["1"]
                self.assertTrue(gui._delivery_audit_has_hard_error({field: value}))

    def test_delivery_failure_is_removed_from_completed_outcome(self):
        rows = [{"source_path": "bad.srt", "run_status": "error"}]
        completed, failed = gui._reconcile_delivery_outcomes(
            rows, ["good.srt", "bad.srt"], [])
        self.assertEqual(completed, ["good.srt"])
        self.assertEqual(failed, ["bad.srt"])

    def test_series_filename_requires_sxxexx(self):
        self.assertIn("SxxExx", gui._upload_filename_issue(
            Path("Show/Season 1/episode 3.srt")))
        self.assertEqual(gui._upload_filename_issue(
            Path("Show/Season 1/Show S01E03 English.srt")), "")

    def test_postprocess_source_is_resolved_from_delivery_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "Show" / "episode.srt"
            source = root / "source.srt"
            output.parent.mkdir(parents=True)
            output.write_text("x", encoding="utf-8")
            source.write_text("y", encoding="utf-8")
            reports = root / "Raporlar"
            reports.mkdir()
            (reports / "ceviri_raporu.json").write_text(json.dumps({
                "files": [{"output_path": str(output),
                           "source_path": str(source)}]
            }), encoding="utf-8")
            self.assertEqual(gui._resolve_postprocess_source(output), source)


class StaleArtifactTest(unittest.TestCase):
    def _app(self):
        app = gui.App.__new__(gui.App)
        app._log = lambda *_args, **_kwargs: None
        app._log_exc = lambda *_args, **_kwargs: None
        return app

    def test_empty_qc_and_critic_remove_stale_reports(self):
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "film.srt"
            reports = fp.parent / "Raporlar"
            reports.mkdir()
            qc = reports / "film.qc_degisiklikler.txt"
            critic = reports / "film.critic_degisiklikler.txt"
            qc.write_text("old", encoding="utf-8")
            critic.write_text("old", encoding="utf-8")
            app = self._app()
            app._write_qc_change_report(fp, [])
            app._write_critic_change_report(fp, [])
            self.assertFalse(qc.exists())
            self.assertFalse(critic.exists())


class TranslationMemoryContextTest(unittest.TestCase):
    def test_store_pairs_passes_source_fingerprint(self):
        app = gui.App.__new__(gui.App)
        app._tm = MagicMock()
        app._tm.store_batch.return_value = True
        app._tm.hit_count_session.return_value = 0
        app._update_tm_stat = lambda: None
        app._log = lambda *_args, **_kwargs: None
        app.profanity_var = SimpleNamespace(get=lambda: "")
        app._store_tm_pairs(
            [("1", "00:00:00,000 --> 00:00:01,000", "Merhaba")],
            {"1": "Hello"}, "gpt", "Turkish",
            context_fingerprint="source-sha")
        self.assertEqual(
            app._tm.store_batch.call_args.kwargs["context_fingerprint"],
            "source-sha")


class AssLanguageAndAnthropicTest(unittest.TestCase):
    def test_hybrid_ass_loader_forwards_source_language(self):
        with patch("subtitle_formats.parse_ass", return_value=[] ) as parse_ass:
            with patch("subtitle_localizer.srt.parse_srt", return_value=[]):
                hybrid_translate.load_subtitle("episode.ass", "Japanese")
        parse_ass.assert_called_once_with(
            "episode.ass", lyric_language="Japanese")

    def test_default_anthropic_route_uses_native_key_header(self):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            helper_models.call_anthropic_messages(
                "claude", [{"role": "user", "content": "x"}],
                api_key_str="key")
        headers = {key.casefold(): value for key, value in
                   urlopen.call_args.args[0].header_items()}
        self.assertEqual(headers.get("x-api-key"), "key")
        self.assertNotIn("authorization", headers)

    def test_live_anthropic_transport_is_closed_on_cancel(self):
        from request_cancellation import RunRequestCanceller

        started = threading.Event()
        released = threading.Event()
        connection = MagicMock()
        connection.request.side_effect = lambda *_args, **_kwargs: started.set()

        def getresponse():
            released.wait(1)
            raise OSError("closed")

        connection.getresponse.side_effect = getresponse
        connection.close.side_effect = released.set
        canceller = RunRequestCanceller()
        errors = []

        def worker():
            try:
                helper_models.call_anthropic_messages(
                    "claude", [{"role": "user", "content": "x"}],
                    cancel_context=canceller)
            except Exception as exc:
                errors.append(exc)

        with patch("http.client.HTTPSConnection", return_value=connection):
            thread = threading.Thread(target=worker)
            thread.start()
            self.assertTrue(started.wait(1))
            self.assertEqual(canceller.cancel(), 1)
            thread.join(1)
        self.assertFalse(thread.is_alive())
        connection.close.assert_called()
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
