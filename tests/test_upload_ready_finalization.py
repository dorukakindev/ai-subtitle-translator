import unittest
from tempfile import TemporaryDirectory
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
        middle = [
            block for block in result[1:-1]
            if block[2] == "discord: ceviri2"]
        self.assertEqual(len(middle), 1)
        self.assertEqual(middle[0][0], "50")
        by_id = {str(idx): (ts, text) for idx, ts, text in result}
        self.assertEqual(by_id["1"][1], "Hala buradayım.")
        self.assertEqual(by_id["2"][1], "<i>Sarı Çizgili</i>")
        self.assertEqual(by_id["49"][1], "Göstermelik")
        joined = "\n".join(text for _ts, text in by_id.values())
        self.assertNotIn("gotwoot", joined)
        self.assertNotIn("Sylf", joined)
        self.assertEqual(
            gui._prepare_upload_ready_blocks(result, "Turkish"),
            result,
        )

    def test_dangling_ass_italic_is_balanced_as_srt_html(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", r"{\i1}Telsiz konuşması"),
            ("2", "00:00:04,000 --> 00:00:05,000", r"Şarkı sözü{\i0}"),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        dialogue = [text for _idx, _ts, text in result if "ceviri2" not in text]

        self.assertEqual(dialogue, [
            "<i>Telsiz konuşması</i>",
            "<i>Şarkı sözü</i>",
        ])

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

    def test_dvd_authoring_credit_is_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Gerçek diyalog."),
            ("2", "00:00:04,000 --> 00:00:05,000", "DVD Yazarlığı DiMEDIA Group"),
        ]
        source = [
            ("1", blocks[0][1], "Real dialogue."),
            ("2", blocks[1][1], "DVD Authoring DiMEDIA Group"),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _i, _ts, text in result)

        self.assertIn("Gerçek diyalog.", joined)
        self.assertNotIn("DiMEDIA", joined)

    def test_french_subtitle_company_credit_is_removed_from_source(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Altyazi : TransPerfect Media"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Sous-titrage : TransPerfect Media"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Dialogue réel."),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _i, _ts, text in result)
        self.assertNotIn("TransPerfect", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_trailing_visiontext_ocr_marker_is_removed_from_source(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Gerçek diyalog."),
            ("2", "00:00:04,000 --> 00:00:05,000", "Fran Welland"),
            ("3", "00:00:05,100 --> 00:00:06,000", "ENHOH"),
            ("4", "00:00:06,100 --> 00:00:07,000", "yayıldı\nkullanici@fileheaven ;)"),
            ("5", "00:00:07,100 --> 00:00:08,000", "C.M.C. tarafından işlendi"),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Real dialogue."),
            ("2", "00:00:04,000 --> 00:00:05,000", "Visiontext Subtitles: Fran Welland"),
            ("3", "00:00:05,100 --> 00:00:06,000", "ENHOH"),
            ("4", "00:00:06,100 --> 00:00:07,000", "ripped and spread by\nkullanici@fileheaven ;)"),
            ("5", "00:00:07,100 --> 00:00:08,000", "Processed by C.M.C. - Paris"),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _i, _ts, text in result)
        self.assertNotIn("Fran Welland", joined)
        self.assertNotIn("ENHOH", joined)
        self.assertNotIn("fileheaven", joined)
        self.assertNotIn("C.M.C.", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_source_ocr_quote_markers_are_normalized(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "'Her şey ortaktı."),
            ("2", "00:00:03,100 --> 00:00:04,000", "ihtiyacına göre#"),
            ("3", "00:00:04,100 --> 00:00:05,000", "İhtiyacımız olan bu#"),
            ("4", "00:00:05,100 --> 00:00:06,000", '"Yüzünü çimenlere bastır,'),
            ("5", "00:00:06,100 --> 00:00:07,000", 'iyi geldiğini hissedersin."'),
            ("6", "00:00:07,100 --> 00:00:08,000", "İhtiyaçları olan bu#"),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "'...had all things common."),
            ("2", "00:00:03,100 --> 00:00:04,000", "as every man had need#"),
            ("3", "00:00:04,100 --> 00:00:05,000", "That's what we need#"),
            ("4", "00:00:05,100 --> 00:00:06,000", "'Try to press your face into grass"),
            ("5", "00:00:06,100 --> 00:00:07,000", "and you'll feel how good it is."),
            ("6", "00:00:07,100 --> 00:00:08,000", "That's what they need#"),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        dialogue = [
            text for _idx, _ts, text in result
            if text != "discord: ceviri2"
        ]

        self.assertEqual(dialogue, [
            '"Her şey ortaktı.',
            'ihtiyacına göre"',
            "İhtiyacımız olan bu.",
            '"Yüzünü çimenlere bastır,',
            'iyi geldiğini hissedersin."',
            "İhtiyaçları olan bu.",
        ])

    def test_double_apostrophe_quoted_cues_do_not_leave_mixed_markers(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "''Birinci satır''"),
            ("2", "00:00:03,100 --> 00:00:04,000", "''ikinci satır''"),
            ("3", "00:00:04,100 --> 00:00:05,000", "''açık alıntı..."),
            ("4", "00:00:05,100 --> 00:00:06,000", "devam ediyor...''"),
            ("5", "00:00:06,100 --> 00:00:07,000", "''Satır sonu''\nGördün mü?"),
            ("6", "00:00:07,100 --> 00:00:08,000", "Başlık: ''Mekke'ye Gidiş''"),
        ]
        source = list(blocks)

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        dialogue = [
            text for _idx, _ts, text in result
            if text != "discord: ceviri2"
        ]

        self.assertEqual(dialogue, [
            '"Birinci satır"',
            '"ikinci satır"',
            '"açık alıntı...',
            'devam ediyor..."',
            '"Satır sonu"\nGördün mü?',
            'Başlık: "Mekke\'ye Gidiş"',
        ])

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

    def test_single_line_subtitle_credit_is_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Subtitles: Some_User"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("Some_User", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_translator_credit_is_removed_but_translation_dialogue_is_kept(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Translator: John Doe"),
            ("2", "00:00:04,000 --> 00:00:05,000",
             "Translation: What does that mean?"),
        ]
        blocks = [
            ("1", source[0][1], "Çevirmen: John Doe"),
            ("2", source[1][1], "Tercüme: Bunun anlamı ne?"),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        dialogue = [text for _idx, _ts, text in result
                    if text != "discord: ceviri2"]

        self.assertEqual(dialogue, ["Tercüme: Bunun anlamı ne?"])

    def test_unknown_ass_commands_are_removed_without_losing_dialogue(self):
        result = gui._prepare_upload_ready_blocks([
            ("1", "00:00:02,000 --> 00:00:04,000",
             r"{\pos(1,2)\fs30}Merhaba{\fad(1,1)}"),
        ], "Turkish")
        dialogue = [text for _idx, _ts, text in result
                    if text != "discord: ceviri2"]

        self.assertEqual(dialogue, ["Merhaba"])

    def test_position_only_cue_is_dropped_instead_of_becoming_missing(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", r"{\pos(357,422)}"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        texts = [text for _idx, _ts, text in result]
        self.assertNotIn("", texts)
        self.assertNotIn("[ÇEVİRİ EKSİK]", texts)
        self.assertNotIn("1", {str(idx) for idx, _ts, _text in result})

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

    def test_source_credit_is_removed_after_sdh_strips_its_role_label(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "JG"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Translation: JG"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Real dialogue."),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("JG", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_subtitled_by_source_credit_is_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "N.F.D.C. tarafından altyazılandı\nBombay"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Subtitled by N.F.D.C.\nBombay (India)"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Real dialogue."),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("N.F.D.C.", joined)
        self.assertIn("Gerçek diyalog.", joined)

    def test_film_editor_credit_is_not_treated_as_subtitle_credit(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Kurgu: L. Tsitsina"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gerçek diyalog."),
        ]
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Editor: L. Tsitsina"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Real dialogue."),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertIn("L. Tsitsina", joined)
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

    def test_pure_language_labels_are_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "(Latince)"),
            ("2", "00:00:03,000 --> 00:00:04,000", "(Fransızca)"),
            ("3", "00:00:04,000 --> 00:00:05,000", "(Afrika dili)"),
            ("4", "00:00:05,000 --> 00:00:06,000", "(unintelligible)"),
            ("5", "00:00:06,000 --> 00:00:07,000", "(African language or glossolalia)"),
            ("6", "00:00:07,000 --> 00:00:08,000", "Gerçek diyalog."),
        ]

        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        by_id = {str(idx): text for idx, _ts, text in result}
        self.assertNotIn("1", by_id)
        self.assertNotIn("2", by_id)
        self.assertNotIn("3", by_id)
        self.assertNotIn("4", by_id)
        self.assertNotIn("5", by_id)
        self.assertEqual(by_id["6"], "Gerçek diyalog.")

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

    def test_delivery_audit_accepts_removed_whistle_sound(self):
        source = [("1", "00:00:02,000 --> 00:00:03,000", "(whistle sound)")]
        delivered = gui._prepare_upload_ready_blocks(
            source, "Turkish", source_cues=source)

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "English")
            gui.write_srt(output_path, delivered, "English")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1"])

    def test_delivery_audit_accepts_documentary_explosion_and_call_to_prayer(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "EXPLOSION"),
            ("2", "00:00:04,000 --> 00:00:05,000", "CALL TO PRAYER"),
        ]
        delivered = gui._prepare_upload_ready_blocks(
            source, "Turkish", source_cues=source)

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "English")
            gui.write_srt(output_path, delivered, "Turkish")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2"])

    def test_delivery_audit_accepts_documentary_work_and_water_sounds(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "MONASTIC CHANTING"),
            ("2", "00:00:04,000 --> 00:00:05,000", "HAMMERING"),
            ("3", "00:00:06,000 --> 00:00:07,000", "WATER SPLASHES"),
        ]
        delivered = gui._prepare_upload_ready_blocks(
            source, "Turkish", source_cues=source)

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "English")
            gui.write_srt(output_path, delivered, "Turkish")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2", "3"])

    def test_delivery_audit_accepts_bare_french_stage_direction(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Petit gémissement de douleur"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Continue until night."),
        ]
        translated = [
            ("1", source[0][1], "Hafif bir acı iniltisi."),
            ("2", source[1][1], "Geceye dek devam edin."),
        ]
        delivered = gui._prepare_upload_ready_blocks(
            translated, "Turkish", source_cues=source)

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "French")
            gui.write_srt(output_path, delivered, "Turkish")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1"])

    def test_delivery_audit_accepts_multiline_sdh_and_unknown_placeholder(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "-[wind blowing]\n-[crickets chirping]"),
            ("2", "00:00:03,000 --> 00:00:04,000", "???"),
            ("3", "00:00:04,000 --> 00:00:05,000", "[thundering]"),
            ("4", "00:00:05,000 --> 00:00:06,000", "Real dialogue."),
        ]
        delivered = gui._prepare_upload_ready_blocks(
            [("2", source[1][1], "Uydurulmuş diyalog."),
             ("4", source[3][1], "Gerçek diyalog.")],
            "Turkish", source_cues=source)

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "English")
            gui.write_srt(output_path, delivered, "English")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2", "3"])

    def test_delivery_audit_accepts_hadestown_sdh_variants(self):
        source = [
            ("1", "00:00:02,000 --> 00:00:03,000", "-[click]\n-[silence]"),
            ("2", "00:00:03,000 --> 00:00:04,000", "[audience clapping to the beat]"),
            ("3", "00:00:04,000 --> 00:00:05,000", "Real dialogue."),
        ]
        delivered = gui._prepare_upload_ready_blocks(
            [("3", source[2][1], "Gercek diyalog.")],
            "Turkish",
            source_cues=source,
        )

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source, "English")
            gui.write_srt(output_path, delivered, "Turkish")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["expected_removed_ids"], ["1", "2"])

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

    def test_unknown_source_placeholder_cannot_gain_hallucinated_dialogue(self):
        source_cues = [
            ("1", "00:00:02,000 --> 00:00:03,000", "???"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Real dialogue."),
        ]
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Uydurulmuş diyalog."),
            ("2", "00:00:03,000 --> 00:00:04,000", "Gerçek diyalog."),
        ]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source_cues)
        texts = {str(idx): text for idx, _ts, text in result}

        self.assertNotIn("1", texts)
        self.assertEqual(texts["2"], "Gerçek diyalog.")

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

    def test_zero_start_does_not_get_overlapping_head_signature(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000", "Başlangıç."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        self.assertEqual(result[0][1], "00:00:00,000 --> 00:00:01,000")
        self.assertEqual(result[0][2], "Başlangıç.")
        self.assertEqual(sum(text == "discord: ceviri2"
                             for _idx, _ts, text in result), 1)

    def test_existing_zero_id_is_shifted_to_keep_signature_ids_unique(self):
        blocks = [
            ("0", "00:00:00,000 --> 00:00:01,000", "Başlangıç."),
            ("1", "00:00:01,100 --> 00:00:02,000", "Devam."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        ids = [idx for idx, _ts, _text in result]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[:3], ["1", "2", "3"])
        self.assertTrue(gui._existing_output_is_complete(result, blocks))

    def test_head_middle_and_tail_signatures_are_added_without_moving_dialogue(self):
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
        self.assertEqual(signatures[0][0], "0")
        self.assertGreater(gui._srt_timestamp_bounds(signatures[2][1])[0],
                           gui._srt_timestamp_bounds(blocks[-1][1])[1])
        middle_start, middle_end = gui._srt_timestamp_bounds(signatures[1][1])
        self.assertGreater(middle_start, gui._srt_timestamp_bounds(blocks[1][1])[1])
        self.assertLess(middle_end, gui._srt_timestamp_bounds(blocks[2][1])[0])
        delivered_dialogue = [
            (ts, text) for _idx, ts, text in result
            if text != "discord: ceviri2"]
        self.assertEqual(
            delivered_dialogue,
            [(ts, text) for _idx, ts, text in blocks],
        )

    def test_middle_signature_round_trip_keeps_auditable_dialogue_timings(self):
        source_blocks = [
            ("1", "00:00:10,000 --> 00:00:12,000", "One."),
            ("2", "00:00:12,100 --> 00:00:14,000", "Two."),
            ("3", "00:00:18,000 --> 00:00:20,000", "Three."),
            ("4", "00:00:20,100 --> 00:00:22,000", "Four."),
        ]
        translated = [
            (idx, ts, text) for (idx, ts, _source), text in zip(
                source_blocks, ("Bir.", "Iki.", "Uc.", "Dort."))]
        delivered = gui._prepare_upload_ready_blocks(translated, "Turkish")

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source_blocks, "English")
            gui.write_srt(output_path, delivered, "English")

            reparsed = gui.parse_srt(output_path)
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual([idx for idx, _ts, _text in reparsed],
                         ["0", "1", "2", "3", "4", "5", "6"])
        self.assertEqual(audit["status"], "ok")
        self.assertEqual(audit["delivery_signatures"], 3)

    def test_delivery_audit_rejects_missing_required_signatures(self):
        source_blocks = [
            ("1", "00:00:10,000 --> 00:00:12,000", "One."),
            ("2", "00:00:18,000 --> 00:00:20,000", "Two."),
        ]
        untranslated_delivery = [
            ("1", "00:00:10,000 --> 00:00:12,000", "Bir."),
            ("2", "00:00:18,000 --> 00:00:20,000", "Iki."),
        ]

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source_blocks, "English")
            gui.write_srt(output_path, untranslated_delivery, "English")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "review")
        self.assertEqual(audit["delivery_signatures"], 0)
        self.assertEqual(audit["expected_delivery_signatures"], 3)
        self.assertTrue(audit["signature_mismatch"])
        self.assertEqual(audit["missing_dialogue_ids"], [])
        self.assertEqual(audit["extra_dialogue_ids"], [])

    def test_delivery_audit_rejects_serialized_json_residue(self):
        source_blocks = [
            ("1", "00:00:10,000 --> 00:00:12,000", "Does it cause hallucinations?"),
        ]
        delivered = gui._prepare_upload_ready_blocks([
            ("1", source_blocks[0][1], "Halüsinasyon yapar mı?},{"),
        ], "Turkish")

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source_blocks, "English")
            gui.write_srt(output_path, delivered, "English")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["serialized_json_residue_ids"], ["1"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_delivery_audit_rejects_signature_id_collision(self):
        source_blocks = [
            ("1", "00:00:10,000 --> 00:00:12,000", "One."),
            ("2", "00:00:18,000 --> 00:00:20,000", "Two."),
        ]
        delivered = gui._prepare_upload_ready_blocks([
            ("1", source_blocks[0][1], "Bir."),
            ("2", source_blocks[1][1], "İki."),
        ], "Turkish")
        delivered[0] = ("1", delivered[0][1], delivered[0][2])

        with TemporaryDirectory() as root:
            source_path = Path(root, "source.srt")
            output_path = Path(root, "output.srt")
            gui.write_srt(source_path, source_blocks, "English")
            gui.write_srt(output_path, delivered, "English")
            audit = gui._subtitle_delivery_audit(source_path, output_path)

        self.assertEqual(audit["status"], "review")
        self.assertEqual(audit["duplicate_cue_ids"], ["1"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_all_final_write_flows_use_shared_delivery_guard(self):
        source = Path(gui.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            source.count("_prepare_upload_ready_blocks("),
            9,
        )


class DeliveryCreditRegressionTest(unittest.TestCase):
    def test_delivery_audit_rejects_source_derived_voice_over_label(self):
        with TemporaryDirectory() as td:
            source_path = Path(td) / "source.srt"
            output_path = Path(td) / "output.srt"
            source_path.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n"
                "YOUSEF, VOICE-OVER: I carried the holy fire.\n",
                encoding="utf-8",
            )
            output_path.write_text(
                "1\n00:00:01,000 --> 00:00:02,000\n"
                "YOUSEF, SES ÜSTÜ: Kutsal ateşi taşıdım.\n",
                encoding="utf-8",
            )

            audit = gui._subtitle_delivery_audit(str(source_path), str(output_path))

        self.assertEqual(audit["residual_speaker_label_ids"], ["1"])
        self.assertTrue(gui._delivery_audit_has_hard_error(audit))

    def test_arabic_translator_credit_is_delivery_removable(self):
        for source in (
                "ترجم من قبل: ناجي بهنان",
                "ترجم من قبل: عبد الرحمن كلاس"):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))

    def test_release_site_promos_are_removed_but_film_credits_remain(self):
        for source in (
                "Downloaded from\nYTS.MX",
                "Official YIFY movies site:\nYTS.MX"):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))
        self.assertFalse(gui._source_cue_is_delivery_removable(
            "Slovenský filmový ústav\npresents"))

    def test_named_chant_bbc_credit_and_open_university_cta_are_removable(self):
        for source in (
                "(Chanting Hercules)",
                'THEY CONTINUE TO SING\n"Viderunt Omnes"',
                "E-mail subtitling@bbc.co.uk",
                "The conversation continues with the\nOpen University.",
                "Go to the address below and follow\nthe links to the Open University."):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))

    def test_bare_french_and_turkish_sdh_are_delivery_removable(self):
        for source in (
                "Musique douce instrumentale", "Musique gaie populaire",
                "On frappe", "La porte s'ouvre", "Elle soupire", "Rire nerveux"):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))
        for target in ("Yumuşak enstrümantal müzik", "Kapı açılıyor",
                       "İç çeker", "Sinirli gülüş"):
            with self.subTest(target=target):
                self.assertTrue(gui._is_delivery_sdh_only(target))
        self.assertFalse(gui._is_delivery_sdh_only("Müzik"))

    def test_ordinal_list_heading_is_not_removed_as_speaker_label(self):
        self.assertFalse(gui._source_cue_is_delivery_removable("Second:"))
        result = gui._prepare_upload_ready_blocks(
            [("604", "00:10:00,000 --> 00:10:01,000", "Ikincisi:")],
            "Turkish",
            source_cues=[("604", "00:10:00,000 --> 00:10:01,000", "Second:")],
        )
        self.assertIn("Ikincisi:", [text for _idx, _ts, text in result])

    def test_speaks_native_language_is_expected_sdh_removal(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            "[ Speaks native language ]"))

    def test_named_native_speech_and_chant_are_expected_sdh_removal(self):
        for source in (
                "[LORNG SPEAKING NATIVE LANGUAGE]",
                "[JAVIER SPEAKING\nNATIVE LANGUAGE]",
                "[WALKIE-TALKIE BEEPS]\n[SPEAKING\nNATIVE LANGUAGE]",
                "[MEN CHANT]",
                "(Speaking Dogon)",
                "(Speaks Kwak'wala)",
                "(People chatting in Spanish)",
                "(Speaking in Quechua)",
                "(Speaking in Indian tongue)",
                '<font color="#ffffff">SHE WAILS</font>',
                '<font color="#ffffff">WOMEN ALL SCREAM</font>',
                '<font color="#ffffff">SHE PANTS</font>',
                '<font color="#ffffff">BATTLE CRIES ECHO</font>',
        ):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))

    def test_multiline_translated_native_language_label_is_residual_sdh(self):
        self.assertTrue(gui._is_delivery_sdh_only(
            "[JAVIER YEREL DİLDE\nKONUŞUYOR]"))
        self.assertFalse(gui._is_delivery_sdh_only(
            "[Javier yerel dilde bir şey\nsöylemek istiyor.]"))

    def test_bare_documentary_sdh_is_expected_delivery_removal(self):
        for source in (
                "(WOMeN ULLULATING)", "(ReADS IN HeBReW)",
                "(PROPELLER STUTTERS)", "(ANNOUNCEMENT ON PA SYSTEM)",
                "(VENDOR CALLING OUT)", "(DEEP, RESONATING NOTES)",
                "(SPEAKING GEORGIAN)", "CHEERFUL HYMN MUSIC", "CHANTING",
                "THEY SING A HYMN", "THEY LAUGH", "[PEOPLE CHANT]",
                "THEY SING SEDERUNT PRINCIPES",
                "THEY CONTINUE TO SING IN PARTS",
                "CHILDREN LAUGH",
                "CHILDREN CHAT IN THEIR LANGUAGE",
                "MOURNERS CRY",
                "HE SHOUTS IN HIS OWN LANGUAGE",
                "THEY SHOUT AND SING",
                "HARMONIC SINGING",
                "THEY SING IN LATIN",
                "UNACCOMPANIED SINGING",
                "THEY HARMONISE",
                "SAME NOTE",
                "SINGING IN HARMONY",
                "SINGING DROWNS\nSIMON RUSSELL BEALE'S WORDS",
                'THEY SING "OMNES" IN PARTS',
                '"VIDERUNT OMNES" CONTINUES',
                '"VITUS ABIT LITTERA" IS SUNG',
                "THEY SHOUT",
                "BABIES CRY",
                "SHE GASPS",
                "THEY APPLAUD",
                "HE SHOUTS",
                "SHE LAUGHS",
                "WHISTLE BLOWS",
                "CROWD CHEERS",
                "THEY BECOME SILENT",
                "MAN GIVES INSTRUCTIONS OVER PA",
                "THEY SING THROUGH THE CHORD PROGRESSION",
                "THEY SING, REPEATING THE SECTION IN FULL",
                "THEY CHEER",
                "[PEOPLE CHEER]", "HEAVY CREAKING DOOR OPENS",
                "HEAVY DOOR CLOSES", "DOOR CREAKS", "WOLF CRIES",
                "HORSE WHINNIES", "SHOUTING", "WOLF HOWLS",
                "TRANSLATION:", "HUNNIC BATTLE CRIES", "BATTLE CRIES",
                "OWL HOOTS AND WOLF HOWLS",
                "[REPEATING\nIN HEBREW]", "[SHEEP BAAS]"):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))

    def test_foreign_speech_mouthing_and_action_sdh_are_removable(self):
        for source in (
                "[SPEAKS IN FOREIGN LANGUAGE]",
                "[MOUTHING WORDS]",
                "<i>(Clamor)</i>",
                "<i>(Rosaura eats noisily)</i>"):
            with self.subTest(source=source):
                self.assertTrue(gui._source_cue_is_delivery_removable(source))

    def test_punctuation_only_source_cue_is_not_required_dialogue(self):
        self.assertTrue(gui._source_cue_is_delivery_removable("..."))

    def test_collapsed_italian_subtitle_credit_and_bare_domain_are_removed(self):
        source = [(
            "3", "00:00:02,000 --> 00:00:05,000",
            "IL DIPENDENTE\nTraduzione: Tartakirka. Revisione: Jago71\n"
            "younditalia.wordpress.com",
        )]
        blocks = [(
            "3", source[0][1],
            "Tartakirka. Jago71\nyounditalia.wordpress.com",
        )]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)

        joined = "\n".join(text for _idx, _ts, text in result)
        self.assertNotIn("Tartakirka", joined)
        self.assertNotIn("wordpress.com", joined)

        title_result = gui._prepare_upload_ready_blocks(
            [("3", source[0][1], "BAĞIMLI")], "Turkish", source_cues=source)
        title_texts = [
            text for _idx, _ts, text in title_result
            if text != "discord: ceviri2"
        ]
        self.assertEqual(title_texts, ["BAĞIMLI"])

    def test_multiline_revised_subtitle_credit_is_removed(self):
        credit = "Revised English subtitles\nby sineintegral@KG"
        self.assertTrue(gui._source_cue_is_delivery_removable(credit))
        result = gui._prepare_upload_ready_blocks(
            [("1528", "01:30:00,000 --> 01:30:02,000", "[ÇEVİRİ EKSİK]")],
            "Turkish",
            source_cues=[("1528", "01:30:00,000 --> 01:30:02,000", credit)],
        )
        self.assertFalse(any("EKSİK" in text for _idx, _ts, text in result))

    def test_ahd_creator_credit_is_removed(self):
        credit = (
            "Subtitles created using AHD Subtitles Maker Professional\n"
            "E-mail: ahdsoftwares@hotmail.com"
        )
        self.assertTrue(gui._source_cue_is_delivery_removable(credit))
        self.assertTrue(gui._source_cue_is_delivery_removable(
            "Subtitles created by Basti"))

    def test_middle_signature_avoids_out_of_order_overlap(self):
        blocks = [
            ("1", "00:00:00,000 --> 00:00:01,000", "Bir"),
            ("2", "00:00:10,000 --> 00:00:12,000", "İki"),
            ("3", "00:00:09,000 --> 00:00:10,500", "Üç"),
            ("4", "00:00:14,000 --> 00:00:16,000", "Dört"),
        ]
        _pos, start, end = gui._delivery_middle_signature_slot(blocks)
        dialogue = [gui._srt_timestamp_bounds(ts) for _idx, ts, _text in blocks]
        self.assertFalse(any(start < other_end and other_start < end
                             for other_start, other_end in dialogue))

    def test_embedded_source_credit_lines_do_not_remove_real_title(self):
        source = [("26", "00:00:02,000 --> 00:00:05,000",
                   "~ RUN MELOS! ~\nSubtitles by Odyssey\nOCR by Inactive (Subs.com.ru)")]
        blocks = [("26", source[0][1],
                   "~ KOS, MELOS! ~\nAltyazi: Odyssey\nOCR: Inactive (Subs.com.ru)")]

        result = gui._prepare_upload_ready_blocks(
            blocks, "Turkish", source_cues=source)
        dialogue = [text for _idx, _ts, text in result
                    if text != "discord: ceviri2"]

        self.assertEqual(dialogue, ["~ KOS, MELOS! ~"])
        self.assertFalse(gui._source_cue_is_delivery_removable(source[0][2]))

    def test_ocr_misspelled_subtitling_credit_is_removed(self):
        blocks = [
            ("1", "00:00:02,000 --> 00:00:03,000", "Subtifling: Eclair Group"),
            ("2", "00:00:04,000 --> 00:00:05,000", "Gercek diyalog."),
        ]
        result = gui._prepare_upload_ready_blocks(blocks, "Turkish")
        joined = "\n".join(text for _i, _ts, text in result)
        self.assertNotIn("Eclair", joined)
        self.assertIn("Gercek diyalog.", joined)

    def test_ampersand_credit_continuation_is_not_missing_dialogue(self):
        credit = "Subtitles: Paul J. MEMMI\n& Nico PAPATAKIS"
        self.assertTrue(gui._source_cue_is_delivery_removable(credit))
        result = gui._prepare_upload_ready_blocks(
            [("810", "00:00:02,000 --> 00:00:03,000", credit)],
            "Turkish",
            source_cues=[("810", "00:00:02,000 --> 00:00:03,000", credit)],
        )
        self.assertFalse(any(text == credit for _idx, _ts, text in result))

    def test_bare_subtitling_header_followed_by_site_is_removed(self):
        credit = "Subtitling:\nwww.pluridioma.pt"
        self.assertTrue(gui._source_cue_is_delivery_removable(credit))
        result = gui._prepare_upload_ready_blocks(
            [("535", "01:00:00,000 --> 01:00:02,000", "[ÇEVİRİ EKSİK]")],
            "Turkish",
            source_cues=[("535", "01:00:00,000 --> 01:00:02,000", credit)],
        )
        self.assertFalse(any("EKSİK" in text for _idx, _ts, text in result))


    def test_superior_court_heading_is_required_dialogue(self):
        self.assertFalse(gui._source_cue_is_delivery_removable("Superior Court:"))
        result = gui._prepare_upload_ready_blocks(
            [("516", "00:46:07,230 --> 00:46:08,891", "Yüksek Mahkeme:")],
            "Turkish",
            source_cues=[(
                "516", "00:46:07,230 --> 00:46:08,891", "Superior Court:")],
        )
        self.assertTrue(any(
            text == "Yüksek Mahkeme:" for _idx, _ts, text in result))

    def test_copyright_and_subtitler_cue_is_removed(self):
        credit = "Copyright © 1999 TITE LBI LD, Berlin\nSubtitler: Alan Wildblood et al."
        self.assertTrue(gui._source_cue_is_delivery_removable(credit))
        result = gui._prepare_upload_ready_blocks(
            [("1", "00:00:01,000 --> 00:00:03,000", "Telif Hakkı 1999\nAlan Wildblood")],
            "Turkish",
            source_cues=[("1", "00:00:01,000 --> 00:00:03,000", credit)],
        )
        self.assertFalse(any("Wildblood" in text for _idx, _ts, text in result))


if __name__ == "__main__":
    unittest.main()
