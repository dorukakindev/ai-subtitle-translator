"""
apply_line_breaks per-blok satır bütçesi testleri (EBU: ≤ _MAX_LINES).
Bug (round 14): satır kırma kaynak-satır başına uygulanınca 2-satır blok 4-6
satıra çıkıp standardı ihlal ediyordu.
"""
import unittest
from unittest.mock import patch

import subtitle_translator_gui as gui

LONG = "Bu cümle gerçekten çok uzun ve ekrana sığması için bölünmesi gereken bir metin"


def _nlines(block_text):
    return block_text.count("\n") + 1


class ApplyLineBreaksBudgetTest(unittest.TestCase):
    def test_two_long_lines_capped_at_max(self):
        out = gui.apply_line_breaks([("1", "ts", LONG + "\n" + LONG)])
        self.assertLessEqual(_nlines(out[0][2]), gui._MAX_LINES)

    def test_single_long_line_still_split(self):
        out = gui.apply_line_breaks([("1", "ts", LONG)])
        self.assertGreaterEqual(_nlines(out[0][2]), 2)
        self.assertLessEqual(_nlines(out[0][2]), gui._MAX_LINES)

    def test_short_line_untouched(self):
        out = gui.apply_line_breaks([("1", "ts", "Kısa satır.")])
        self.assertEqual(out[0][2], "Kısa satır.")

    def test_already_at_max_lines_preserved(self):
        # Zaten _MAX_LINES satır → model'in kırmasına saygı, daha fazla bölme
        src = "\n".join([LONG] * gui._MAX_LINES)
        out = gui.apply_line_breaks([("1", "ts", src)])
        self.assertEqual(_nlines(out[0][2]), gui._MAX_LINES)

    def test_no_text_loss(self):
        # Bölme metni kaybetmemeli (boşluklar normalize, kelimeler korunur)
        out = gui.apply_line_breaks([("1", "ts", LONG)])
        self.assertEqual(out[0][2].replace("\n", " ").split(), LONG.split())

    def test_block_count_preserved(self):
        blocks = [("1", "ts", LONG), ("2", "ts", "Kısa."), ("3", "ts", LONG + "\n" + LONG)]
        out = gui.apply_line_breaks(blocks)
        self.assertEqual(len(out), 3)
        self.assertEqual([b[0] for b in out], ["1", "2", "3"])


class CondenseThresholdTest(unittest.TestCase):
    def test_gui_condense_uses_quality_target_21_cps(self):
        calls = []

        class Flag:
            def get(self):
                return True

        class DummyApp:
            condense_var = Flag()
            quality_report_only_var = type("Off", (), {"get": lambda self: False})()

            def _set_status(self, *_args, **_kwargs):
                pass

            def _log(self, *_args, **_kwargs):
                pass

            def _log_exc(self, *_args, **_kwargs):
                pass

            def _update_tokens(self, *_args, **_kwargs):
                pass

        def fake_condense_fast_lines(**kwargs):
            calls.append(kwargs)
            return kwargs["tr_blocks"], 0

        blocks = [("1", "00:00:00,000 --> 00:00:01,000", "Çok uzun bir satır.")]
        app = DummyApp()
        app._active_snapshot = {"quality_report_only": False}
        with patch("hybrid_translate.condense_fast_lines", side_effect=fake_condense_fast_lines):
            gui.App._maybe_condense(app, blocks, "key", "url", "model", "Turkish")

        self.assertEqual(calls[0]["cps_limit"], 21.0)


if __name__ == "__main__":
    unittest.main()
