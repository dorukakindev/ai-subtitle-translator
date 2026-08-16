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
        self.assertEqual(audit["residual_sdh_ids"], ["1"])
        self.assertIn({
            "reason": "residual_sdh",
            "source_id": "",
            "output_id": "1",
            "source": "(MEN SPEAKING SPANISH QUIETLY)",
            "target": "Adamlar İspanyolca alçak sesle sohbet ediyor",
        }, audit["review_details"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_dialogue_shifted_into_sdh_timestamp_is_not_accepted(self):
        audit = self._audit("(SINGING, DRUM BEATING)",
                            "Hollywood, Sebe'yi bir seks tanrıçasına çevirdi,")
        self.assertEqual(audit["residual_sdh_cues"], 1)
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_normal_dialogue_source_is_not_sdh(self):
        audit = self._audit("He cries every night.", "Her gece ağlar.")
        self.assertEqual(audit["residual_sdh_cues"], 0)
        self.assertEqual(audit["residual_sdh_ids"], [])

    def test_standalone_proper_name_is_not_untranslated_fragment(self):
        audit = self._audit("James haywood...", "James Haywood...")
        self.assertEqual(audit["untranslated_fragment_ids"], [])

    def test_repeated_inline_object_term_is_not_untranslated_fragment(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Üzeriniz kazınıyor,\nstrigil..."),
            ("2", "00:00:02,100 --> 00:00:03,000", "Strigil kullanılır."),
        ]
        source_map = {
            "1": "You get strigiled off,\nstrigil...",
            "2": "Use the strigil.",
        }
        self.assertEqual(
            gui._delivery_untranslated_fragment_ids(
                blocks, source_map, source_language="English"),
            [])

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
                "HE CHANTS IN GE'EZ LANGUAGE", "HE BLOWS HORN", "UH!"):
            with self.subTest(source_text=source_text):
                self.assertTrue(
                    gui._source_cue_is_delivery_removable(source_text))

    def test_bare_live_log_sdh_descriptors_are_removable(self):
        for source_text in (
                "BABY CRIES", "MAN SINGS", "HE SINGS PLAINSONG",
                "CHEERING", "SINGING CONTINUES", "SINGING ENDS",
                "ELECTRONIC DANCE MUSIC PLAYS", "HE PLAYS A NOTE",
                "HE PLAYS THE NOTE ON THE MOUTH ORGAN",
                "VOICES GRADUALLY RISE\nIN A LOUD CRESCENDO",
                "[NON-ENGLISH SPEECH]", "NGAKPA: [NON-ENGLISH SPEECH]",
                "STANDCHEN: [NON-ENGLISH SPEECH]"):
            with self.subTest(source_text=source_text):
                self.assertTrue(
                    gui._source_cue_is_delivery_removable(source_text))

    def test_arabic_academic_lower_third_is_removable(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            '"البروفيسور (أندرو تيفيرسون)\nجامعة (كينغستون)"'))
        self.assertTrue(gui._source_cue_is_delivery_removable(
            '"د. (ليز غلوين)\nكلية (لندن)"'))
        self.assertTrue(gui._source_cue_is_delivery_removable(
            '"بروفسور (ديان بوركيس)\nكلية (كيبل)، (أوكسفورد)"'))

    def test_arabic_author_title_card_is_removable(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            '"(دراكولا)\nتأليف (برام ستوكر)"'))

    def test_arabic_dialogue_about_university_is_not_removable(self):
        self.assertFalse(gui._source_cue_is_delivery_removable(
            "قال البروفيسور إنه عاد إلى الجامعة."))

    def test_parenthesized_arabic_dialogue_is_not_sdh(self):
        self.assertFalse(gui._source_cue_is_delivery_removable(
            "(لا يمكننا مخالفة الآلهة.)"))
        self.assertFalse(gui._source_cue_is_delivery_removable("(اعتقلوهم!)"))
        self.assertFalse(gui._source_cue_is_delivery_removable("(أرجوك، ماء.)"))

    def test_delivery_log_details_include_reason_id_and_source(self):
        lines = gui._delivery_audit_log_details({
            "review_details": [{
                "reason": "missing_dialogue",
                "source_id": "250",
                "source": "for women.",
            }],
        })
        self.assertEqual(
            lines,
            ["Teslim denetimi ayrıntısı [missing_dialogue] #250: "
             "kaynak='for women.'"])

    def test_delivery_log_uses_output_id_and_prints_target(self):
        lines = gui._delivery_audit_log_details({
            "review_details": [{
                "reason": "residual_sdh",
                "output_id": "84",
                "source": "(SPEAKING GEORGIAN)",
                "target": "Gürcüce konuşuluyor",
            }],
        })
        self.assertEqual(
            lines,
            ["Teslim denetimi ayrıntısı [residual_sdh] #84: "
             "kaynak='(SPEAKING GEORGIAN)' | çıktı='Gürcüce konuşuluyor'"])


if __name__ == "__main__":
    unittest.main()
