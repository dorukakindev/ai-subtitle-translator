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

    def test_parenthetical_narrative_prose_is_not_sdh_only(self):
        self.assertFalse(gui._src_is_sdh_only(
            "(son of dońa Delores Mendizábal, an\n"
            "illustrious and wealthy lady from Havana)"
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

    def test_completed_preflight_does_not_clear_retranslate_choice(self):
        app = gui.App.__new__(gui.App)
        app._force_retranslate_paths = {gui.App._norm_path(app, "movie.srt")}
        app._file_integrity_preflight_done = True
        app._file_integrity_preflight_signature = ("same",)
        app._file_preflight_signature = lambda _files: ("same",)

        started = gui.App._start_file_integrity_preflight(app, ["movie.srt"])

        self.assertFalse(started)
        self.assertEqual(
            app._force_retranslate_paths,
            {gui.App._norm_path(app, "movie.srt")},
        )


class PermanentQuotaFailureTest(unittest.TestCase):
    def test_repair_handles_visible_missing_translation_marker(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]")]
        raw = {"1": "Where are you?"}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":"1","t":"Neredesin?"}]'))],
            usage=None,
        )

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish")

        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "Neredesin?")

    def test_repair_injects_and_enforces_locked_terms(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        raw = {"1": "Biotechnology Supply Laboratory is closed."}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":"1","t":"Biyoteknoloji Sağlama Laboratuvarı kapalı."}]'))],
            usage=None,
        )
        locked = {
            "Biotechnology Supply Laboratory":
            "Biyoteknoloji Tedarik Laboratuvarı",
        }
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", locked_terms=locked, retry_delays=())
        payload = __import__("json").loads(
            create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(payload["glossary"], locked)
        self.assertEqual(repaired, 0)
        self.assertEqual(result[0][2], "[HATA]")

    def test_repair_uses_rich_prompt_and_neighbor_context(self):
        blocks = [("2", "00:00:02,000 --> 00:00:03,000", "[HATA]")]
        raw = {"1": "Before.", "2": "Missing line.", "3": "After."}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":"2","t":"Eksik satır."}]'))],
            usage=None,
        )
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", system_prompt="RICH FILE CONTEXT")

        messages = create.call_args.kwargs["messages"]
        payload = __import__("json").loads(messages[1]["content"])
        self.assertEqual(messages[0]["content"], "RICH FILE CONTEXT")
        self.assertEqual(payload["ctx"], ["Before."])
        self.assertEqual(payload["next_ctx"], ["After."])
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "Eksik satır.")

    def test_repair_rejects_duplicate_and_malformed_response_ids(self):
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "[HATA]"),
            (2, "00:00:02,000 --> 00:00:03,000", "[HATA]"),
            (3, "00:00:03,000 --> 00:00:04,000", "[HATA]"),
        ]
        raw = {"1": "First source.", "2": "Second source.", "3": "Third source."}
        payload = [
            {"i": "1", "t": "Birinci."},
            {"i": 1, "t": "Çelişkili birinci."},
            {"i": "2", "t": "İkinci."},
            {"i": "3", "t": 123},
            {"i": "999", "t": "Küme dışı."},
        ]
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content=__import__("json").dumps(payload, ensure_ascii=False)))],
            usage=None,
        )
        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response):
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", retry_delays=())
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "[HATA]")
        self.assertEqual(result[1][2], "İkinci.")
        self.assertEqual(result[2][2], "[HATA]")

    def test_repair_retries_ids_missing_from_an_otherwise_valid_response(self):
        blocks = [
            (1, "00:00:01,000 --> 00:00:02,000", "[HATA]"),
            (2, "00:00:02,000 --> 00:00:03,000", "[HATA]"),
        ]
        raw = {"1": "First source.", "2": "Second source."}
        responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content='[{"i":"1","t":"Birinci kaynak."}]'))],
                usage=None,
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content='[{"i":"2","t":"İkinci kaynak."}]'))],
                usage=None,
            ),
        ]

        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=responses) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", retry_delays=(0,))

        self.assertEqual(create.call_count, 2)
        self.assertEqual(repaired, 2)
        self.assertEqual([text for _idx, _ts, text in result], [
            "Birinci kaynak.", "İkinci kaynak.",
        ])

    def test_repair_rejects_foreign_leak_then_accepts_clean_retry(self):
        blocks = [(1, "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        raw = {"1": "I told the girl."}
        responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content='[{"i":"1","t":"Mädchen’e söyledim."}]'))],
                usage=None,
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content='[{"i":"1","t":"Kıza söyledim."}]'))],
                usage=None,
            ),
        ]

        with patch("subtitle_translator_gui._safe_chat_create",
                   side_effect=responses) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", retry_delays=(0,))

        self.assertEqual(create.call_count, 2)
        self.assertEqual(repaired, 1)
        self.assertEqual(result[0][2], "Kıza söyledim.")

    def test_unresolved_mixed_source_line_is_quarantined(self):
        blocks = [(
            982,
            "01:03:08,000 --> 01:03:10,000",
            "The Krauss couple dün kendi dairelerinde asıldı.",
        )]
        raw = {"982": "The Krauss couple were hung yesterday in their own flat."}
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content='[{"i":"982","t":"The Krauss couple dün kendi dairelerinde asıldı."}]'))],
            usage=None,
        )

        with patch("subtitle_translator_gui._safe_chat_create",
                   return_value=response) as create:
            result, repaired = gui._repair_untranslated_sync(
                blocks, raw, client=object(), src_lang="English",
                tgt_lang="Turkish", retry_delays=(0,))

        self.assertEqual(create.call_count, 2)
        self.assertEqual(repaired, 0)
        self.assertEqual(result[0][2], "[ÇEVİRİ EKSİK]")

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
        permanent = MagicMock()

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
                permanent_failure_cb=permanent,
            )

        self.assertEqual(create.call_count, 1)
        self.assertEqual(repaired, 0)
        self.assertEqual(result, blocks)
        permanent.assert_called_once_with()
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
        self.assertTrue(app._auto_retry_blocked_by_permanent_provider)
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
            gui.Path(r"C:\out\Raporlar\Kurtarma\episode.partial.srt"),
        )

    def test_stage_move_creates_nested_recovery_directory(self):
        with TemporaryDirectory() as tmp:
            root = gui.Path(tmp)
            stage = root / ".episode.stage.srt"
            final = root / "episode.srt"
            stage.write_text("partial", encoding="utf-8")

            partial = gui._move_stage_to_partial(stage, final)

            self.assertEqual(
                partial, root / "Raporlar" / "Kurtarma" / "episode.partial.srt")
            self.assertEqual(partial.read_text(encoding="utf-8"), "partial")
            self.assertFalse(stage.exists())

    def test_incomplete_existing_final_is_quarantined_outside_srt_set(self):
        with TemporaryDirectory() as root:
            final = gui.Path(root, "episode.srt")
            final.write_text("[ÇEVİRİ EKSİK]", encoding="utf-8")

            quarantined = gui._quarantine_incomplete_final(final)

            self.assertFalse(final.exists())
            self.assertEqual(quarantined.suffix, ".bak")
            self.assertEqual(quarantined.parent.name, "Kurtarma")
            self.assertEqual(quarantined.parent.parent.name, "Raporlar")
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

    def test_broad_output_across_scene_gap_is_not_complete(self):
        source = [
            ("1", "00:00:01,000 --> 00:00:02,000", "First."),
            ("2", "00:00:10,000 --> 00:00:11,000", "Second."),
        ]
        output = [
            ("1", "00:00:01,000 --> 00:00:11,000", "Only first."),
        ]
        self.assertFalse(gui._existing_output_is_complete(output, source))

    def test_legitimate_fragment_merge_is_complete(self):
        source = [
            ("1", "00:00:01,000 --> 00:00:02,000", "I do"),
            ("2", "00:00:02,100 --> 00:00:03,000", "not know."),
        ]
        output = [
            ("1", "00:00:01,000 --> 00:00:03,000", "Bilmiyorum."),
        ]
        self.assertTrue(gui._existing_output_is_complete(output, source))

    def test_user_retranslate_choice_overrides_hybrid_complete_skip(self):
        source_path = r"C:\input\film.srt"
        source = [SimpleNamespace(index=1, text="Hello.")]
        output = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba.")]

        self.assertTrue(gui._should_skip_existing_output(
            source_path, output, source, force_retranslate_paths=()))
        self.assertFalse(gui._should_skip_existing_output(
            source_path, output, source,
            force_retranslate_paths={r"c:\INPUT\FILM.srt"}))


if __name__ == "__main__":
    unittest.main()
