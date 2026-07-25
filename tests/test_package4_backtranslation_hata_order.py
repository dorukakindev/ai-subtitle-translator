import unittest
from unittest.mock import MagicMock, patch

import subtitle_translator_gui as gui


class TestPackage4BacktranslationAndHataOrder(unittest.TestCase):
    def test_backtranslation_check_returns_int_and_modifies_blocks(self):
        """_maybe_backtranslation_check returns integer fix count and modifies blocks in-place."""
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

        with patch("hybrid_translate.back_translation_check", return_value=fake_flags), \
             patch("hybrid_translate._safe_chat_create") as mock_chat, \
             patch("hybrid_translate.validate_polish_candidate", return_value=(True, "")):
            
            mock_choice = MagicMock()
            mock_choice.message.content = "Merhaba dünya"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_chat.return_value = mock_resp

            with patch("builtins.open", unittest.mock.mock_open()):
                fixes = app._maybe_backtranslation_check("out.srt", src_map, blocks, src_lang="en")

        self.assertEqual(fixes, 1)
        self.assertEqual(blocks[0][2], "Merhaba dünya")

    def test_backtranslation_disabled_returns_zero(self):
        """When backtranslation option is off, _maybe_backtranslation_check returns 0 immediately."""
        app = gui.App.__new__(gui.App)
        app.backtrans_var = MagicMock()
        app.backtrans_var.get.return_value = False

        blocks = [(1, "00:00:01 -> 00:00:03", "Text")]
        fixes = app._maybe_backtranslation_check("out.srt", {"1": "Text"}, blocks)
        self.assertEqual(fixes, 0)

    def test_pipeline_order_in_gui_flows(self):
        """Verify _fill_hata_with_source and _restore_tags_blocks presence in _run_hybrid phase 2 success path."""
        import inspect
        src = inspect.getsource(gui.App._run_hybrid)
        
        # Verify _fill_hata_with_source is called in success path
        self.assertIn("_fill_hata_with_source(_final_blocks", src)
        
        # Verify order: _maybe_backtranslation_check before _fill_hata_with_source before write_srt
        bt_pos = src.rfind("_maybe_backtranslation_check(")
        fill_pos = src.rfind("_fill_hata_with_source(")
        write_pos = src.rfind("write_srt(")
        
        self.assertGreater(fill_pos, bt_pos, "_fill_hata_with_source must follow _maybe_backtranslation_check")
        self.assertGreater(write_pos, fill_pos, "write_srt must follow _fill_hata_with_source")


if __name__ == "__main__":
    unittest.main()
