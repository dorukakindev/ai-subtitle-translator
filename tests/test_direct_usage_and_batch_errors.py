import json
import inspect
import re
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
        usage_available=False,
    )


class DirectUsageAndBatchErrorTests(unittest.TestCase):
    def test_usage_accounting_failure_never_breaks_translation_flow(self):
        broken = MagicMock(side_effect=RuntimeError("ledger unavailable"))
        response = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=12), usage_available=True)
        self.assertFalse(gui._report_response_usage(broken, response))

        missing = MagicMock()
        missing.report_missing_usage = MagicMock(
            side_effect=RuntimeError("ledger unavailable"))
        self.assertFalse(gui._report_response_usage(missing, _response("[]")))

    def test_missing_repair_usage_is_reported(self):
        callback = MagicMock()
        callback.report_missing_usage = MagicMock()
        response = _response(json.dumps([{"i": "1", "t": "Merhaba."}]))

        with patch.object(gui, "_safe_chat_create", return_value=response):
            blocks, repaired = gui._repair_untranslated_sync(
                [("1", "00:00:01,000 --> 00:00:02,000", "[HATA]")],
                {"1": "Hello."},
                client=object(),
                src_lang="English",
                tgt_lang="Turkish",
                model="gpt-test",
                token_cb=callback,
                enabled=True,
            )

        self.assertEqual(repaired, 1)
        self.assertEqual(blocks[0][2], "Merhaba.")
        callback.report_missing_usage.assert_called_once_with()

    def test_repair_call_sites_bind_usage_to_the_file_and_pass(self):
        source = inspect.getsource(gui.App)
        calls = [match.start() for match in re.finditer(
            r"_repair_untranslated_sync\(", source)]

        self.assertEqual(len(calls), 6)
        for start in calls:
            self.assertIn(
                "token_cb=_app_token_callback(", source[start:start + 1800])

        callback = MagicMock()
        app = object()
        with patch.object(gui.App, "_token_callback_for_pass",
                          return_value=callback) as factory:
            self.assertIs(
                gui._app_token_callback(
                    app, "gpt-test", "Eksik Cue API OnarÄ±mÄ±",
                    base_url="https://provider.example/v1",
                    file_path="C:/source.srt"),
                callback)
        factory.assert_called_once_with(
            app, "gpt-test", "Eksik Cue API OnarÄ±mÄ±",
            base_url="https://provider.example/v1", file_path="C:/source.srt")

    def test_missing_precontext_usage_is_reported(self):
        callback = MagicMock()
        callback.report_missing_usage = MagicMock()
        response = _response(json.dumps({
            "summary": "Özet", "tone": "ciddi", "characters": [],
            "address_map": [], "terms": {},
        }))

        with patch("hybrid_translate._safe_chat_create", return_value=response):
            result = gui.analyze_file_precontext(
                object(), [(1, "00:00:01,000 --> 00:00:02,000", "Hello.")],
                "gpt-test", "English", "Turkish", token_cb=callback)

        self.assertEqual(result["summary"], "Özet")
        callback.report_missing_usage.assert_called_once_with()

    def test_auxiliary_pass_usage_is_bound_to_pass_and_file(self):
        source = inspect.getsource(gui.App)

        self.assertNotIn(
            "token_callback=self._token_callback_for_model(", source)
        self.assertNotIn("token_cb=self._update_tokens", source)
        self.assertIn('"Okuma Hızı Kısaltma"', source)
        self.assertIn('"AI Segmentasyon"', source)
        self.assertIn('"Ön-Bağlam Analizi"', source)
        self.assertIn('"İçerik Türü Ön Analizi"', source)

        condense_calls = list(re.finditer(r"self\._maybe_condense\(", source))
        merge_calls = list(re.finditer(r"self\._maybe_merge_cues\(", source))
        self.assertEqual(len(condense_calls), 4)
        self.assertEqual(len(merge_calls), 5)
        for match in condense_calls + merge_calls:
            self.assertIn("file_path=", source[match.start():match.start() + 900])

    def test_disabled_condense_does_not_open_a_timing_stage(self):
        source = inspect.getsource(gui.App)
        timing_calls = list(re.finditer(
            r'_record_file_status\(\s*[^,]+, "Okuma Hızı Kısaltma", "running"\)',
            source,
        ))

        self.assertEqual(len(timing_calls), 3)
        for match in timing_calls:
            prefix = source[max(0, match.start() - 100):match.start()]
            self.assertIn("if self.condense_var.get():", prefix)

    def test_json_repair_usage_is_bound_to_request_file(self):
        app = SimpleNamespace(
            _stop_flag=False,
            _helper_request_canceller=None,
            _main_model_name=lambda: "gpt-test",
            _main_api_base_url=lambda: "https://provider.example/v1",
            _log=lambda *_args, **_kwargs: None,
        )
        req = {
            "custom_id": "chunk-1",
            "body": {
                "model": "gpt-test",
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": json.dumps({
                        "tr": [{"i": "1", "t": "Hello."}],
                    })},
                ],
            },
        }
        callback = MagicMock()
        callback.report_missing_usage = MagicMock()
        response = _response('[{"i":"1","t":"Merhaba."}]')

        with patch.object(gui, "_safe_chat_create", return_value=response), \
             patch.object(gui, "_app_token_callback",
                          return_value=callback) as callback_factory:
            gui.App._json_repair_pass(
                app, object(), {"chunk-1": "{broken"}, [req],
                file_map={"chunk-1": [("1", "ts", "C:/movie/source.srt")]},
            )

        callback_factory.assert_called_once_with(
            app, "gpt-test", "JSON Onarımı",
            base_url="https://provider.example/v1",
            file_path="C:/movie/source.srt",
        )

    def test_retry_call_sites_supply_file_ownership(self):
        source = inspect.getsource(gui.App)
        calls = list(re.finditer(r"self\._retry_hata\(", source))

        self.assertEqual(len(calls), 10)
        for match in calls:
            call_text = source[match.start():match.start() + 500]
            self.assertTrue(
                "file_map=" in call_text or "file_path=" in call_text,
                call_text,
            )

    def test_malformed_batch_error_row_does_not_hide_later_errors(self):
        content = "\n".join([
            "not-json",
            json.dumps({"custom_id": "chunk_2", "error": {"message": "bad request"}}),
        ])
        entries, malformed = gui._batch_error_file_entries(content)

        self.assertEqual(entries, [("chunk_2", "bad request")])
        self.assertEqual(malformed, 1)

    def test_batch_error_download_failure_is_logged(self):
        app = SimpleNamespace(_stop_flag=False, _log=MagicMock())
        with patch.object(gui, "_batch_api_call_with_retry",
                          side_effect=RuntimeError("offline")):
            gui.App._show_errors(app, object(), "file_error")

        self.assertIn(
            "Batch hata dosyası okunamadı",
            app._log.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
