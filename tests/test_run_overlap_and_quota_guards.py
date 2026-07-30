import unittest
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class MultiLineSdhFallbackTest(unittest.TestCase):
    def test_bulleted_multi_effect_source_is_sdh_only(self):
        self.assertTrue(gui._src_is_sdh_only(
            "- [scream]\n- [glass shattering]"
        ))
        self.assertFalse(gui._src_is_sdh_only(
            "- [scream]\n- Get out of here!"
        ))

    def test_hata_for_sdh_only_source_is_dropped_not_marked_missing(self):
        blocks = [("547", "00:20:23,290 --> 00:20:24,790", "[HATA]")]
        result, marked = gui._fill_hata_with_source(
            blocks,
            {"547": "- [scream]\n- [glass shattering]"},
        )
        self.assertEqual(result, [])
        self.assertEqual(marked, 0)


class ConcurrentTestTranslationGuardTest(unittest.TestCase):
    def test_test_translation_cannot_start_during_active_run(self):
        app = gui.App.__new__(gui.App)
        app._is_running = True
        app._folder_scan_busy = False
        app._log = MagicMock()
        app._main_api_key = MagicMock()

        app._test_translate()

        app._main_api_key.assert_not_called()
        app._log.assert_called_once_with(
            "Test çevirisi çalışan çeviri sırasında başlatılamaz.", "warn"
        )


class PermanentQuotaFailureTest(unittest.TestCase):
    def test_repair_stops_after_first_permanent_quota_error(self):
        class QuotaError(RuntimeError):
            status_code = 403

        blocks = [
            (str(idx), "00:00:01,000 --> 00:00:02,000", "[HATA]")
            for idx in range(1, 32)
        ]
        raw = {str(idx): f"Source dialogue {idx}." for idx in range(1, 32)}
        log = MagicMock()

        with patch(
            "subtitle_translator_gui._safe_chat_create",
            side_effect=QuotaError(
                "token quota is not enough: pre_consume_token_quota_failed"
            ),
        ) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks,
                raw,
                client=object(),
                src_lang="English",
                tgt_lang="Turkish",
                log_fn=log,
            )

        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 0)
        self.assertEqual(result, blocks)
        self.assertTrue(any(
            "kalan onarım istekleri gönderilmeyecek" in str(call.args[0])
            for call in log.call_args_list
        ))


if __name__ == "__main__":
    unittest.main()
