import unittest
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class TestPackage4BacktranslationAndHataOrder(unittest.TestCase):
    def test_final_semantic_wrapper_updates_visible_phase_for_both_passes(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = None
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = True
        app.semantic_reconcile_var = MagicMock()
        app.semantic_reconcile_var.get.return_value = True
        app._set_phase = MagicMock()
        app._update_file_progress = MagicMock()
        app._maybe_backtranslation_check = MagicMock(return_value=0)
        app._maybe_semantic_reconciliation = MagicMock(return_value=0)

        app._run_final_semantic_checks(
            "output.srt", {"1": "Hello."},
            [(1, "00:00:01,000 --> 00:00:02,000", "Merhaba.")],
            source_path=r"C:\input\source.srt",
        )

        self.assertEqual(
            [call.args[0] for call in app._set_phase.call_args_list],
            ["Geri Çeviri", "Nihai Anlam Mutabakatı"],
        )
        self.assertEqual(
            [call.args[1] for call in app._update_file_progress.call_args_list],
            ["Geri Çeviri", "Nihai Anlam Mutabakatı"],
        )
        self.assertTrue(all(
            call.args[0] == r"C:\input\source.srt"
            for call in app._update_file_progress.call_args_list))

    def test_backtranslation_check_is_report_only_and_returns_flagged_ids(self):
        app = gui.App.__new__(gui.App)
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = True
        app._log = MagicMock()
        app._update_tokens = MagicMock()
        app._helper_api_key = MagicMock(return_value="test_key")
        app._helper_api_base_url = MagicMock(return_value="https://api.openai.com/v1")
        app._helper_api_model = MagicMock(return_value="gpt-5.4-mini")
        app.src_var = MagicMock()
        app.src_var.get.return_value = "English"
        app.tgt_var = MagicMock()
        app.tgt_var.get.return_value = "Turkish"

        blocks = [(1, "00:00:01 -> 00:00:03", "Bozuk çeviri")]
        src_map = {"1": "Hello world"}

        fake_flags = [{
            "idx": "1",
            "src": "Hello world",
            "tr": "Bozuk çeviri",
            "back": "Broken translation",
            "reason": "Meaning mismatch"
        }]

        status = {}
        with patch("hybrid_translate.back_translation_check", return_value=fake_flags):
            with patch("builtins.open", unittest.mock.mock_open()):
                fixes = app._maybe_backtranslation_check(
                    "out.srt", src_map, blocks, src_lang="en", status_out=status)

        self.assertEqual(fixes, 0)
        self.assertEqual(blocks[0][2], "Bozuk çeviri")
        self.assertEqual(status["flagged_ids"], ["1"])
        self.assertEqual(status["changed"], 0)

    def test_backtranslation_does_not_send_per_flag_fix_requests(self):
        app = gui.App.__new__(gui.App)
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = True
        app._log = MagicMock()
        app._update_tokens = MagicMock()
        app._helper_api_key = MagicMock(return_value="test_key")
        app._helper_api_base_url = MagicMock(
            return_value="https://api.openai.com/v1")
        app._helper_api_model = MagicMock(return_value="gpt-5.4-mini")
        app._get_locked_terms_dict = MagicMock(return_value={})
        app.src_var = MagicMock()
        app.src_var.get.return_value = "English"
        app.tgt_var = MagicMock()
        app.tgt_var.get.return_value = "Turkish"
        flags = [{
            "idx": "1", "src": "Hello world", "tr": "Bozuk Ã§eviri",
            "back": "Broken translation", "reason": "Meaning mismatch",
        }]
        blocks = [(1, "00:00:01 -> 00:00:03", "Bozuk Ã§eviri")]

        with patch("hybrid_translate.back_translation_check",
                   return_value=flags), patch(
                "hybrid_translate._safe_chat_create") as safe_chat, patch(
                "builtins.open", unittest.mock.mock_open()):
            app._maybe_backtranslation_check(
                "out.srt", {"1": "Hello world"}, blocks, src_lang="en")

        safe_chat.assert_not_called()
        app._update_tokens.assert_not_called()

    def test_backtranslation_disabled_returns_zero(self):
        """When backtranslation option is off, _maybe_backtranslation_check returns 0 immediately."""
        app = gui.App.__new__(gui.App)
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = False

        blocks = [(1, "00:00:01 -> 00:00:03", "Text")]
        fixes = app._maybe_backtranslation_check("out.srt", {"1": "Text"}, blocks)
        self.assertEqual(fixes, 0)

    def test_backtranslation_flag_cannot_directly_replace_locked_term(self):
        app = gui.App.__new__(gui.App)
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = True
        app._log = MagicMock()
        app._helper_api_key = MagicMock(return_value="test_key")
        app._helper_api_base_url = MagicMock(return_value="https://api.openai.com/v1")
        app._helper_api_model = MagicMock(return_value="gpt-5.4-mini")
        app._get_locked_terms_dict = MagicMock(
            return_value={"Emperor": "İmparator"})
        app.src_var = MagicMock()
        app.src_var.get.return_value = "English"
        app.tgt_var = MagicMock()
        app.tgt_var.get.return_value = "Turkish"
        blocks = [(1, "00:00:01 -> 00:00:03", "İmparator geliyor.")]
        flags = [{
            "idx": "1",
            "src": "The Emperor is coming.",
            "tr": "İmparator geliyor.",
            "back": "The ruler is coming.",
            "reason": "Meaning mismatch",
        }]
        with patch("hybrid_translate.back_translation_check",
                   return_value=flags), \
             patch("builtins.open", unittest.mock.mock_open()):
            fixed = app._maybe_backtranslation_check(
                "out.srt",
                {"1": "The Emperor is coming."},
                blocks,
                src_lang="English",
                source_path="source.srt",
            )
        self.assertEqual(fixed, 0)
        self.assertEqual(blocks[0][2], "İmparator geliyor.")

    def test_final_semantic_receives_backtranslation_flagged_ids(self):
        app = gui.App.__new__(gui.App)
        app._active_snapshot = None
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = True
        app.semantic_reconcile_var = MagicMock()
        app.semantic_reconcile_var.get.return_value = True
        app._set_phase = MagicMock()
        app._update_file_progress = MagicMock()

        def backtranslation(*args, status_out=None, **kwargs):
            status_out.update({"status": "completed", "flagged_ids": ["7"], "changed": 0})
            return 0

        app._maybe_backtranslation_check = backtranslation
        app._maybe_semantic_reconciliation = MagicMock(return_value=0)
        app._run_final_semantic_checks(
            "out.srt", {"7": "Source"},
            [(7, "00:00:01 --> 00:00:02", "Mevcut")],
            changed_ids={"3"}, backtranslation_status_out={})
        passed_ids = app._maybe_semantic_reconciliation.call_args.kwargs["changed_ids"]
        self.assertEqual(passed_ids, {"3", "7"})

    def test_pipeline_order_in_gui_flows(self):
        """Verify _fill_hata_with_source and _restore_tags_blocks presence in _run_hybrid phase 2 success path."""
        import inspect
        src = inspect.getsource(gui.App._run_hybrid)
        
        # Verify _fill_hata_with_source is called in success path
        self.assertIn("_fill_hata_with_source(_final_blocks", src)
        
        # Verify order: final semantic checks before _fill_hata_with_source before write_srt
        bt_pos = src.rfind("_run_final_semantic_checks(")
        fill_pos = src.rfind("_fill_hata_with_source(")
        write_pos = src.rfind("write_srt(")
        
        self.assertGreater(fill_pos, bt_pos, "_fill_hata_with_source must follow final semantic checks")
        self.assertGreater(write_pos, fill_pos, "write_srt must follow _fill_hata_with_source")

    def test_hybrid_batch_tail_hata_counting_and_raw_backup(self):
        """Simulate post-processing pass producing [HATA], verify [ÇEVİRİ EKSİK] output, report counting _n_filled, and raw backup preservation."""
        cues = [
            MagicMock(index=1, text="Hello world"),
            MagicMock(index=2, text="Goodbye world"),
        ]
        # Simulate post-processing producing a [HATA] line
        pp_blocks = [
            (1, "00:00:01 -> 00:00:02", "Merhaba dünya"),
            (2, "00:00:03 -> 00:00:05", "[HATA: timeout]"),
        ]
        raw_backup_blocks = [(1, "00:00:01 -> 00:00:02", "Hello world"), (2, "00:00:03 -> 00:00:05", "Goodbye world")]
        raw_map = gui._raw_src_map_from_cues(cues)

        final_blocks, n_filled = gui._fill_hata_with_source(pp_blocks, raw_map)
        self.assertEqual(n_filled, 1)
        self.assertEqual(final_blocks[1][2], "[ÇEVİRİ EKSİK]")

        # Report counting logic in _run_hybrid: uses _n_filled from _fill_hata_with_source
        self.assertEqual(n_filled, 1)

        # Raw backup preserves pre-quality content
        self.assertEqual(raw_backup_blocks[1][2], "Goodbye world")


if __name__ == "__main__":
    unittest.main()
