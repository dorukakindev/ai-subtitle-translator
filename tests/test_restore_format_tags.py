"""
restore_format_tags ve GUI prev_scene köprüsü testleri.
Bağlam: _clean_src çeviri öncesi <i>/{\\an8} etiketlerini söker; bu modül
çeviri sonrası geri yüklemeyi doğrular.
"""
import json
import os
import tempfile
import unittest

import subtitle_translator_gui as gui


class CleanSourceTagsTest(unittest.TestCase):
    def test_empty_ass_override_tag_is_removed_without_touching_unmatched_brace(self):
        self.assertEqual(gui._clean_src(r"{}Hello {\i1}world{\i0}"), "Hello world")
        self.assertEqual(gui._clean_src("A literal { stays"), "A literal { stays")
        self.assertEqual(
            gui._clean_src(r"Type {username} here. {\an8}"),
            "Type {username} here.",
        )

from subtitle_formats import restore_format_tags


class RestoreFormatTagsTest(unittest.TestCase):
    def test_full_italic_wrap(self):
        self.assertEqual(restore_format_tags("<i>I was here.</i>", "Buradaydım."),
                         "<i>Buradaydım.</i>")

    def test_nested_wrap(self):
        self.assertEqual(restore_format_tags("<b><i>Run!</i></b>", "Kaç!"),
                         "<b><i>Kaç!</i></b>")

    def test_font_wrap(self):
        out = restore_format_tags('<font color="#ffff00">Hello.</font>', "Merhaba.")
        self.assertEqual(out, '<font color="#ffff00">Merhaba.</font>')

    def test_leading_position_tag_is_removed_from_srt(self):
        self.assertEqual(restore_format_tags(r"{\an8}STREET SIGN", "SOKAK TABELASI"),
                         "SOKAK TABELASI")

    def test_position_plus_italic(self):
        out = restore_format_tags(r"{\an8}<i>narrator voice</i>", "anlatıcı sesi")
        self.assertEqual(out, "<i>anlatıcı sesi</i>")

    def test_per_line_wrap(self):
        src = "<i>line one</i>\n<i>line two</i>"
        out = restore_format_tags(src, "satır bir\nsatır iki")
        self.assertEqual(out, "<i>satır bir</i>\n<i>satır iki</i>")

    def test_partial_inline_tags_not_restored(self):
        # Satır içi kısmi etiket güvenle geri konamaz — çeviri değişmemeli
        src = "he said <i>never</i> again"
        self.assertEqual(restore_format_tags(src, "bir daha asla dedi"),
                         "bir daha asla dedi")

    def test_untagged_source_unchanged(self):
        self.assertEqual(restore_format_tags("Plain line.", "Düz satır."), "Düz satır.")

    def test_idempotent_when_translation_already_tagged(self):
        self.assertEqual(restore_format_tags("<i>Hi.</i>", "<i>Selam.</i>"),
                         "<i>Selam.</i>")
        self.assertEqual(restore_format_tags(r"{\an8}Sign", r"{\an8}Tabela"),
                         "Tabela")

    def test_hata_lines_untouched(self):
        self.assertEqual(restore_format_tags("<i>Hi.</i>", "[HATA]"), "[HATA]")

    def test_empty_inputs(self):
        self.assertEqual(restore_format_tags("", "Çeviri."), "Çeviri.")
        self.assertEqual(restore_format_tags("<i>Hi.</i>", ""), "")

    def test_vtt_metadata_tags_do_not_leak_into_srt_output(self):
        self.assertEqual(restore_format_tags("<c.yellow>Yellow text</c>", "Sarı metin"),
                         "Sarı metin")
        self.assertEqual(restore_format_tags("<v Roger>Voice text</v>", "Ses metni"),
                         "Ses metni")
        self.assertEqual(restore_format_tags("<lang en>English text</lang>", "İngilizce metin"),
                         "İngilizce metin")
        self.assertEqual(
            restore_format_tags("<i><v Roger>Voice text</v></i>", "Ses metni"),
            "<i>Ses metni</i>")

    def test_math_operators_inside_and_outside_tags(self):
        # Etiket içindeki matematiksel < / > operatörleri
        self.assertEqual(restore_format_tags("<i>x < 5 and y > 3</i>", "x < 5 ve y > 3"),
                         "<i>x < 5 ve y > 3</i>")
        # Düz metindeki matematiksel < / > etiket sayılmamalı
        self.assertEqual(restore_format_tags("If x < 5 and y > 3", "x < 5 ve y > 3 ise"),
                         "x < 5 ve y > 3 ise")

    def test_ass_override_tags_restored(self):
        self.assertEqual(restore_format_tags(r"{\an8}{\c&H00FFFF&}Top text", "Üst metin"),
                         "Üst metin")
        self.assertEqual(restore_format_tags(r"{\i1}Italic ASS{\i0}", "İtalik ASS"),
                         r"{\i1}İtalik ASS{\i0}")

    def test_ass_position_and_rotation_are_removed_from_srt(self):
        self.assertEqual(
            restore_format_tags(r"{\frz345.405\pos(302, 129)}YELLOW LINE", "SARI ÇİZGİLİ"),
            "SARI ÇİZGİLİ",
        )

    def test_safe_italic_survives_mixed_position_override(self):
        self.assertEqual(
            restore_format_tags(
                r"{\pos(332,52)\i1}I dreamed of this day{\i0}",
                "Bu günü düşledim",
            ),
            r"{\i1}Bu günü düşledim{\i0}",
        )

    def test_literal_braced_dialogue_is_not_reappended_from_source(self):
        self.assertEqual(
            restore_format_tags(
                "(TV/Radio) {Now he is lying paralysed,\nbut I can assure you of...}",
                "(TV/Radio) {Şimdi felçli yatıyor,\nama size şunun sözünü verebilirim:}",
            ),
            "(TV/Radio) {Şimdi felçli yatıyor,\nama size şunun sözünü verebilirim:}",
        )
        self.assertEqual(
            restore_format_tags(
                "...{what has happened with Patel,\nwon't let it happen to you...}",
                "...{Patel'in başına gelenlerin\nsize de olmasına izin vermeyeceğiz...}",
            ),
            "...{Patel'in başına gelenlerin\nsize de olmasına izin vermeyeceğiz...}",
        )



class RestoreTagsBlocksTest(unittest.TestCase):
    def test_blocks_helper(self):
        raw_map = {"1": "<i>Hello.</i>", "2": "Plain."}
        blocks = [("1", "ts", "Merhaba."), ("2", "ts", "Düz."), ("3", "ts", "Eksik.")]
        out = gui._restore_tags_blocks(blocks, raw_map)
        self.assertEqual(out[0][2], "<i>Merhaba.</i>")
        self.assertEqual(out[1][2], "Düz.")
        self.assertEqual(out[2][2], "Eksik.")  # kaynak yoksa dokunma


class PrevSceneBridgeTest(unittest.TestCase):
    def test_scene_break_carries_bridge(self):
        # 2 chunk'lık dosya; ikinci chunk sahne boşluğuyla başlasın →
        # ctx yerine prev_scene köprüsü taşınmalı
        def ts(a, b):
            def f(s):
                return f"00:{int(s//60):02d}:{s%60:06.3f}".replace(".", ",")
            return f"{f(a)} --> {f(b)}"

        srt_lines = []
        t = 0.0
        for i in range(1, 7):
            srt_lines.append(f"{i}\n{ts(t, t+1.5)}\nLine {i}.\n")
            t += 2.0
            if i == 3:
                t += 30.0  # büyük sahne boşluğu
        fd, fp = tempfile.mkstemp(suffix=".srt"); os.close(fd)
        with open(fp, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        try:
            reqs, _ = gui.build_requests([fp], "English", "Turkish",
                                         "gpt-4.1-mini", chunk_size=3)
            self.assertEqual(len(reqs), 2)
            p2 = json.loads(reqs[1]["body"]["messages"][1]["content"])
            self.assertNotIn("ctx", p2, "sahne kırılınca ctx sıfırlanmalı")
            self.assertIn("prev_scene", p2, "sahne köprüsü taşınmalı")
            self.assertLessEqual(len(p2["prev_scene"]), 6)
        finally:
            os.unlink(fp)


if __name__ == "__main__":
    unittest.main()
