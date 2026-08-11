import json
import inspect
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
    @staticmethod
    def _request():
        return {"custom_id": "chunk_0", "body": {
            "model": "gpt-test",
            "messages": [
                {"role": "system", "content": "translate"},
                {"role": "user", "content": json.dumps({
                    "tr": [
                        {"i": 1, "t": "John arrived."},
                        {"i": 2, "t": "Mary left."},
                    ],
                    "ctx": ["Earlier."],
                })},
            ],
        }}

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

    def test_owner_mismatch_is_preserved_for_manual_report_without_retry(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._json_repair_pass = lambda *_args, **_kwargs: None
        logs = []
        app._log = lambda message, *_args, **_kwargs: logs.append(message)
        original = json.dumps([
            {"i": 1, "t": "Mary ayrıldı."},
            {"i": 2, "t": "John geldi."},
        ])
        raw_map = {"chunk_0": original}
        unresolved = app._retry_hata(
            MagicMock(), raw_map, [self._request()], max_rounds=0)
        self.assertEqual(unresolved, set())
        self.assertEqual(raw_map["chunk_0"], original)
        self.assertTrue(any("API yeniden denenmedi" in item for item in logs))

    def test_single_owner_mismatch_does_not_trigger_small_api_retry(self):
        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._json_repair_pass = lambda *_args, **_kwargs: None
        logs = []
        app._log = lambda message, *_args, **_kwargs: logs.append(message)
        request = {"custom_id": "chunk_0", "body": {
            "model": "gpt-test",
            "messages": [
                {"role": "system", "content": "translate"},
                {"role": "user", "content": json.dumps({"tr": [
                    {"i": 1, "t": "John arrived."},
                    {"i": 2, "t": "The door opened."},
                    {"i": 3, "t": "Mary left."},
                ]})},
            ],
        }}
        original = json.dumps([
            {"i": 1, "t": "Mary geldi."},
            {"i": 2, "t": "Kapı açıldı."},
            {"i": 3, "t": "Mary ayrıldı."},
        ])
        raw_map = {"chunk_0": original}
        with patch.object(gui, "_safe_chat_create") as api_call:
            unresolved = app._retry_hata(
                MagicMock(), raw_map, [request], max_rounds=2)
        api_call.assert_not_called()
        self.assertEqual(unresolved, set())
        self.assertEqual(raw_map["chunk_0"], original)
        self.assertTrue(any("#1" in item for item in logs))

    def test_invalid_wave_tail_is_not_injected_into_next_wave(self):
        request = self._request()
        wave_b = [{"custom_id": "chunk_1", "body": {
            "messages": [
                {"role": "system", "content": "translate"},
                {"role": "user", "content": json.dumps({
                    "tr": [{"i": 3, "t": "Continue."}],
                    "ctx": ["Earlier."],
                })},
            ]}}]
        raw_map = {"chunk_0": json.dumps([
            {"i": 1, "t": "Mary ayrıldı."},
            {"i": 2, "t": "John geldi."},
        ])}
        result = gui._chain_waves(
            [request], wave_b, raw_map,
            {"chunk_0": [("1", "", "x"), ("2", "", "x")]}, 10)
        payload = json.loads(result[0]["body"]["messages"][1]["content"])
        self.assertNotIn("prev_tr", payload)


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

    def test_manual_postprocess_does_not_write_after_selected_pass_failure(self):
        source = inspect.getsource(gui.App._run_post_process)
        self.assertIn("postprocess_failed = True", source)
        failure_gate = source.index("if postprocess_failed:")
        write_call = source.index("write_srt(fp, _delivery_blocks, tgt)")
        self.assertLess(failure_gate, write_call)
        self.assertIn("orijinal dosya değiştirilmedi", source)

    def test_term_normalization_failures_are_not_silent(self):
        for method in (
                gui.App._run_sync_hybrid,
                gui.App._wait_batch_hybrid,
                gui.App._write_results):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertIn("Normalizasyonu çalışmadı", source)

    def test_failed_required_quality_pass_blocks_completed_status(self):
        self.assertTrue(gui._quality_pass_has_hard_failure({
            "Critic": {"status": "failed"}}))
        self.assertTrue(gui._quality_pass_has_hard_failure({
            "Final-Semantic": {"status": "cancelled"}}))
        self.assertFalse(gui._quality_pass_has_hard_failure({
            "Critic": {"status": "partial"},
            "Series-Memory": {"status": "failed"},
        }))

    def test_all_main_flows_gate_required_quality_pass_failures(self):
        for method in (
                gui.App._run_sync_hybrid,
                gui.App._wait_batch_hybrid,
                gui.App._write_results,
                gui.App._run_hybrid):
            with self.subTest(method=method.__name__):
                source = inspect.getsource(method)
                self.assertIn("_quality_pass_has_hard_failure", source)
                self.assertIn("_quarantine_incomplete_final", source)

    def test_repair_only_output_runs_delivery_audit_before_completion(self):
        source = inspect.getsource(gui.App._run_partial_repair_only_file)
        audit_pos = source.index("_subtitle_delivery_audit")
        archive_pos = source.index("_archive_completed_partial_output")
        self.assertLess(audit_pos, archive_pos)
        self.assertIn("_quarantine_incomplete_final", source)


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
