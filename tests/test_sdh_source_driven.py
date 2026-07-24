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

    def test_no_src_map_falls_back_to_legacy(self):
        # source_driven=True ama src_map YOK → eski beyaz-liste davranışına düşer,
        # çökmez (KRİTİK ön koşul: src_map yoksa source_driven çalışamaz).
        blocks = [("1", "00:00:01,000 --> 00:00:02,000", "[KAHKAHA]"),
                  ("2", "00:00:02,000 --> 00:00:03,000", "Normal replik.")]
        with_flag = sdh.clean_sdh_blocks(blocks, source_driven=True)
        legacy = sdh.clean_sdh_blocks(blocks)
        self.assertEqual(with_flag, legacy)
        self.assertEqual([b[0] for b in with_flag], ["2"])


if __name__ == "__main__":
    unittest.main()
