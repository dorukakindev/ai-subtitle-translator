import json
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
