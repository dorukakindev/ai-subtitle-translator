import unittest

import sdh_cleaner as sdh


class TestPackage5SpeakerHeading(unittest.TestCase):
    def test_chapter_and_heading_preserved_in_strip_labels_by_source(self):
        """Screen headings like CHAPTER 1:, BREAKING NEWS: are not stripped as speaker labels."""
        src1 = "CHAPTER 1: The Beginning"
        tr1 = "BÖLÜM 1: Başlangıç"
        res1 = sdh.strip_labels_by_source(tr1, src1)
        self.assertEqual(res1, "BÖLÜM 1: Başlangıç")

        src2 = "BREAKING NEWS: Markets Fall"
        tr2 = "SON DAKİKA HABERİ: Piyasalar Düştü"
        res2 = sdh.strip_labels_by_source(tr2, src2)
        self.assertEqual(res2, "SON DAKİKA HABERİ: Piyasalar Düştü")

        src3 = "LOCATION: PARIS, FRANCE"
        tr3 = "KONUM: PARİS, FRANSA"
        res3 = sdh.strip_labels_by_source(tr3, src3)
        self.assertEqual(res3, "KONUM: PARİS, FRANSA")

    def test_actual_speakers_stripped_in_strip_labels_by_source(self):
        """Actual speaker names like JOHN:, DR. SMITH: are stripped when present in source."""
        src1 = "JOHN: Hello there."
        tr1 = "JOHN: Merhaba orada."
        res1 = sdh.strip_labels_by_source(tr1, src1)
        self.assertEqual(res1, "Merhaba orada.")

        src2 = "DR. SMITH: How are you?"
        tr2 = "DR. SMITH: Nasılsınız?"
        res2 = sdh.strip_labels_by_source(tr2, src2)
        self.assertEqual(res2, "Nasılsınız?")

        src3 = "Morris:\nLand counts for little more"
        tr3 = "Morris:\nKaralar, Dünya yüzeyinin"
        res3 = sdh.clean_sdh_blocks(
            [("1", "00:01 -> 00:03", tr3)],
            src_map={"1": src3}, source_driven=True)
        self.assertEqual(res3[0][2], "Karalar, Dünya yüzeyinin")

    def test_formal_salutations_are_not_stripped_as_speaker_labels(self):
        self.assertEqual(
            sdh.strip_labels_by_source(
                "Sayın Hakim: Doğru değil.", "Your Honor: Not right."),
            "Sayın Hakim: Doğru değil.",
        )
        self.assertEqual(
            sdh.strip_labels_by_source("Yüksek Mahkeme:", "Superior Court:"),
            "Yüksek Mahkeme:",
        )

    def test_clean_sdh_blocks_preserves_headings(self):
        """clean_sdh_blocks preserves heading lines while cleaning speaker labels."""
        blocks = [
            ("1", "00:01 -> 00:03", "BÖLÜM 1: Başlangıç"),
            ("2", "00:04 -> 00:06", "JOHN: Merhaba"),
        ]
        src_map = {
            "1": "CHAPTER 1: The Beginning",
            "2": "JOHN: Hello",
        }
        cleaned = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(cleaned[0][2], "BÖLÜM 1: Başlangıç")
        self.assertEqual(cleaned[1][2], "Merhaba")


if __name__ == "__main__":
    unittest.main()
