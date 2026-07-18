"""
write_srt: çıktı HER ZAMAN .srt olmalı (VTT/ASS girdilerde de) ve metindeki çift+
newline'lar SRT blok ayracını (\\n\\n) taklit edip yeniden okumada satır düşürmemeli.
"""
import os
import tempfile
import unittest

import hybrid_translate as ht
import sdh_cleaner
import subtitle_translator_gui as gui


class WriteSrtOutputTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_vtt_path_writes_srt(self):
        # .vtt yola yazsak bile çıktı .srt olmalı (eskiden .vtt içinde SRT içeriği = oynatılamaz)
        gui.write_srt(os.path.join(self.d, "movie.vtt"),
                      [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba")])
        self.assertTrue(os.path.exists(os.path.join(self.d, "movie.srt")))
        self.assertFalse(os.path.exists(os.path.join(self.d, "movie.vtt")))

    def test_ass_path_writes_srt(self):
        gui.write_srt(os.path.join(self.d, "movie.ass"),
                      [("1", "00:00:01,000 --> 00:00:02,000", "Selam")])
        self.assertTrue(os.path.exists(os.path.join(self.d, "movie.srt")))

    def test_srt_path_unchanged(self):
        p = os.path.join(self.d, "a.srt")
        gui.write_srt(p, [("1", "00:00:01,000 --> 00:00:02,000", "x")])
        self.assertTrue(os.path.exists(p))

    def test_double_newline_collapsed_roundtrips(self):
        p = os.path.join(self.d, "b.srt")
        gui.write_srt(p, [("1", "00:00:01,000 --> 00:00:02,000", "satır1\n\n\nsatır2")])
        blocks = gui.parse_srt(p)
        self.assertEqual(len(blocks), 1)                 # tek blok kaldı (bölünmedi)
        self.assertEqual(blocks[0][2], "satır1\nsatır2") # boş satır temizlendi

    def test_empty_text_is_marked_instead_of_dropping_cue(self):
        p = os.path.join(self.d, "empty.srt")
        gui.write_srt(p, [
            ("1", "00:00:01,000 --> 00:00:02,000", ""),
            ("2", "00:00:02,000 --> 00:00:03,000", "Sonraki satır."),
        ])
        blocks = gui.parse_srt(p)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0][2], "[ÇEVİRİ EKSİK]")

    def test_write_normalizes_english_sdh_descriptors(self):
        p = os.path.join(self.d, "sdh.srt")
        gui.write_srt(p, [
            ("1", "00:00:01,000 --> 00:00:02,000", "(AUDIENCE LAUGHING)"),
            ("2", "00:00:02,000 --> 00:00:03,000", "-(DISCO MUSIC PLAYING)\nAUDIENCE: Again!"),
        ])
        blocks = gui.parse_srt(p)
        self.assertEqual(blocks[0][2], "(SEYİRCİ KAHKAHA ATIYOR)")
        self.assertEqual(blocks[1][2], "-(DİSKO MÜZİĞİ ÇALIYOR)\nSEYİRCİ: Again!")

    def test_write_normalizes_unicode_and_tabs(self):
        p = os.path.join(self.d, "unicode.srt")
        gui.write_srt(p, [("1", "00:00:01,000 --> 00:00:02,000", "o\u0308yle\tmi?")])
        blocks = gui.parse_srt(p)
        self.assertEqual(blocks[0][2], "öyle mi?")

    def test_write_normalizes_cyrillic_latin_homoglyphs(self):
        p = os.path.join(self.d, "homoglyph.srt")
        gui.write_srt(p, [("1", "00:00:01,000 --> 00:00:02,000", "O da BАNA geldi.")])
        raw = open(p, encoding="utf-8").read()
        self.assertIn("BANA", raw)
        self.assertNotIn("\u0410", raw)

    def test_sdh_descriptor_translation_does_not_touch_parenthetical_prose(self):
        text = sdh_cleaner.normalize_sdh_descriptors("(The audience loved it)")
        self.assertEqual(text, "(The audience loved it)")

    def test_sdh_cleaner_preserves_music_notes_inside_lyrics(self):
        lyric = "\u266a Seni seviyorum \u266a"
        self.assertEqual(sdh_cleaner.strip_sdh_line(lyric), lyric)
        self.assertEqual(sdh_cleaner.strip_sdh_line("\u266a"), "")

    def test_hybrid_output_normalizer_matches_write_cleanup(self):
        text = ht._normalize_output_text("(AUDIENCE LAUGHING)\nAUDIENCE:\to\u0308yle\n\nmi?")
        self.assertEqual(text, "(SEYİRCİ KAHKAHA ATIYOR)\nSEYİRCİ: öyle\nmi?")

    def test_hybrid_output_normalizer_cleans_latin_homoglyphs(self):
        text = ht._normalize_output_text("O da BАNA kavanozda şeyler getirdi.")
        self.assertEqual(text, "O da BANA kavanozda şeyler getirdi.")

    def test_hybrid_output_normalizer_cleans_s03e20_artifacts(self):
        text = ht._normalize_output_text(
            "Ya bize katılırsın\nyada aidatını ödersin.\n"
            "Bu mekanik saat işi oreriler.\n"
            "bu elektromıknatısların açabiliyorum.\n"
            "Ona tuaf bir şey almalıyım.\n"
            "Orada eski bir hapishanede\nyasıyoruz."
        )
        self.assertEqual(
            text,
            "Ya bize katılırsın\nya da aidatını ödersin.\n"
            "Bu mekanik saat mekanizmalı gök modelleri.\n"
            "bu elektromıknatısları açabiliyorum.\n"
            "Ona tuhaf bir şey almalıyım.\n"
            "Orada eski bir hapishanede\nyaşıyoruz.",
        )

    def test_hybrid_output_normalizer_cleans_turkic_artifacts(self):
        text = ht._normalize_output_text(
            "Bir bäýram/holidaý oturylyşyğı.\n"
            "Bir taksidermiya ortadagy bezeg.\n"
            "Avtomatonofobi ve ventriloq.\n"
            "ventriloquistler'in ürkütücü olduğunu düşünüyor.\n"
            "Partlatılmış kəllə, patlatılmış kâse, chiropraktör.\n"
            "Bir kelle alıp bir kelle tasarlamam gerekiyor.\n"
            "HEY, ÇOK DÜŞÜNDÜRÜCÜSÜN, DOSTUM.\n"
            "Mummy parts, mummy'nin phallus'u authentic.\n"
            "Ben \"repeat customer\"ım ve uppercut değil yükseltme indirebilir.\n"
            "- NOW, THE SECOND THING,\n- OTHER THAN THE DARK COLOR,\n"
            "- THAT WE WOULD NORMALLY LOOK FOR - IS\nGILDING... SO, AS WE SEE ON THE MASK HERE,\n"
            "THIS APPLICATION OF GOLD LEAF.\n"
            "AND WE TEND TO SEE THAT ON THE\nGENITALIA, ON BOTH OF MALES AND FEMALES.\n"
            "ON THE ACTUAL MUMMY ITSELF?\n"
            "ON THE LINEN WRAPPINGS.\n"
            "SO WE WOULD EXPECT TO SEE\nIT ON SOMETHING LIKE THIS.\n"
            "MINICIK, TINY yarasa penisi.\n"
            "FARKLI KAFATLARI.\n"
            "Jaal ile dans etmek zor mu?\n"
            "- Jaalimi görmek ister misin?\n"
            "- çünkü benim de - birkaç jalam var.\n"
            "Düğmeye basma beni yavrum.\n"
            "Protez enjamlary ve polio için brasekler.\n"
            "Mortuary school'a gittim ve wound-filler'ı kullandım.\n"
            "Ben sideshow performerım; body modification collection'ında çalışıyorum.\n"
            "Şu rat'le indirim koparabilir miyiz?\n"
            "Bizim bir client’ımızın client için macabre tarzında macabre mobile'ında işi var.\n"
            "Lukmançylyk degişli zatlar, basically kanatır.\n"
            "koroner's office'i için coroner's gurney, table istiyor.\n"
            "HUNTER VE SEÇEREK...\n"
            "bir gerçek boy ölüm maskesi yapmak için.\n"
            "o'nu\n"
            "İsrael"
        )
        self.assertEqual(
            text,
            "Bir yılbaşı partisi.\n"
            "Bir taksidermi masa süsü.\n"
            "otomatonofobi ve ventrilok.\n"
            "ventrilokların ürkütücü olduğunu düşünüyor.\n"
            "patlatılmış kafatası, patlatılmış kafatası, kiropraktör.\n"
            "bir kafatası alıp bir kafatası tasarlamam gerekiyor.\n"
            "HEY, sağ ol, dostum.\n"
            "Mumya parçaları, mumyanın fallusu gerçek.\n"
            "Ben devamlı müşteriyim ve uppercut değil aparkat indirebilir.\n"
            "- Şimdi ikinci şey,\n- koyu rengin dışında,\n"
            "- normalde arayacağımız şey\naltın yaldızdır... Maskede gördüğümüz gibi,\n"
            "Bu altın varak uygulaması.\n"
            "Bunu genelde hem erkeklerde hem kadınlarda\ngenital bölgede görürüz.\n"
            "Gerçek mumyanın üzerinde mi?\n"
            "Keten sargılarda.\n"
            "Böyle bir şeyde de\nonu görmeyi beklerdik.\n"
            "MİNİCİK yarasa penisi.\n"
            "FARKLI KAFATASLARI.\n"
            "yara iziyle dans etmek zor mu?\n"
            "- yara izimi görmek ister misin?\n"
            "- çünkü benim de - birkaç yara izim var.\n"
            "Beni düğmeye bastırma yavrum.\n"
            "Protez cihazlar ve polio korseleri.\n"
            "cenaze hizmetleri okuluna gittim ve yara dolgusunu kullandım.\n"
            "Ben yan gösteri sanatçısıyım; beden modifikasyonu koleksiyonunda çalışıyorum.\n"
            "Şu sıçanla indirim koparabilir miyiz?\n"
            "müşterilerimizden birinin müşterimiz için ürkütücü/ölüm temalı ürkütücü arabasında işi var.\n"
            "tıbbi şeyler, temelde kanatır.\n"
            "adli tabip ofisini için adli tabip sedyesi, masa istiyor.\n"
            "ARAŞTIRIP SEÇEREK...\n"
            "bir yaşam maskesi yapmak için.\n"
            "onu\n"
            "Israel",
        )


if __name__ == "__main__":
    unittest.main()
