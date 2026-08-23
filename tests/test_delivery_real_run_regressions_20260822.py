import tempfile
import unittest
from pathlib import Path

import sdh_cleaner as sdh
import subtitle_translator_gui as gui


class DeliveryRealRunRegressionsTest(unittest.TestCase):
    def test_english_surgeon_bare_sdh_labels_are_strongly_removable(self):
        labels = (
            "GREETINGS IN UKRAINIAN", "HE STARTS MACHINERY", "A BELL PEALS",
            "WOMAN SPEAKS IN UKRAINIAN", "CONGREGATION SINGS", "DRILLING",
            "STATION ANNOUNCEMENT", "MUSICAL INTRO PLAYS", "IGOR TRANSLATES",
            "SHE ASKS A QUESTION", "MOBILE PHONES RING", "LIFT RUMBLES",
            "HENRY LAUGHS", "CAMERA CLICKS", "HENRY MUMBLES",
            "DRILL SLOWS FURTHER", "DRILLING STOPS", "SUCKING NOISE",
            "HISS OF AIR", "LOUD DRILLING", "CRACKLING", "INAUDIBLE",
            "THEY SPEAK IN UKRAINIAN", "THEY MAKE TOASTS",
            "HE SPEAKS UKRAINIAN",
        )
        for value in labels:
            with self.subTest(value=value):
                self.assertTrue(gui._source_cue_is_delivery_removable(value))

    def test_html_wrapped_and_hash_only_sdh_sources_are_removed(self):
        cases = (
            ("<i>[Cup Clatters]</i>", "<i>[Cup Clatters]</i>"),
            ("<i>[Boys Shouting, Arguing]</i>",
             "<i>[Boys Shouting, Arguing]</i>"),
            ("[Stomps Ice Puddle]", "[Stomps Ice Puddle]"),
            ("[Gasping, Pounding On Floor]",
             "[Gasping, Pounding On Floor]"),
            ("[Susan Pounding On Floor]", "[Susan Pounding On Floor]"),
            ("## [Continues, Indistinct]", "##"),
            ("- [Chattering]\n- ## [Singing]", "- ##"),
        )
        for source, target in cases:
            with self.subTest(source=source):
                self.assertTrue(sdh.src_is_sfx_only(source))
                self.assertEqual(
                    sdh.clean_sdh_blocks(
                        [("1", "00:00:01,000 --> 00:00:02,000", target)],
                        src_map={"1": source}, source_driven=True),
                    [],
                )

    def test_real_mixed_warrendale_labels_are_stripped(self):
        cases = (
            ("<i>- Turn around.\n- [Woman On Radio]... metro area.</i>",
             "<i>- Dön.\n- [Woman On Radio]... şehir bölgesi.</i>",
             "<i>- Dön.\n- ... şehir bölgesi.</i>"),
            ("<i>- Thank you, Davey.\n- [Blows Nose]</i>",
             "<i>- Teşekkürler, Davey.\n- [Blows Nose]</i>",
             "<i>- Teşekkürler, Davey.</i>"),
            ("- Good morning.\n- [Girl, Muffled] Fuck off.",
             "- Günaydın.\n- [Girl, Muffled] Siktir git.",
             "- Günaydın.\n- Siktir git."),
            ("<i>- It's all right.\n- [Footsteps Approaching]</i>",
             "<i>- Tamam.\n- [Footsteps Approaching]</i>",
             "<i>- Tamam.</i>"),
        )
        for source, target, expected in cases:
            with self.subTest(source=source):
                result = sdh.clean_sdh_blocks(
                    [("1", "00:00:01,000 --> 00:00:02,000", target)],
                    src_map={"1": source}, source_driven=True)
                self.assertEqual(result[0][2], expected)

    def test_repeated_hey_is_a_valid_unchanged_interjection(self):
        value = "Hey, hey. Hey, hey, hey, hey."
        self.assertEqual(gui._untranslated_reason(value, value), "")

    def test_repeated_at_and_hash_placeholders_are_removable(self):
        for value in ("@@@@@", "#####"):
            with self.subTest(value=value):
                self.assertTrue(gui._source_cue_is_delivery_removable(value))

    def test_offscreen_plain_speaker_labels_are_stripped(self):
        cases = (
            ("MALE SPEAKER (OFFSCREEN): Not lately.",
             "MALE SPEAKER: Son zamanlarda hayır.", "Son zamanlarda hayır."),
            ("MARJOE'S MOTHER (OFFSCREEN): Listen.",
             "MARJOE'NUN ANNESİ: Dinleyin.", "Dinleyin."),
            ("CONGREGANT (OFFSCREEN):\nThank you, loving God.",
             "CEMAAT ÜYESİ:\nTeşekkürler, sevgi dolu Tanrı.",
             "Teşekkürler, sevgi dolu Tanrı."),
        )
        for source, target, expected in cases:
            with self.subTest(source=source):
                result = sdh.clean_sdh_blocks(
                    [("1", "00:00:01,000 --> 00:00:02,000", target)],
                    src_map={"1": source}, source_driven=True)
                self.assertEqual(result[0][2], expected)

    def test_punctuated_sdh_only_source_is_removable(self):
        for value in ("[speaking in tongues].", "[inaudible]."):
            with self.subTest(value=value):
                self.assertTrue(sdh.src_is_sfx_only(value))
                self.assertTrue(gui._source_cue_is_delivery_removable(value))

    def test_speaker_prefix_does_not_create_semantic_loss_false_positive(self):
        source = {"1": "MALE SPEAKER (OFFSCREEN): Two."}
        self.assertEqual(
            gui._delivery_semantic_loss_ids(
                [("1", "00:00:01,000 --> 00:00:02,000", "İki.")], source),
            [],
        )

    def test_turkish_kinship_words_do_not_create_typo_false_positive(self):
        blocks = [
            ("1", "ts", "Rahip Marjoe'nun babasının da"),
            ("2", "ts", "Basının ilgisi büyüktü."),
        ]
        self.assertEqual(gui._repeated_head_typo_ids(blocks), [])

    def test_kiz_kardes_is_not_a_midword_space(self):
        blocks = [
            ("1", "ts", "Kız kardeş, hadi şuraya gel."),
            ("2", "ts", "Kızkardeşim beni aradı."),
            ("3", "ts", "Kızkardeşi de oradaydı."),
        ]
        self.assertEqual(gui._midword_space_ids(blocks), [])

    def test_mixed_bracket_roles_and_delivery_style_are_stripped(self):
        cases = (
            ("[both] Aaaah?!", "[both] Aaaah?!", "Aaaah?!"),
            ("[co-hosts] Yay!", "[co-hosts] Yaşasın!", "Yaşasın!"),
            ("[sing-songy] ♪ Dun-dun-da-da ♪",
             "[sing-songy] ♪ Dun-dun-da-da ♪", "♪ Dun-dun-da-da ♪"),
        )
        for source, target, expected in cases:
            with self.subTest(source=source):
                result = sdh.clean_sdh_blocks(
                    [("1", "00:00:01,000 --> 00:00:02,000", target)],
                    src_map={"1": source}, source_driven=True)
                self.assertEqual(result[0][2], expected)

    def test_portuguese_exclusive_subtitle_credit_is_removed_and_reported(self):
        source_text = "Legendas Exclusivas: Elias Dourado\nMakingOff"
        self.assertTrue(gui._delivery_source_is_all_credit(source_text))
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "Özel altyazılar: Elias Dourado\nÇekim arkası")]
        self.assertEqual(
            gui._prepare_upload_ready_blocks(
                blocks, source_cues=[("1", blocks[0][1], source_text)]), [])
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.srt"
            output = Path(tmp) / "output.srt"
            source.write_text(
                f"1\n{blocks[0][1]}\n{source_text}\n", encoding="utf-8")
            output.write_text(
                f"1\n{blocks[0][1]}\n{blocks[0][2]}\n", encoding="utf-8")
            audit = gui._subtitle_delivery_audit(
                str(source), str(output), "Turkish", "Portuguese")
        self.assertEqual(audit["residual_credit_ids"], ["1"])


if __name__ == "__main__":
    unittest.main()
