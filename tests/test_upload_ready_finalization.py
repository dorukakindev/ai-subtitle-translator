import unittest
from pathlib import Path

import subtitle_translator_gui as gui


class UploadReadyFinalizationTest(unittest.TestCase):
    def test_real_delivery_cases_are_cleaned_and_signed_idempotently(self):
        blocks = [
            ("1", "00:00:03,000 --> 00:00:04,000", "Hâlâ buradayım."),
            (
                "2",
                "00:00:04,100 --> 00:00:05,000",
                r"{\i1}{\frz345.405\pos(302, 129)\an8}Sarı Çizgili{\i0}",
            ),
            ("49", "00:00:05,100 --> 00:00:06,000", "Göstermelik"),
            (
                "50",
                "00:00:05,100 --> 00:00:06,000",
                "Bizi ziyaret edin:\nirc.gotwoot.net\n#gotwoot-fansubs",
            ),
            ("51", "00:00:05,100 --> 00:00:06,000", "veya internet sitemiz:"),
            ("52", "00:00:05,100 --> 00:00:06,000", "http://www.gotwoot.net/"),
            (
                "410",
                "00:00:06,100 --> 00:00:07,000",
                "Sylf, Çeviri\nNanne, Zamanlama\nCollectr, Dizgi",
            ),
            ("411", "00:00:08,000 --> 00:00:10,000", "Bitti."),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")

        self.assertEqual(result[0], (
            "0",
            "00:00:00,999 --> 00:00:02,999",
            "discord: ceviri2",
        ))
        self.assertEqual(result[-1], (
            "412",
            "00:00:10,001 --> 00:00:12,001",
            "discord: ceviri2",
        ))
        by_id = {str(idx): (ts, text) for idx, ts, text in result}
        self.assertEqual(by_id["1"][1], "Hala buradayım.")
        self.assertEqual(by_id["2"][1], r"{\i1}Sarı Çizgili{\i0}")
        self.assertEqual(by_id["49"][1], "Göstermelik")
        self.assertNotIn("50", by_id)
        self.assertNotIn("51", by_id)
        self.assertNotIn("52", by_id)
        self.assertNotIn("410", by_id)
        self.assertEqual(
            gui._prepare_upload_ready_blocks(result, "Turkish"),
            result,
        )

    def test_subtitle_company_credit_is_removed(self):
        blocks = [
            (
                "1",
                "00:00:02,000 --> 00:00:03,000",
                "Film ve Video Altyazılama\nGerhard Lehmann AG",
            ),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        self.assertNotIn("Film ve Video", "\n".join(text for _i, _ts, text in result))
        self.assertIn("Gerçek diyalog.", "\n".join(text for _i, _ts, text in result))

    def test_production_credit_and_dialogue_url_are_preserved(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Müzik:"),
            ("2", "00:00:02,000 --> 00:00:03,000", "Kenji Kawai"),
            (
                "3",
                "00:00:04,000 --> 00:00:05,000",
                "Adresi https://example.com olarak söyledi.",
            ),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        joined = "\n".join(text for _i, _ts, text in result)
        self.assertIn("Müzik:", joined)
        self.assertIn("Kenji Kawai", joined)
        self.assertIn("https://example.com", joined)

    def test_unresolved_translation_is_not_signed_as_complete(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]"),
            ("2", "00:00:02,000 --> 00:00:03,000", "Sonraki cue."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        self.assertFalse(any(text == "discord: ceviri2" for _i, _ts, text in result))
        self.assertEqual(result[0][2], "[ÇEVİRİ EKSİK]")

    def test_non_turkish_output_is_unchanged(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", r"{\pos(1,2)}Hâlâ"),
        ]
        self.assertEqual(
            gui._prepare_upload_ready_blocks(blocks, "English"),
            blocks,
        )

    def test_zero_start_still_gets_valid_minimal_head_signature(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000", "Başlangıç."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        self.assertEqual(result[0][1], "00:00:00,000 --> 00:00:00,001")

    def test_all_final_write_flows_use_shared_delivery_guard(self):
        source = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            source.count("_prepare_upload_ready_blocks("),
            7,
        )


if __name__ == "__main__":
    unittest.main()
