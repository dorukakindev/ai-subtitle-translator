import unittest

import subtitle_translator_gui as gui


class RunLogRegressionTests(unittest.TestCase):
    def test_delivery_signature_number_is_not_a_cue_id_leak(self):
        blocks = [
            ("0", "00:00:00,000 --> 00:00:00,001", "discord: ceviri2"),
            ("107", "ts", "Sadakati bu kadar yücelten sen,\n108"),
        ]
        self.assertEqual(gui._cue_id_leak_ids(blocks), ["107"])

    def test_midword_detector_ignores_postpositions_and_apostrophe_suffixes(self):
        blocks = [
            ("1", "ts", "Öğleden sonrası için de altı çizgi var."),
            ("2", "ts", "Kutunun içinde bir çizgi var."),
            ("3", "ts", "Evin içinde iki çizgi var."),
            ("4", "ts", "Dünya'yı ölçtü."),
            ("5", "ts", "Dünyayı değiştirdi."),
            ("6", "ts", "Dünyayı dolaştı."),
            ("7", "ts", "Filip'e aitti."),
        ]
        self.assertEqual(
            gui._midword_space_ids(blocks, {"7": "Pertencia a Filipe."}), [])

    def test_midword_detector_still_finds_a_split_word(self):
        blocks = [("154", "ts", "Piram itler Çağı başladı.")]
        self.assertEqual(
            gui._midword_space_ids(
                blocks, {"154": "The Age of Piramitler began."}),
            ["154"],
        )

    def test_title_and_dotcom_spelling_variants_are_not_midword_breaks(self):
        blocks = [
            ("1", "ts", "Good Will Hunting'de oynadı."),
            ("2", "ts", "dot-com patlaması sırasında büyüdü."),
        ]
        self.assertEqual(gui._midword_space_ids(blocks, {
            "1": "He acted in Goodwill Hunting.",
            "2": "It grew during the dotcom boom.",
        }), [])

    def test_owner_detector_ignores_dutch_kan_and_compound_roentgen(self):
        items = [
            {"i": "57", "t": "Röntgen gösterileri daha çok insan çekti."},
            {"i": "62", "t": "Röntgen ışınları onlara yeniden hayat verdi."},
            {"i": "83", "t": "Geleceğe doğru saldırır. Kan onu etkilemez."},
        ]
        sources = {
            "57": "Röntgen-shows trokken meer mensen dan films.",
            "62": "Röntgenstralen gaven ze nieuw leven.",
            "70": "Röntgen schreef hierover.",
            "83": "Hij stormt naar de toekomst. Bloed deert hem niet.",
            "84": "Kan ik komen?",
        }
        self.assertEqual(
            gui._chunk_content_owner_mismatch_ids(items, sources), set())

    def test_french_institution_name_is_not_untranslated_dialogue(self):
        text = "Bureau\nInternationale des Poids et Mesures."
        self.assertEqual(
            gui._delivery_untranslated_fragment_ids(
                [("309", "ts", text)], {"309": text},
                target_language="Turkish", source_language="English",
            ),
            [],
        )

    def test_repeated_foreign_refrain_is_not_reported_as_untranslated(self):
        logs = []
        warnings = gui.scan_translation_quality(
            "missing-source.srt",
            [("52", "ts", "# Gloria, gloria! #")],
            log_fn=lambda *args, **kwargs: logs.append(args),
            src_clean_map={"52": "# Gloria, gloria! #"},
            source_language="English",
        )
        self.assertEqual(warnings, 0)
        self.assertEqual(logs, [])

    def test_source_backed_one_letter_in_foreign_quote_is_not_garble(self):
        source = 'Diz assim: "a summ grafai", regras de construção.'
        target = '"a summ grafai", yani "yapı kuralları".'
        logs = []
        warnings = gui.scan_translation_quality(
            "missing-source.srt", [("850", "ts", target)],
            log_fn=lambda *args, **kwargs: logs.append(args),
            src_clean_map={"850": source}, source_language="Portuguese",
        )
        self.assertEqual(warnings, 0)
        self.assertEqual(logs, [])


if __name__ == "__main__":
    unittest.main()
