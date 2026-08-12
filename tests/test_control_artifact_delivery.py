import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui
from subtitle_formats import normalize_subtitle_control_artifacts


class ControlArtifactDeliveryTest(unittest.TestCase):
    def test_repairs_model_emitted_nul_hex_artifacts(self):
        self.assertEqual(
            normalize_subtitle_control_artifacts("Caf\x00e9 H\x00fck\x00fcmet"),
            "Café Hükümet",
        )

    def test_writer_never_serializes_c0_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.srt"
            gui.write_srt(path, [("1", "00:00:01,000 --> 00:00:02,000",
                                  "Caf\x00e9\x01test")])
            text = path.read_text(encoding="utf-8-sig")
        self.assertIn("Café test", text)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x01", text)

    def test_delivery_audit_rejects_existing_control_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            output = Path(tmp) / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n",
                encoding="utf-8",
            )
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\nMer\x00haba\n\n",
                encoding="utf-8",
            )
            audit = gui._subtitle_delivery_audit(source, output)
        self.assertEqual(audit["residual_control_chars"], 1)
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))


if __name__ == "__main__":
    unittest.main()
