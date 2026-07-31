import unittest
from types import SimpleNamespace
from tempfile import TemporaryDirectory
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
    def test_repair_stops_during_retry_wait_when_user_cancels(self):
        blocks = [
            (str(idx), "00:00:01,000 --> 00:00:02,000", "[HATA]")
            for idx in range(1, 32)
        ]
        raw = {str(idx): f"Source dialogue {idx}." for idx in range(1, 32)}
        stopped = False

        def fail_once(*args, **kwargs):
            nonlocal stopped
            stopped = True
            return SimpleNamespace(choices=[], usage=None)

        with patch(
            "subtitle_translator_gui._safe_chat_create",
            side_effect=fail_once,
        ) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks,
                raw,
                client=object(),
                src_lang="English",
                tgt_lang="Turkish",
                cancel_check=lambda: stopped,
            )

        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 0)
        self.assertEqual(result, blocks)

    def test_repair_stops_after_provider_model_channel_error(self):
        class ChannelError(RuntimeError):
            status_code = 503

        blocks = [
            (str(idx), "00:00:01,000 --> 00:00:02,000", "[HATA]")
            for idx in range(1, 32)
        ]
        raw = {str(idx): f"Source dialogue {idx}." for idx in range(1, 32)}
        log = MagicMock()

        with patch(
            "subtitle_translator_gui._safe_chat_create",
            side_effect=ChannelError(
                "Error code: 503 - model_not_found: Failed to get available "
                "channel for model gpt-5.4 under group auto(auto): auto groups "
                "is not enabled"
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
            "model kanalı yok" in str(call.args[0])
            for call in log.call_args_list
        ))

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

    def test_chunk_retry_stops_before_subrequest_salvage_on_permanent_error(self):
        class QuotaError(RuntimeError):
            status_code = 403

        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = MagicMock()
        app._json_repair_pass = MagicMock()
        app._resend_missing_blocks = MagicMock()
        request = {
            "custom_id": "chunk_1",
            "body": {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": '{"tr":[{"i":1,"t":"Hello"}]}'},
                ],
            },
        }

        with patch(
            "subtitle_translator_gui._safe_chat_create",
            side_effect=QuotaError(
                "token quota is not enough: pre_consume_token_quota_failed"
            ),
        ) as create:
            unresolved = app._retry_hata(
                client=object(),
                raw_map={},
                requests_list=[request],
                max_rounds=3,
            )

        self.assertEqual(create.call_count, 1)
        self.assertEqual(unresolved, {"chunk_1"})
        app._resend_missing_blocks.assert_not_called()
        self.assertTrue(any(
            "kalan chunk ve alt-istek kurtarmaları gönderilmeyecek"
            in str(call.args[0])
            for call in app._log.call_args_list
        ))

    def test_chunk_retry_stops_after_provider_model_channel_error(self):
        class ChannelError(RuntimeError):
            status_code = 503

        app = gui.App.__new__(gui.App)
        app._stop_flag = False
        app._log = MagicMock()
        app._json_repair_pass = MagicMock()
        app._resend_missing_blocks = MagicMock()
        request = {
            "custom_id": "chunk_1",
            "body": {
                "model": "gpt-5.4",
                "messages": [
                    {"role": "system", "content": "translate"},
                    {"role": "user", "content": '{"tr":[{"i":1,"t":"Hello"}]}'},
                ],
            },
        }

        with patch(
            "subtitle_translator_gui._safe_chat_create",
            side_effect=ChannelError(
                "Error code: 503 - model_not_found: No available channel for "
                "model gpt-5.4 under group auto"
            ),
        ) as create:
            unresolved = app._retry_hata(
                client=object(),
                raw_map={},
                requests_list=[request],
                max_rounds=3,
            )

        self.assertEqual(create.call_count, 1)
        self.assertEqual(unresolved, {"chunk_1"})
        app._resend_missing_blocks.assert_not_called()
        self.assertTrue(any(
            "model kanalı yok" in str(call.args[0])
            for call in app._log.call_args_list
        ))

    def test_partial_output_path_never_overwrites_final(self):
        self.assertEqual(
            gui._partial_output_path(r"C:\out\episode.srt"),
            gui.Path(r"C:\out\episode.partial.srt"),
        )

    def test_incomplete_existing_final_is_quarantined_outside_srt_set(self):
        with TemporaryDirectory() as root:
            final = gui.Path(root, "episode.srt")
            final.write_text("[ÇEVİRİ EKSİK]", encoding="utf-8")

            quarantined = gui._quarantine_incomplete_final(final)

            self.assertFalse(final.exists())
            self.assertEqual(quarantined.suffix, ".bak")
            self.assertEqual(
                quarantined.read_text(encoding="utf-8"),
                "[ÇEVİRİ EKSİK]",
            )

    def test_delivery_credits_and_dropped_sfx_do_not_force_retranslation(self):
        source = [
            SimpleNamespace(index=1, text="Hello."),
            SimpleNamespace(index=2, text="[door closes]"),
            SimpleNamespace(index=3, text="Goodbye."),
        ]
        output = [
            ("0", "00:00:00,000 --> 00:00:00,999", "discord: ceviri2"),
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba."),
            ("3", "00:00:03,000 --> 00:00:04,000", "Hoşça kal."),
            ("4", "00:00:04,001 --> 00:00:06,001", "discord: ceviri2"),
        ]

        self.assertTrue(gui._existing_output_is_complete(output, source))

    def test_existing_output_with_missing_dialogue_is_not_complete(self):
        source = [
            SimpleNamespace(index=1, text="Hello."),
            SimpleNamespace(index=2, text="Where are you?"),
        ]
        output = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Merhaba."),
        ]

        self.assertFalse(gui._existing_output_is_complete(output, source))


if __name__ == "__main__":
    unittest.main()
