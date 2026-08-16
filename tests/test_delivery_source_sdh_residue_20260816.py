import tempfile
import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class DeliverySourceSdhResidueTest(unittest.TestCase):
    def _audit(self, source_text, output_text):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.srt"
            output = root / "output.srt"
            source.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n" + source_text + "\n",
                encoding="utf-8")
            output.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n" + output_text + "\n",
                encoding="utf-8")
            return gui._subtitle_delivery_audit(
                str(source), str(output), source_language="English")

    def test_translated_bare_sdh_at_source_timestamp_is_residual(self):
        audit = self._audit("(MEN SPEAKING SPANISH QUIETLY)",
                            "Adamlar İspanyolca alçak sesle sohbet ediyor")
        self.assertEqual(audit["residual_sdh_cues"], 1)
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_dialogue_shifted_into_sdh_timestamp_is_not_accepted(self):
        audit = self._audit("(SINGING, DRUM BEATING)",
                            "Hollywood, Sebe'yi bir seks tanrıçasına çevirdi,")
        self.assertEqual(audit["residual_sdh_cues"], 1)
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_normal_dialogue_source_is_not_sdh(self):
        audit = self._audit("He cries every night.", "Her gece ağlar.")
        self.assertEqual(audit["residual_sdh_cues"], 0)

    def test_documentary_action_descriptors_are_removable(self):
        for source_text in (
                "(Ghostly wail)", "(Birds squawk)",
                "(Man reading Nahuatl poem)",
                "(Men chatting quietly in Spanish)",
                "(Men chatting quietly)", "(Big Ben chimes)",
                "(KeSSIS ReADS)", "(GREETINGS IN LOCAL LANGUAGE)",
                "(COCKEREL CROWS)", "(SPEAKING IN GEORGIAN)",
                "(SPEAKS CORNISH)", "HE SPEAKS GREEK",
                "THE SPEAK IN TONGUES", "SHE CRIES",
                "MUEZZIN CHANTS", "DRUM RHYTHMS AND CHANTING",
                "LOUD DRUMMING", "GOSPEL SINGING",
                "THE SINGING CONTINUES", "HE SINGS IN ARABIC",
                "BELLS RING, DRUMS BEAT", "THEY CHANT AND DRUM",
                "HE CHANTS IN GE'EZ LANGUAGE", "HE BLOWS HORN"):
            with self.subTest(source_text=source_text):
                self.assertTrue(
                    gui._source_cue_is_delivery_removable(source_text))


if __name__ == "__main__":
    unittest.main()
