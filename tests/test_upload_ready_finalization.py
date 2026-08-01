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
            "413",
            "00:00:10,001 --> 00:00:12,001",
            "discord: ceviri2",
        ))
        middle = [block for block in result[1:-1]
                  if block[2] == "discord: ceviri2"]
        self.assertEqual(len(middle), 1)
        self.assertEqual(middle[0][0], "412")
        self.assertEqual(
            middle[0][1],
            "00:00:06,001 --> 00:00:07,999",
        )
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

    def test_html_wrapped_resync_credit_is_removed(self):
        blocks = [
            (
                "12",
                "00:00:02,000 --> 00:00:04,000",
                '<font color="#ff65b4"><i>Yeniden eşitleyen: M_I_S\n'
                "www.opensubtitles.org</i></font>",
            ),
            (
                "13",
                "00:00:04,100 --> 00:00:04,900",
                '<font color="#ff65b4"><i>Senkron: M_I_S\n'
                "www.opensubtitles.org</i></font>",
            ),
            ("14", "00:00:05,000 --> 00:00:06,000", "Gerçek diyalog."),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("M_I_S", joined)
        self.assertNotIn("opensubtitles.org", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_source_script_credit_translated_by_model_is_removed(self):
        blocks = [
            (
                "1",
                "00:00:02,000 --> 00:00:12,000",
                "Savaş perisi Yukikaze 5 metni: yu",
            ),
            ("2", "00:00:13,000 --> 00:00:14,000", "Gerçek diyalog."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("metni: yu", joined)
        self.assertIn("Gerçek diyalog.", joined)

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

    def test_residual_sdh_and_music_only_cues_are_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "[HEPSİ AYNI ANDA KONUŞUR]"),
            ("2", "00:00:03,000 --> 00:00:04,000", "[LAUGHTER]"),
            ("3", "00:00:04,000 --> 00:00:05,000", "*"),
            ("4", "00:00:05,000 --> 00:00:06,000", "[KAMERA DEKLANŞÖR SESİ]"),
            ("5", "00:00:06,000 --> 00:00:07,000", "[Fransızca konuşan erkekler]"),
            ("6", "00:00:07,000 --> 00:00:08,000", "[SEYİRCİ NEFESİ KESİLİR]"),
            ("7", "00:00:08,000 --> 00:00:09,000", "[SİS DÜDÜĞÜ ÇALAR]"),
            ("8", "00:00:09,000 --> 00:00:10,000", "[Penguen cıvıltıları]"),
            ("9", "00:00:10,000 --> 00:00:11,000", "[ERKEKLERİN BAĞRIŞMALARI]"),
            ("10", "00:00:11,000 --> 00:00:12,000", "Gerçek diyalog."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        by_id = {str(idx): text for idx, _ts, text in result}
        self.assertNotIn("1", by_id)
        self.assertNotIn("2", by_id)
        self.assertNotIn("3", by_id)
        self.assertNotIn("4", by_id)
        self.assertNotIn("5", by_id)
        self.assertNotIn("6", by_id)
        self.assertNotIn("7", by_id)
        self.assertNotIn("8", by_id)
        self.assertNotIn("9", by_id)
        self.assertEqual(by_id["10"], "Gerçek diyalog.")

    def test_final_source_timing_guard_removes_reintroduced_sdh(self):
        source_cues = [
            ("44", "00:00:02,000 --> 00:00:03,000", "(fireballs thudding)"),
            (
                "45",
                "00:00:03,000 --> 00:00:04,000",
                "(shields clattering)\nHold.",
            ),
        ]
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "[ATEŞ TOPLARININ GÜMBÜRTÜSÜ]"),
            (
                "2",
                "00:00:03,000 --> 00:00:04,000",
                "(kalkanlar takırdar)\nDayanın.",
            ),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source_cues)
        texts = {str(idx): text for idx, _ts, text in result}

        self.assertNotIn("1", texts)
        self.assertEqual(texts["2"], "Dayanın.")

    def test_parenthetical_dialogue_and_bracketed_ui_text_are_preserved(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "(No.)"),
            ("2", "00:00:03,000 --> 00:00:04,000", "[OK]"),
            ("3", "00:00:04,000 --> 00:00:05,000", "(f(x))"),
            ("4", "00:00:05,000 --> 00:00:06,000", "[404 ERROR]"),
            ("5", "00:00:06,000 --> 00:00:07,000", "[Sesame Street]"),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        texts = {str(idx): text for idx, _ts, text in result}
        self.assertEqual(texts["1"], "(No.)")
        self.assertEqual(texts["2"], "[OK]")
        self.assertEqual(texts["3"], "(f(x))")
        self.assertEqual(texts["4"], "[404 ERROR]")
        self.assertEqual(texts["5"], "[Sesame Street]")

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

    def test_middle_signature_uses_nearest_safe_gap_without_moving_dialogue(self):
        blocks = [
            ("1", "00:00:10,000 --> 00:00:12,000", "Bir."),
            ("2", "00:00:12,100 --> 00:00:14,000", "İki."),
            ("3", "00:00:18,000 --> 00:00:20,000", "Üç."),
            ("4", "00:00:20,100 --> 00:00:22,000", "Dört."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        signatures = [block for block in result
                      if block[2] == "discord: ceviri2"]
        self.assertEqual(len(signatures), 3)
        self.assertEqual(
            signatures[1][1],
            "00:00:15,000 --> 00:00:17,000",
        )
        original = {idx: ts for idx, ts, _text in blocks}
        delivered = {idx: ts for idx, ts, _text in result if idx in original}
        self.assertEqual(delivered, original)

    def test_all_final_write_flows_use_shared_delivery_guard(self):
        source = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            source.count("_prepare_upload_ready_blocks("),
            8,
        )


if __name__ == "__main__":
    unittest.main()
