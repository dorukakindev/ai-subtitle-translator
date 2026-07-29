"""
İçerik türü şemaları ve otomatik tespit eşleştirme testleri.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import subtitle_translator_gui as gui


class ContentSchemaIntegrityTest(unittest.TestCase):
    def test_all_schemas_have_name_and_rules(self):
        for key, schema in gui.CONTENT_SCHEMAS.items():
            self.assertIn("name", schema, f"{key}: name yok")
            self.assertIn("rules", schema, f"{key}: rules yok")
            self.assertIsInstance(schema["rules"], list)

    def test_schema_names_are_unique(self):
        names = [v["name"] for v in gui.CONTENT_SCHEMAS.values()]
        self.assertEqual(len(names), len(set(names)), "şema adları tekrarlı")

    def test_new_schemas_exist(self):
        names = {v["name"] for v in gui.CONTENT_SCHEMAS.values()}
        for expected in ["Bilim Kurgu / Fantastik", "Tıbbi Dram / Hastane",
                         "Savaş / Askeri", "Spor / Maç Yayını", "Yemek / Seyahat",
                         "Reality / Sokak Argosu", "Siyaset / Toplum Belgeseli",
                         "Arkeoloji / Antik Tarih Belgeseli",
                         "Komedyen Biyografisi / Stand-up Belgeseli",
                         "Mitoloji / Antik Dünya"]:
            self.assertIn(expected, names)

    def test_2026_07_schemas_exist(self):
        # 2026-07-08'de eklenen türler (Oddities gibi koleksiyoncu-reality içerik dahil)
        names = {v["name"] for v in gui.CONTENT_SCHEMAS.values()}
        for expected in ["Koleksiyoncu / Meraklı Eşya Reality",
                         "Talk Show / Gece Programı", "Yarışma / Bilgi Yarışması",
                         "Doğa / Yaban Hayatı Belgeseli", "Dini İçerik / Vaaz"]:
            self.assertIn(expected, names)

    def test_new_schemas_resolve_via_detection_and_match(self):
        # Yeni türler otomatik tespit listesine girmeli ve _match_category ile çözülmeli
        cats = gui._detect_categories()
        for name in ["Koleksiyoncu / Meraklı Eşya Reality",
                     "Talk Show / Gece Programı", "Yarışma / Bilgi Yarışması",
                     "Doğa / Yaban Hayatı Belgeseli", "Dini İçerik / Vaaz"]:
            self.assertIn(name, cats)
            self.assertEqual(gui._match_category(name, cats), name)

    def test_bare_reality_still_resolves_to_shortest(self):
        # Yeni 'Koleksiyoncu ... Reality' adı, salt 'Reality' cevabının eski
        # davranışını (en kısa = 'Reality Show') BOZMAMALI.
        cats = gui._detect_categories()
        self.assertEqual(gui._match_category("Reality", cats), "Reality Show")

    def test_detect_categories_match_schemas(self):
        # Tespit listesi şemalardan türemeli — her kategori bir şemaya çözülmeli
        names = {v["name"] for v in gui.CONTENT_SCHEMAS.values()}
        for cat in gui._detect_categories():
            self.assertIn(cat, names)
        self.assertNotIn("Otomatik", gui._detect_categories())

    def test_every_nonauto_schema_has_substantial_rules(self):
        for key, schema in gui.CONTENT_SCHEMAS.items():
            if schema["name"] == "Otomatik":
                continue
            self.assertGreaterEqual(len(schema["rules"]), 7,
                                    f"{key}: {len(schema['rules'])} kural — çok zayıf")


    def test_art_cinema_schemas_exist_and_are_detectable(self):
        names = {
            "Deneysel / Deneme Sineması",
            "Politik / Toplumsal Sanat Sineması",
            "Felsefi / Teolojik Diyalog Sineması",
            "Sanatçı Biyografisi / Dönem",
            "Psikolojik / Kurumsal Dram",
        }
        schema_names = {v["name"] for v in gui.CONTENT_SCHEMAS.values()}
        self.assertTrue(names.issubset(schema_names))
        self.assertTrue(names.issubset(set(gui._detect_categories())))
        for name in names:
            self.assertEqual(gui._match_category(name, gui._detect_categories()), name)

    def test_detection_lines_include_disambiguating_descriptions(self):
        lines = "\n".join(gui._detect_category_lines())
        self.assertIn("Sinema / Film Belgeseli:", lines)
        self.assertIn("never scripted fiction", lines)
        self.assertIn("Tıbbi Dram / Hastane:", lines)
        self.assertIn("not merely a film set in a psychiatric institution", lines)
        self.assertIn("Deneysel / Deneme Sineması:", lines)


class MatchCategoryTest(unittest.TestCase):
    CATS = ["Komedi (Sitcom)", "Sketch Komedi / Absürt", "Stand-up Komedi",
            "Bilim Kurgu / Fantastik", "Film", "Dizi"]

    def test_exact_match(self):
        self.assertEqual(gui._match_category("Film", self.CATS), "Film")
        self.assertEqual(gui._match_category("bilim kurgu / fantastik", self.CATS),
                         "Bilim Kurgu / Fantastik")

    def test_category_inside_answer(self):
        # Model fazladan kelime eklemiş — en spesifik (uzun) kategori kazanır
        self.assertEqual(
            gui._match_category("Bu içerik Stand-up Komedi kategorisine girer", self.CATS),
            "Stand-up Komedi")

    def test_partial_answer_picks_shortest_category(self):
        # Model sadece 'Komedi' demiş — en kısa komedi kategorisi (genel sitcom) seçilir
        self.assertEqual(gui._match_category("Komedi", self.CATS), "Komedi (Sitcom)")

    def test_partial_answer_prefers_whole_word_over_prefix(self):
        cats = ["Tarihi / Dönem", "Tarih Belgeseli"]
        self.assertEqual(gui._match_category("Tarih", cats), "Tarih Belgeseli")

    def test_no_match_returns_none(self):
        self.assertIsNone(gui._match_category("Western", self.CATS))
        self.assertIsNone(gui._match_category("", self.CATS))
        self.assertIsNone(gui._match_category(None, self.CATS))

    def test_partial_word_is_not_a_category_match(self):
        self.assertIsNone(gui._match_category("Çocuklar", ["Çocuk"]))
        self.assertIsNone(gui._match_category("Çocuk", ["Çocuklar"]))

    def test_real_schema_list_resolves_old_detection_names(self):
        # Eski tespit listesindeki sorunlu adlar artık gerçek şemalara çözülmeli
        cats = gui._detect_categories()
        self.assertEqual(gui._match_category("Komedi", cats), "Komedi (Sitcom)")
        self.assertEqual(gui._match_category("Bilim Kurgu / Fantastik", cats),
                         "Bilim Kurgu / Fantastik")
        resolved = gui._match_category("Anime / Animasyon", cats)
        self.assertIsNotNone(resolved, "'Anime / Animasyon' hiçbir şemaya çözülemedi")
        # Çözülen ad gerçek bir şema olmalı
        self.assertIsNotNone(gui._match_category(resolved, cats))

    def test_turkish_dotted_i_category_matches_case_variants(self):
        cats = gui._detect_categories()
        expected = "Dini İçerik / Vaaz"
        for value in ("dini içerik / vaaz", "DİNİ İÇERİK / VAAZ"):
            self.assertEqual(gui._match_category(value, cats), expected)
            self.assertEqual(gui.normalize_schema_name(value), expected)

    def test_content_detection_prompt_does_not_name_categories_outside_schema_list(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"category": "Belgesel"}'))],
            usage=None,
        )
        with patch("hybrid_translate._safe_chat_create", return_value=response) as call:
            self.assertEqual(
                gui.detect_content_type_with_ai(None, [("1", "00:00:01,000", "A sample")], "test"),
                "Belgesel",
            )
        system_prompt = call.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("'Gaming'", system_prompt)
        self.assertNotIn("'Akademik Anlatım'", system_prompt)


    def test_content_detection_prompt_disambiguates_form_from_setting(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content='{"category": "Felsefi / Teolojik Diyalog Sineması"}'
                )
            )],
            usage=None,
        )
        with patch("hybrid_translate._safe_chat_create", return_value=response) as call:
            result = gui.detect_content_type_with_ai(
                None,
                [("1", "00:00:01,000", "What is evil, and may one resist it with force?")],
                "test",
                filename="Malmkrog.srt",
            )
        self.assertEqual(result, "Felsefi / Teolojik Diyalog Sineması")
        messages = call.call_args.kwargs["messages"]
        self.assertIn("hospital setting alone is not a medical procedural", messages[0]["content"])
        self.assertIn("Felsefi / Teolojik Diyalog Sineması:", messages[1]["content"])


class SchemaNameNormalizeTest(unittest.TestCase):
    def test_normalizes_legacy_auto_value(self):
        self.assertEqual(gui.normalize_schema_name("auto"), "Otomatik")
        self.assertEqual(gui.normalize_schema_name("automatic"), "Otomatik")
        self.assertEqual(gui.normalize_schema_name("otomatik"), "Otomatik")

    def test_normalizes_case_insensitive_real_schema(self):
        self.assertEqual(gui.normalize_schema_name("film"), "Film")
        self.assertEqual(
            gui.normalize_schema_name("bilim kurgu / fantastik"),
            "Bilim Kurgu / Fantastik",
        )


if __name__ == "__main__":
    unittest.main()
