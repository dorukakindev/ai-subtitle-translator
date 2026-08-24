import unittest

import hybrid_translate as ht
import prompt_constants as pc
import sdh_cleaner
import subtitle_translator_gui as gui


class AmericanMovieDeliveryRegressions(unittest.TestCase):
    def test_ellipsis_hesitation_is_dialogue_but_caption_vocalization_is_removable(self):
        self.assertFalse(gui._source_cue_is_delivery_removable("Uh..."))
        self.assertFalse(gui._source_cue_is_delivery_removable("<i>UH…</i>"))
        self.assertTrue(gui._source_cue_is_delivery_removable("UH!"))

    def test_source_driven_cleanup_strips_structural_bracket_speakers(self):
        source = {
            "1": "-[Cee-Cee] You're not a fox.",
            "2": "[Bill, sarcastically] Yay.",
            "3": "<i>[Buck on radio] ...in 17 plays.</i>",
        }
        blocks = [
            ("1", "t1", "-[Cee-Cee] Sen tilki değilsin."),
            ("2", "t2", "[Bill, sarcastically] Yaşasın."),
            ("3", "t3", "<i>[Buck on radio]...17 oyunda.</i>"),
        ]

        cleaned = sdh_cleaner.clean_sdh_blocks(
            blocks, src_map=source, source_driven=True)
        text = "\n".join(value for _idx, _ts, value in cleaned)

        self.assertNotIn("Cee-Cee", text)
        self.assertNotIn("Bill, sarcastically", text)
        self.assertNotIn("Buck on radio", text)
        self.assertIn("Sen tilki değilsin.", text)
        self.assertIn("Yaşasın.", text)
        self.assertIn("17 oyunda.", text)

    def test_source_driven_cleanup_preserves_same_line_bracketed_titles(self):
        source = {
            "1": "[Soft Power] A documentary.",
            "2": "[Sesame Street] is a show.",
        }
        blocks = [
            ("1", "t1", "[Soft Power] Bir belgesel."),
            ("2", "t2", "[Sesame Street] bir programdır."),
        ]

        self.assertEqual(
            sdh_cleaner.clean_sdh_blocks(
                blocks, src_map=source, source_driven=True),
            blocks,
        )

    def test_source_driven_cleanup_strips_ocr_damaged_speaker_prefixes(self):
        source = {"1": "'Mike] Go.", "2": "Mike| Here you go."}
        blocks = [
            ("1", "t1", '"[Mike] Başla.'),
            ("2", "t2", "Mike| Al bakalım."),
        ]

        cleaned = sdh_cleaner.clean_sdh_blocks(
            blocks, src_map=source, source_driven=True)

        self.assertEqual([value for _idx, _ts, value in cleaned],
                         ["Başla.", "Al bakalım."])

    def test_ambiguous_ocr_pipe_is_reported_not_rewritten(self):
        blocks = [("933", "t", "Hayır, bir şe||-- Bir kelime kullandım.")]
        source = {"933": "No, I changed a||-- I used one word."}

        self.assertEqual(gui._delivery_ocr_artifact_ids(blocks, source), ["933"])
        self.assertIn("şe||", blocks[0][2])

    def test_bad_film_glossary_locks_are_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Action": "Aksiyon",
            "in the can": "kutuda",
            "atmosphere": "figürasyon ortamı",
            "camera": "kamera",
        })

        self.assertEqual(cleaned, {"camera": "kamera"})

    def test_thanksgiving_identity_lock_is_unsafe(self):
        self.assertIn("thanksgiving", pc.TRANSLATABLE_CAPITALISED_STOPS)
        self.assertEqual(
            ht.sanitize_glossary_for_turkish({"Thanksgiving": "Thanksgiving"}),
            {},
        )

    def test_delivery_typography_removes_double_and_quote_edge_spaces(self):
        self.assertEqual(
            gui._normalize_delivery_typography('Bir  şey.  "'),
            'Bir şey."',
        )


if __name__ == "__main__":
    unittest.main()
