"""plans/program-bug-brief-2026-08-19.md — 78 dosyalık teslim taramasından çıkan
bulguların regresyon kilidi. Her test brief'teki gerçek dosya kanıtına dayanır.
"""
import tempfile
import unittest
from pathlib import Path

import subtitle_formats as sf
import subtitle_translator_gui as gui


class MissingPlaceholderReachesFinalTest(unittest.TestCase):
    """P0-1: '[ÇEVİRİ EKSİK]' nihai dosyaya çıkıyordu (4 dosyada 5 örnek)."""

    def test_empty_cue_counts_as_missing(self):
        # write_srt boş metni diske '[ÇEVİRİ EKSİK]' olarak yazar; sayım da görmeli
        blocks = [
            ("1", "00:00:01,000 --> 00:00:02,000", "Normal satır."),
            ("2", "00:00:02,000 --> 00:00:03,000", "   "),
        ]
        self.assertEqual(gui._count_hata_cps(blocks)[0], 1)

    def test_placeholder_is_listed_with_timestamp(self):
        blocks = [
            ("189", "00:12:30,000 --> 00:12:32,000", "Dolu satır."),
            ("190", "00:12:32,000 --> 00:12:34,000", "[ÇEVİRİ EKSİK]"),
        ]
        self.assertEqual(gui._hata_index_entries(blocks), ["190 (00:12:32)"])


class ContentOffsetDetectorTest(unittest.TestCase):
    """P0-2: 27 cue'luk içerik kayması bölgeleri hiç yakalanmıyordu."""

    NAMES = ["Calais", "Channel", "Latham", "Sangatte", "London",
             "Wright", "Dover", "Farman", "Voisin", "Reims"]

    def _source(self):
        return {str(i + 1): f"The story of {n} continues in this part."
                for i, n in enumerate(self.NAMES)}

    def _shifted_blocks(self):
        return [
            (str(i + 1), "00:00:0%d,000 --> 00:00:0%d,000" % (i % 8, i % 8 + 1),
             f"{self.NAMES[i - 1]} hikâyesi burada sürüyor." if i
             else "Blériot hikâyesi burada başlıyor.")
            for i in range(len(self.NAMES))
        ]

    def test_shifted_region_is_reported_with_offset(self):
        regions = gui._content_offset_regions(self._shifted_blocks(), self._source())
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["offset"], -1)
        self.assertGreaterEqual(len(regions[0]["ids"]), 3)

    def test_aligned_file_reports_nothing(self):
        blocks = [(str(i + 1), "00:00:01,000 --> 00:00:02,000",
                   f"{n} hikâyesi burada sürüyor.")
                  for i, n in enumerate(self.NAMES)]
        self.assertEqual(gui._content_offset_regions(blocks, self._source()), [])

    def test_detector_is_wired_into_alignment_scan(self):
        types = {
            finding["type"]
            for finding in gui.detect_alignment_issues(
                self._shifted_blocks(), self._source())
        }
        self.assertIn("content_offset", types)


class PartialPromotionTest(unittest.TestCase):
    """P0-3: %100 tam .partial.srt dosyaları aylarca terfi ettirilmiyordu."""

    def _make(self, root, partial_text):
        source = Path(root, "bolum.srt")
        source.write_text(
            "1\n00:00:01,000 --> 00:00:03,000\nFirst line.\n\n"
            "2\n00:00:03,500 --> 00:00:05,000\nSecond line.\n",
            encoding="utf-8")
        out = Path(root, "bolum.tr.srt")
        partial = gui._partial_output_path(out)
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.write_text(partial_text, encoding="utf-8")
        return source, out

    def test_complete_partial_is_promoted_and_signed(self):
        with tempfile.TemporaryDirectory() as root:
            source, out = self._make(
                root,
                "1\n00:00:01,000 --> 00:00:03,000\nBirinci satır.\n\n"
                "2\n00:00:03,500 --> 00:00:05,000\nİkinci satır.\n")
            promoted = gui.promote_complete_partial_outputs(
                [str(source)], [out], "Turkish",
                source_languages={str(source): "English"})
            self.assertEqual(len(promoted), 1)
            self.assertTrue(out.exists())
            written = [text for _i, _ts, text in gui.parse_srt(str(out))]
            self.assertIn("Birinci satır.", written)
            self.assertIn(gui._DELIVERY_SIGNATURE, written)

    def test_incomplete_partial_is_left_alone(self):
        with tempfile.TemporaryDirectory() as root:
            source, out = self._make(
                root,
                "1\n00:00:01,000 --> 00:00:03,000\nBirinci satır.\n\n"
                "2\n00:00:03,500 --> 00:00:05,000\n[ÇEVİRİ EKSİK]\n")
            promoted = gui.promote_complete_partial_outputs(
                [str(source)], [out], "Turkish",
                source_languages={str(source): "English"})
            self.assertEqual(promoted, [])
            self.assertFalse(out.exists())


class ZeroStartSignatureTest(unittest.TestCase):
    """P0-4 kapandı: imza artık YALNIZ SONDA, baş imza hiç yazılmıyor.

    Sıfır-başlangıç bir istisna olmaktan çıktı; ilk cue 00:00:00,000'da
    başlasa da imzaya yer aramak gerekmiyor. Denetimin geçmesi hâlâ şart.
    """

    def test_only_tail_signature_written_and_audit_passes(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "src.srt")
            out = Path(root, "out.srt")
            source.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\nFirst real line here.\n\n"
                "2\n00:00:02,500 --> 00:00:04,000\nSecond line follows.\n",
                encoding="utf-8")
            cues = list(gui.parse_srt(str(source)))
            blocks = [
                ("1", "00:00:00,000 --> 00:00:02,000", "İlk replik burada."),
                ("2", "00:00:02,500 --> 00:00:04,000", "İkinci replik geliyor."),
            ]
            delivery = gui._prepare_upload_ready_blocks(
                blocks, "Turkish", None, source_cues=cues)
            gui.write_srt(str(out), delivery, "Turkish")
            signatures = [b for b in delivery if b[2] == gui._DELIVERY_SIGNATURE]
            self.assertEqual(len(signatures), 1)
            self.assertEqual(delivery[-1][2], gui._DELIVERY_SIGNATURE)
            # İlk diyalog 00:00:00,000'da ve hiç kıpırdamamış olmalı
            self.assertEqual(delivery[0][1], "00:00:00,000 --> 00:00:02,000")
            audit = gui._subtitle_delivery_audit(
                str(source), str(out), "Turkish", "English")
            self.assertFalse(audit.get("signature_mismatch"))
            self.assertFalse(gui._delivery_audit_has_hard_error(audit))


class CyrillicCreditTest(unittest.TestCase):
    """P0-5: Kiril hazırlayan imzası + e-posta cue'su teslim ediliyordu."""

    def test_cyrillic_and_contact_cues_are_credits(self):
        for value in ("Субтитры подготовлены Red Bee Media Ltd",
                      "Эл. почта: subtitling@bbc.co.uk",
                      "E-posta: subtitling@bbc.co.uk",
                      "www.opensubtitles.org"):
            with self.subTest(value=value):
                self.assertTrue(gui._looks_like_positional_credit(value))

    def test_real_dialogue_is_not_a_credit(self):
        for value in ("Bana e-posta at dedi ama adresi vermedi.",
                      "Altyazıyı okuyabiliyor musun?",
                      "Bu çeviri işini çok seviyorum."):
            with self.subTest(value=value):
                self.assertFalse(gui._looks_like_positional_credit(value))

    def test_contact_cue_is_removed_from_middle_of_file(self):
        rows = [(str(i), f"Обычная реплика номер {i} здесь.")
                for i in range(1, 12)]
        rows.insert(5, ("99", "Эл. почта: subtitling@bbc.co.uk"))
        ids = gui._delivery_removable_source_ids(
            [(i, "00:00:01,000 --> 00:00:02,000", t) for i, t in rows])
        self.assertIn("99", ids)


class WorkAttributionTest(unittest.TestCase):
    """P0-6: SDH temizleyici ekran üstü kitap künyelerini siliyordu."""

    def test_book_credits_are_content(self):
        for value in ('"Frankenstein"\nBayan Shelley',
                      '"Dracula"\nby Bram Stoker',
                      '"(دراكولا)\nتأليف (برام ستوكر)"'):
            with self.subTest(value=value):
                self.assertFalse(gui._source_cue_is_delivery_removable(value))

    def test_expert_name_card_is_still_removed(self):
        self.assertTrue(gui._source_cue_is_delivery_removable(
            '"د. ليز غلوين"\nجامعة "لندن"'))

    def test_plain_sdh_is_still_removed(self):
        self.assertTrue(
            gui._source_cue_is_delivery_removable("(Shrill flute playing)"))


class TypographyAndInvisibleTest(unittest.TestCase):
    """P1-7/P1-8: tipografik tırnak ve görünmez karakterler."""

    def test_typographic_quotes_are_flattened(self):
        result = gui._prepare_upload_ready_blocks(
            [("1", "00:00:01,000 --> 00:00:03,000",
              "Camelot’taki «şato» ve “kule”.")], "Turkish")
        texts = [t for _i, _ts, t in result if t != gui._DELIVERY_SIGNATURE]
        self.assertEqual(texts, ['Camelot\'taki "şato" ve "kule".'])

    def test_soft_hyphen_is_removed(self):
        self.assertEqual(
            sf.normalize_subtitle_control_artifacts("ay­nı selen­yum"),
            "aynı selenyum")


class CueIdLeakAndMidwordTest(unittest.TestCase):
    """P1-9/P1-14: cue numarası sızması ve kelime ortası boşluk."""

    def test_neighbor_cue_number_in_text_is_flagged(self):
        blocks = [
            ("107", "ts", "Sadakati bu kadar yücelten sen,\n108"),
            ("81", "ts", "Yazışmaları sırasında\nLeibniz ve Papin, 84"),
            ("42", "ts", "1969 yılında oldu."),
        ]
        self.assertEqual(sorted(gui._cue_id_leak_ids(blocks)), ["107", "81"])

    def test_midword_space_needs_source_evidence(self):
        self.assertEqual(
            gui._midword_space_ids(
                [("154", "ts", "Piram itler Çağı başladı.")],
                {"154": "The Age of Piramitler began."}),
            ["154"])
        self.assertEqual(
            gui._midword_space_ids(
                [("1", "ts", "Her şey değişti burada.")],
                {"1": "Everything changed here."}),
            [])


class LineBreakPlacementTest(unittest.TestCase):
    """P1-12: 1.046 satır bölme ihlali — sarkan edat/bağlaç."""

    def test_dangling_words_are_moved(self):
        cases = {
            "…tiyatroları\ngibi yerlerde": "…tiyatroları gibi\nyerlerde",
            "gözünüzün görebildiği yere\nkadar uzanıyordu":
                "gözünüzün görebildiği yere kadar\nuzanıyordu",
            "10. yüzyılın kaos ve\nkarmaşasından":
                "10. yüzyılın kaos\nve karmaşasından",
            "yolcu uçakları\nmı yapmalıyız?": "yolcu uçakları mı\nyapmalıyız?",
        }
        for before, after in cases.items():
            with self.subTest(before=before):
                self.assertEqual(gui._rebalance_line_break(before), after)

    def test_natural_sentence_boundary_and_dialogue_are_untouched(self):
        for value in ("Bu bitti.\nYeni cümle başlıyor.", "- Evet.\n- Hayır."):
            with self.subTest(value=value):
                self.assertEqual(gui._rebalance_line_break(value), value)


class AllCapsPunctuationPromptTest(unittest.TestCase):
    """P1-13: ALL-CAPS kaynakta nokta/virgül ayrımı."""

    def test_rule_present_in_both_prompts(self):
        sync = gui._build_sync_system_prompt("English", "Turkish", None, "Orta")
        hybrid = Path("hybrid_translate.py").read_text(encoding="utf-8")
        self.assertIn("ALL-CAPS SOURCE PUNCTUATION", sync)
        self.assertIn("ALL-CAPS SOURCE PUNCTUATION", hybrid)


class DeliveryScanCountsTest(unittest.TestCase):
    """Teslim taraması: etiketler genişliğe sayılmamalı, yeni sinyaller görünmeli."""

    def test_format_tags_do_not_count_towards_width(self):
        blocks = [("1", "00:00:01,000 --> 00:00:09,000", "<i>" + "A" * 40 + "</i>")]
        self.assertEqual(gui._scan_delivery_blocks(blocks, None)["over_width"], 0)

    def test_scan_reports_cue_id_leak(self):
        blocks = [("107", "00:00:10,000 --> 00:00:12,000", "Yücelten sen,\n108")]
        self.assertEqual(
            gui._scan_delivery_blocks(blocks, None)["cue_id_leak"], 1)


class QuotedWorkTitleGlossaryTest(unittest.TestCase):
    """P1-11: sözlük konuşmacının KİTAP adını çeviriyordu."""

    def test_quoted_title_is_dropped_from_glossary(self):
        import hybrid_translate as ht
        source = ('His book "Egyptian Sonics" explains the resonance. '
                  'Egyptian Sonics costs twenty pounds.')
        cleaned = ht.drop_quoted_work_title_terms(
            {"Egyptian Sonics": "Mısır Sonikleri", "resonance": "rezonans"},
            source)
        self.assertNotIn("Egyptian Sonics", cleaned)
        self.assertEqual(cleaned.get("resonance"), "rezonans")

    def test_unquoted_terms_are_kept(self):
        import hybrid_translate as ht
        cleaned = ht.drop_quoted_work_title_terms(
            {"resonance": "rezonans"}, "The resonance was measured here.")
        self.assertEqual(cleaned, {"resonance": "rezonans"})


if __name__ == "__main__":
    unittest.main()
