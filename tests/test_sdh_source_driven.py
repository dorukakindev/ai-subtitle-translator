"""Kaynak-güdümlü SDH temizliği — plans/sdh-kaynak-gutlu-temizlik-brief.md.

Sorun: sdh_cleaner._SDH_KEYWORDS elle yazılmış bir kelime beyaz listesi, ama
clean_sdh çeviriden SONRA çalışıyor — yani artık Türkçeleşmiş etiketlere
bakıyor. Gerçek ölçümde (The Blood of Hussain) 20 etiketten yalnızca 1'i
tanındı. Bu dosya yeni source_driven=True yolunu kilitler: ayırt edici işaret
PARANTEZİN KENDİSİ (kaynakta var mı), içindeki kelimeler değil.

source_driven=False (varsayılan) davranışı bu dosyada test EDİLMEZ — o zaten
tests/test_sdh_cleaner_extended.py, tests/test_write_srt_output.py,
tests/test_speaker_labels.py, tests/test_merge_cues.py ve
tests/test_silent_empty_cue_loss.py tarafından korunuyor ve bu değişiklikle
hiçbiri değişmedi.
"""
import unittest

import sdh_cleaner as sdh


def _src(**kw):
    return {str(k): v for k, v in kw.items()}


class SdhSourceDrivenTest(unittest.TestCase):
    def test_bare_french_sdh_is_removed_from_whole_and_mixed_cues(self):
        self.assertTrue(sdh.src_is_sfx_only("Musique douce instrumentale"))
        self.assertTrue(sdh.src_is_sfx_only("La porte s'ouvre"))
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Yumuşak müzik"),
            ("2", "00:00:03,000 --> 00:00:04,000", "Fısıldar\nUzun kalmayacağım."),
        ]
        src_map = {
            "1": "Musique douce instrumentale",
            "2": "Elle chuchote\nJe reste pas longtemps.",
        }
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [("2", blocks[1][1], "Fısıldar\nUzun kalmayacağım.")])

    def test_bare_french_sdh_line_is_removed_from_mixed_cue(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "Gerilim müziği\nAh, onu değil!")]
        src_map = {"1": "Musique inquiétante\nAh, pas ça !"}
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "Ah, onu değil!")

    def test_common_english_sdh_phrases_are_source_sfx(self):
        samples = [
            "[thundering]", "[raining]", "[train whistles]",
            "[Chanting of holy verses in praise of Lord Vishnu]",
            "[engine starts]", "[car honks]", "[all laugh]",
            "[indistinct conversation]", "[Eli breathing heavily]",
            "[inhales, shivers]",
        ]
        for sample in samples:
            self.assertTrue(sdh.src_is_sfx_only(sample), msg=sample)

    def test_live_run_parenthetical_effects_are_source_sfx(self):
        samples = [
            "(vomits)", "(disappointed grunt)", "(breathes noisily)",
            "(weeps)", "(Geoff yelps)", "(loud kissing noises)",
            "(orgasms noisily)", "(makes modem dialling noises)",
            "(# \"Singin' in the Rain\")",
            "- (Anne sobs)\n- (door bursts open)",
            "(chokes)", "(zip)", "(sniffs)", "(cat wails)", "(yawns)",
            "(sirens)", "(thud)", "(machine whirrs)",
            "(# theme from \"The A-Team\")", "(feedback)",
            "(Nokia ringtone)", "('80s-style cheesy solo)", "(yelp)",
            "(bleeping)",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(sdh.src_is_sfx_only(sample), msg=sample)

    def test_mojibake_music_ornament_does_not_turn_sfx_into_dialogue(self):
        for sample in ("Âª[playing]", "Aª[violin playing]", "ª[piano playing]"):
            with self.subTest(sample=sample):
                self.assertTrue(sdh.src_is_sfx_only(sample))
        self.assertFalse(sdh.src_is_sfx_only("1ª classe"))

    def test_verified_pumpkin_eater_and_russian_sdh_are_source_sfx(self):
        samples = [
            "(SLAMS DRAWER SHUT)", "(PIANO BEING TUNED)",
            "(PAGES FLICKING LOUDLY)", "- (CHURCH BELLS)\n- (CHATTERING)",
            "(CHURCH BELL)", "(KEY TURNING IN LOCK)", "Музыка!",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(sdh.src_is_sfx_only(sample))

    def test_chevron_speaker_markers_stripped(self):
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", ">> Merhaba."),
            ("2", "00:00:02,000 --> 00:00:03,000", "&gt;&gt; Dünya."),
        ]
        src_map = _src(**{"1": ">> Hello.", "2": "&gt;&gt; World."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            {idx: text for idx, _ts, text in result},
            {"1": "Merhaba.", "2": "Dünya."},
        )

    def test_inline_narrator_label_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "Bunun karşılığı yok. Anlatıcı: Zırhlı balıklar artık yok.",
        )]
        src_map = _src(**{
            "1": "There are no modern analogues to this. >> Narrator: "
                 "Though armored fish no longer exist."
        })
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "Bunun karşılığı yok. Zırhlı balıklar artık yok.",
        )

    def test_narrator_word_preserved_without_source_marker(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "Anlatıcı: güvenilmez olabilir.",
        )]
        src_map = _src(**{"1": "The narrator may be unreliable."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "Anlatıcı: güvenilmez olabilir.",
        )

    def test_plain_speaker_label_stripped_by_source(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "HABER SPİKERİ: Her şey burada başladı.",
        )]
        src_map = _src(**{"1": "NEWS ANCHOR: It all started here."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "Her şey burada başladı.",
        )

    def test_title_case_and_inline_speaker_labels_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "Troy: Hayır. Röportajcı: Size ateş etti mi?",
        )]
        src_map = _src(**{
            "1": "Troy: NO. Interviewer: DID HE SHOOT AT YOU?"
        })
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "Hayır. Size ateş etti mi?",
        )

    def test_bracket_source_label_plain_translation_label_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            'Ses: "Dışarı çık."',
        )]
        src_map = _src(**{"1": '[Voice] "Go outside."'})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            '"Dışarı çık."',
        )

    def test_comma_quote_source_label_plain_translation_label_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            'Ses: "Otur."',
        )]
        src_map = _src(**{"1": 'Voice, "Sit."'})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            '"Otur."',
        )

    def test_plain_label_only_line_is_dropped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "JOHN:\nBunu bilmiyordum.",
        )]
        src_map = _src(**{"1": "JOHN:\nI didn't know that."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "Bunu bilmiyordum.",
        )

    def test_split_automated_voice_label_is_fully_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "OTOMATİK SES\nKayıt: Günaydın.",
        )]
        src_map = _src(**{"1": "AUTOMATED VOICE\nRECORDING: Good morning."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "Günaydın.")

    def test_split_voiceover_name_is_fully_stripped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "RAY BRADBURY\nİnsanlar sorar,",
        )]
        src_map = _src(**{"1": "RAY BRADBURY\n(VOICEOVER): People ask,"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "İnsanlar sorar,")

    def test_split_label_with_descriptor_only_is_dropped(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "OTOMATİK SES\n(GİDEREK KISILAN SES)",
        )]
        src_map = _src(**{
            "1": "AUTOMATED VOICE\nRECORDING: (FADING VOICE)"
        })
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [])

    def test_plain_colon_prose_preserved_without_source_label(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "SONUÇ: Bu ihtimal hâlâ geçerli.",
        )]
        src_map = _src(**{"1": "The result is that this remains possible."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "SONUÇ: Bu ihtimal hâlâ geçerli.",
        )

    def test_sentence_ending_with_colon_is_not_a_speaker_label(self):
        blocks = [(
            "1",
            "00:00:01,000 --> 00:00:02,000",
            "O kadar çok şey örtüşüyor ki:",
        )]
        src_map = _src(**{"1": "So many things line up:"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            dict((b[0], b[2]) for b in result)["1"],
            "O kadar çok şey örtüşüyor ki:",
        )

    def test_repeated_listen_imperative_is_not_a_speaker_label(self):
        blocks = [("595", "00:10:00,000 --> 00:10:02,000", "Simdi dinle. Iyi dinle:")]
        src_map = _src(**{"595": "Now, listen. Listen:"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "Simdi dinle. Iyi dinle:")

    def test_chevron_language_only_cue_dropped(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", ">> [anlaşılmayan konuşma]")]
        src_map = _src(**{"1": "&gt;&gt; [non-english]"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [])

    def test_src_sfx_only_cue_dropped(self):
        # Kaynak tamamen parantez → kural 1: çeviri cue'su tamamen silinir.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ÇAN SESLERİ]")]
        src_map = _src(**{"1": "(Bells jingling)"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertNotIn("1", [b[0] for b in result])

    def test_technical_or_dialogue_parentheses_are_not_sfx_only(self):
        for text in (
                "[OK]", "(No.)", "(f(x))", "(Hey!)", "(#1 choice)",
                "(Han Solo)"):
            with self.subTest(text=text):
                self.assertFalse(sdh.src_is_sfx_only(text))
        self.assertTrue(sdh.src_is_sfx_only("[door closes]"))

    def test_multiline_parenthetical_prose_is_not_dropped(self):
        cases = [
            ("(the grandmother\nwas from Tunisia)", "(büyükanne\nTunusluydu)"),
            ("(was originally composed\nsolely of Jews)",
             "(başlangıçta yalnızca\nYahudilerden oluşuyordu)"),
        ]
        for source, translation in cases:
            with self.subTest(source=source):
                self.assertFalse(sdh.src_is_sfx_only(source))
                result = sdh.clean_sdh_blocks(
                    [("1", "00:00:01,000 --> 00:00:02,000", translation)],
                    src_map=_src(**{"1": source}),
                    source_driven=True,
                )
                self.assertEqual(result[0][2], translation)

    def test_speaking_phrase_is_not_confused_with_speech_descriptor(self):
        self.assertFalse(sdh.is_sdh_descriptor("Speaking of which"))
        self.assertFalse(sdh.src_is_sfx_only("[Speaking of which]"))
        self.assertTrue(sdh.is_sdh_descriptor("woman speaking"))
        self.assertTrue(sdh.is_sdh_descriptor("speaking softly"))
        self.assertTrue(sdh.is_sdh_descriptor("woman screams"))
        self.assertTrue(sdh.is_sdh_descriptor("teeth chattering"))

        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "[Hazır konusu açılmışken]")]
        result = sdh.clean_sdh_blocks(
            blocks, src_map={"1": "[Speaking of which]"}, source_driven=True)
        self.assertEqual(result, blocks)

    def test_multiline_sfx_is_still_dropped(self):
        source = "(Bells\njingling)"
        self.assertTrue(sdh.src_is_sfx_only(source))
        result = sdh.clean_sdh_blocks(
            [("1", "00:00:01,000 --> 00:00:02,000", "(Çanlar\nçınlıyor)")],
            src_map=_src(**{"1": source}),
            source_driven=True,
        )
        self.assertEqual(result, [])

    def test_dash_prefixed_multiline_sfx_is_dropped(self):
        source = "- [scream]\n- [glass shattering]"
        self.assertTrue(sdh.src_is_sfx_only(source))
        self.assertFalse(sdh.src_is_sfx_only("- [scream]\n- Get out!"))
        result = sdh.clean_sdh_blocks(
            [("1", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]")],
            src_map=_src(**{"1": source}),
            source_driven=True,
        )
        self.assertEqual(result, [])

    def test_translated_exhale_label_is_stripped_by_source(self):
        self.assertEqual(
            sdh.strip_labels_by_source("[nefes verir] Ah!", "[exhales] Oh!"),
            "Ah!",
        )

    def test_source_sdh_does_not_strip_target_technical_parentheses(self):
        self.assertEqual(
            sdh.strip_labels_by_source(
                "(f(x)) değerini hesapla. [KAPI KAPANIR]",
                "[door closes] Calculate f(x).",
            ),
            "(f(x)) değerini hesapla.",
        )

    def test_position_tagged_sfx_only_cue_dropped(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ZİL ÇALIYOR]")]
        src_map = _src(**{"1": r"{\an8}(bell ringing)"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [])

    def test_inline_label_stripped_by_source(self):
        # Kaynak satırında parantez grubu var → kural 2: çeviridekiler sökülür,
        # kalan replik bırakılır.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "(Urduca konuşur) Yoldan çekilin!")]
        src_map = _src(**{"1": "(Speaks Urdu) Get out of the way!"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "Yoldan çekilin!")

    def test_speaker_label_stripped(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "(Kaptan) 'Havaalanı bomboş...'")]
        src_map = _src(**{"1": "(Captain) 'The airport is empty...'"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "'Havaalanı bomboş...'")

    def test_turkish_label_stripped_despite_whitelist(self):
        """ASIL REGRESYON KİLİDİ: '[ÇAN SESLERİ]' _SDH_KEYWORDS beyaz listesinde
        YOK — bu yüzden legacy (source_driven=False) yol onu tanıyamayıp sağ
        bırakıyor (bugünkü hata). Kaynak-güdümlü yol beyaz listeyi hiç
        sorgulamadan, yalnızca kaynağın yapısına bakarak doğru siliyor."""
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[ÇAN SESLERİ]")]
        src_map = _src(**{"1": "[BELLS RINGING]"})

        legacy = sdh.clean_sdh_blocks(blocks)  # source_driven=False (varsayılan), src_map yok
        self.assertIn("1", [b[0] for b in legacy],
                      "regresyon belgesi: beyaz liste 'çan sesleri'ni tanımıyor, satır hayatta kalıyor")

        fixed = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertNotIn("1", [b[0] for b in fixed],
                          "kaynak-güdümlü yol beyaz listeden bağımsız olarak silmeli")

    def test_lyric_with_notes_preserved(self):
        # ♪ tek başına parantez DEĞİL → kural 3: dokunma, şarkı sözü korunur.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "♪ Seni seviyorum ♪")]
        src_map = _src(**{"1": "♪ I love you ♪"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "♪ Seni seviyorum ♪")

    def test_prose_paren_in_translation_preserved(self):
        # Kaynakta parantez YOK → çevirideki parantez gerçek nesir olabilir, dokunma.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "(Seyirci bunu sevdi)")]
        src_map = _src(**{"1": "The audience loved it"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "(Seyirci bunu sevdi)")

    def test_dialogue_dash_preserved(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "- (Pencapça konuşur) Ne oldu?")]
        src_map = _src(**{"1": "- (Speaks Punjabi) What happened?"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "- Ne oldu?")

    def test_dash_only_line_dropped(self):
        # Etiket sökülünce yalnızca '-' kalıyorsa satır (ve tek satırlı cue) düşer.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "- [KIKIRDAR]")]
        src_map = _src(**{"1": "- [Chuckles]"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [])

    def test_format_tags_preserved(self):
        # <i>/<b> biçim etiketlerine source_driven modda da dokunulmaz.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "(Kaptan) <i>Selamünaleyküm.</i>")]
        src_map = _src(**{"1": "(Captain) Peace be upon you."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "<i>Selamünaleyküm.</i>")

    def test_mixed_sdh_and_location_brackets_preserve_location(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[MUSIC] [PARIS]")]
        src_map = _src(**{"1": "[MUSIC] [PARIS]"})
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "[PARIS]")

    def test_mixed_unknown_translated_sdh_uses_source_group_positions(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "[boğuk bir titreşim duyulur] [PARİS]")]
        src_map = _src(**{"1": "[OMINOUS MUSIC] [PARIS]"})
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "[PARİS]")

    def test_mixed_sdh_and_heading_brackets_preserve_heading(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "[MUSIC] [CHAPTER ONE]")]
        src_map = _src(**{"1": "[MUSIC] [CHAPTER ONE]"})
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "[CHAPTER ONE]")

    def test_double_space_collapsed(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "Merhaba (gülüyor) dünya.")]
        src_map = _src(**{"1": "Hello (laughs) world."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "Merhaba dünya.")

    def test_orphaned_colon_after_bracket_stripped(self):
        # Model ham çeviride '[Name]: metin' biçimini aynen koruyor; bracket
        # sökülünce ':' satır başında sarkık kalmamalı.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "[Caine]: Hoş geldin!")]
        src_map = _src(**{"1": "[Caine]: Welcome!"})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "Hoş geldin!")

    def test_orphaned_colon_only_label_line_dropped(self):
        # Etiket satırında replik hiç yoksa ('[Name]:' tek başına) satır boşalır.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "[Zooble]:\nHayır.")]
        src_map = _src(**{"1": "[Zooble]:\nNope."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "Hayır.")

    def test_orphaned_colon_with_dash_keeps_dash(self):
        # '-[Name]: metin' -> tire diyalog işareti olarak kalmalı, ':' gitmeli.
        blocks = [("1", "00:00:01,000 --> 00:00:02,000",
                   "-[Kinger]: Bu şurupla dolu.")]
        src_map = _src(**{"1": "-[Kinger]: This one's full of syrup."})
        result = sdh.clean_sdh_blocks(blocks, src_map=src_map, source_driven=True)
        self.assertEqual(dict((b[0], b[2]) for b in result)["1"], "-Bu şurupla dolu.")

    def test_dialogue_sentence_ending_with_colon_is_not_a_speaker_label(self):
        blocks = [("144", "00:00:01,000 --> 00:00:02,000",
                   "Yargıç şuna karar verdi:")]
        src_map = _src(**{"144": "[Trent] The judge made the decision"})
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "Yargıç şuna karar verdi:")

    def test_numbered_sheriff_and_tv_speaker_labels_are_stripped(self):
        blocks = [
            ("3", "00:00:01,000 --> 00:00:02,000",
             "[şerif 1] Şerif Departmanı."),
            ("19", "00:00:02,000 --> 00:00:03,000",
             "[TV'deki adam] Son dakika."),
        ]
        src_map = _src(**{
            "3": "[sheriff 1] Sheriff's Department.",
            "19": "[man 2 on TV] Breaking news.",
        })
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            {idx: text for idx, _ts, text in result},
            {"3": "Şerif Departmanı.", "19": "Son dakika."},
        )

    def test_action_descriptors_with_adverbs_are_stripped(self):
        blocks = [
            ("146", "00:00:01,000 --> 00:00:02,000",
             "Biraz kalabalıktı. [üzgün gülüş]"),
            ("391", "00:00:02,000 --> 00:00:03,000",
             "[KADINLAR HEYECANLA BAĞIRIYOR]"),
        ]
        src_map = _src(**{
            "146": "It was crowded. [laughs sadly]",
            "391": "[women yell enthusiastically]",
        })
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [
            ("146", "00:00:01,000 --> 00:00:02,000", "Biraz kalabalıktı."),
        ])

    def test_mixed_sfx_and_named_speaker_prefixes_are_both_stripped(self):
        blocks = [(
            "526", "00:00:01,000 --> 00:00:02,000",
            "- [kalabalığın çığlıkları]\n- [Ron] Bir savaşımız vardı.",
        )]
        src_map = _src(**{
            "526": "- [crowd screaming]\n- [Ron] We had a battle.",
        })
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result[0][2], "- Bir savaşımız vardı.")

    def test_no_src_map_falls_back_to_legacy(self):
        # source_driven=True ama src_map YOK → eski beyaz-liste davranışına düşer,
        # çökmez (KRİTİK ön koşul: src_map yoksa source_driven çalışamaz).
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[KAHKAHA]"),
                  ("2", "00:00:02,000 --> 00:00:03,000", "Normal replik.")]
        with_flag = sdh.clean_sdh_blocks(blocks, source_driven=True)
        legacy = sdh.clean_sdh_blocks(blocks)
        self.assertEqual(with_flag, legacy)
        self.assertEqual([b[0] for b in with_flag], ["2"])

    def test_failure_marker_survives_mixed_sdh_and_dialogue_source(self):
        blocks = [
            ("190", "00:00:01,000 --> 00:00:02,000", "[ÇEVİRİ EKSİK]"),
            ("409", "00:00:02,000 --> 00:00:03,000", "[HATA]"),
        ]
        src_map = _src(**{
            "190": "- [Ben laughs]\n- Would you like to see?",
            "409": "- [Audience laughing]\n- Oh, shit.",
        })
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(
            {idx: text for idx, _ts, text in result},
            {"190": "[ÇEVİRİ EKSİK]", "409": "[HATA]"},
        )

    def test_failure_marker_for_sfx_only_source_is_still_dropped(self):
        blocks = [("313", "00:00:01,000 --> 00:00:02,000", "[HATA]")]
        src_map = _src(**{"313": "[organ music playing]"})
        result = sdh.clean_sdh_blocks(
            blocks, src_map=src_map, source_driven=True)
        self.assertEqual(result, [])

    def test_vtt_voice_wrapped_pure_sfx_is_dropped(self):
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "KAPI KAPANIR")]
        result = sdh.clean_sdh_blocks(
            blocks,
            src_map=_src(**{"1": "<v SFX>[door closes]</v>"}),
            source_driven=True,
        )
        self.assertEqual(result, [])
        self.assertFalse(sdh.src_is_sfx_only("<v Roger>Hello</v>"))

    def test_equal_multiline_cue_uses_line_aligned_source(self):
        blocks = [(
            "1", "00:00:01,000 --> 00:00:03,000",
            "[KAPI KAPANIR]\n(aslında bu önemli) devam et.",
        )]
        result = sdh.clean_sdh_blocks(
            blocks,
            src_map=_src(**{"1": "[door closes]\nActually, continue."}),
            source_driven=True,
        )
        self.assertEqual(
            result[0][2], "(aslında bu önemli) devam et.")


if __name__ == "__main__":
    unittest.main()
