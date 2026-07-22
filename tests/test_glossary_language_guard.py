"""
Sözlük hedef-dil guard'ı: denylist → sözlük-seviyesi reddi.

Bkz. plans/sozluk-hedef-dil-guard-brief.md — The Blood of Hussain (2026-07-16)
olayı: analiz geçişinin ürettiği 13 terimlik sözlük Somalice çıktı, ana model
sözlüğe sadık kalarak hatayı tüm dosyaya yaydı. Mevcut guard (non_turkish_leak_token)
bir DENYLIST'ti — yalnızca bilinen yabancı script/Turkic-drift-kelime-listesi/
Latin-extended-diakritik arıyordu; saf-Latin, kelime-listesi-dışı, diakritiksiz
Somalice'yi ("madaxweynaha", "Bangiga Adduunka") yapısal olarak göremiyordu.

Bu testler:
  - yeni R_wqx sinyalini (Türkçe'de q/w/x yok) kilitler,
  - sözlük-seviyesi reddi kilitler (bir terim açıkça yabancıysa TÜM sözlük atılır —
    "Bangiga Adduunka" ve "mu'addinka" gibi tekil kuralları tetiklemeyen terimler
    de bu sayede gider — asıl kazanç budur),
  - precontext yolunun (Yardımcı Analiz KAPALIYKEN) artık sanitize edildiğini
    kilitler (KRİTİK BOŞLUK — eskiden hiç sanitize edilmiyordu),
  - target_language="tr" DIŞINDA guard'ın devre dışı kaldığını kilitler.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import hybrid_translate as ht


class RomanNumeralGlossaryGuardTest(unittest.TestCase):
    def test_wrong_roman_numeral_conversion_is_corrected(self):
        logs = []
        cleaned = ht.sanitize_glossary_for_turkish(
            {"MCMLXXVII": "1877", "Fritz": "Fritz"},
            log_fn=lambda msg, level="": logs.append((level, msg)),
        )
        self.assertEqual(cleaned["MCMLXXVII"], "1977")
        self.assertEqual(cleaned["Fritz"], "Fritz")
        self.assertTrue(any("Roma rakami" in msg for _, msg in logs))

    def test_correct_roman_numeral_conversion_is_kept(self):
        self.assertEqual(
            ht.sanitize_glossary_for_turkish({"MCMLXXVII": "1977"}),
            {"MCMLXXVII": "1977"},
        )


class WqxTargetGuardTest(unittest.TestCase):
    def test_wqx_target_rejected(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
        })
        self.assertEqual(cleaned, {})

    def test_lowercase_wqx_rejected(self):
        cleaned = ht.sanitize_glossary_for_turkish({"President": "madaxweynaha"})
        self.assertEqual(cleaned, {})

    def test_single_word_proper_noun_kept(self):
        cleaned = ht.sanitize_glossary_for_turkish({"Washington": "Washington"})
        self.assertEqual(cleaned, {"Washington": "Washington"})

    def test_title_case_show_name_does_not_drop_glossary(self):
        glossary = {
            "the Cosby's": "The Cosby Show",
            "Greek mythology": "Yunan mitolojisi",
        }
        self.assertEqual(ht.sanitize_glossary_for_turkish(glossary), glossary)

    def test_whole_glossary_dropped_on_one_leak(self):
        # Gerçek olay: The Blood of Hussain analiz sözlüğü (bkz. brief).
        dirty = {
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
            "President": "madaxweynaha",
            "World Bank": "Bangiga Adduunka",      # hiçbir tekil kural tetiklenmiyor
            "Muezzin": "mu'addinka",                # hiçbir tekil kural tetiklenmiyor
            "Karbala": "Kerbela",                   # tertemiz bir terim
        }
        cleaned = ht.sanitize_glossary_for_turkish(dirty)
        self.assertEqual(cleaned, {})
        # Asıl kazanç: bireysel olarak "temiz görünen" terimler de gider.
        self.assertNotIn("World Bank", cleaned)
        self.assertNotIn("Muezzin", cleaned)
        self.assertNotIn("Karbala", cleaned)

    def test_clean_turkish_glossary_untouched(self):
        clean = {"Armed Forces": "Silahlı Kuvvetler"}
        self.assertEqual(ht.sanitize_glossary_for_turkish(clean), clean)

    def test_multiword_proper_noun_kept_asis_does_not_drop_whole_glossary(self):
        """Gerçek olay (4 Louis Theroux belgeseli art arda, 2026-07-20): dil-kodu
        bug'ı düzeltilip R_wqx canlanınca, çok kelimeli özel isimlerin (kişi/
        kurum/yer adı) hiç çevrilmeden aynen bırakılması ("Joe Exotic"->"Joe
        Exotic", "Wynnewood, Oklahoma"->"Oklahoma, Wynnewood", "Daniella Weiss"->
        "Daniella Weiss") tek-kelimelik-özel-isim istisnasını (Washington gibi)
        tetiklemediği için TÜM sözlüğü (42-77 terim) götürüyordu. Hedef, kaynağın
        kendi kelimelerinin AYNISIYSA (sırası değişmiş olsa da) bu yabancı-dile-
        sürüklenme değildir -- çeviri hiç yapılmamış, bilinçli bırakılmış demektir."""
        real_settlers_glossary = {
            "Daniella Weiss": "Daniella Weiss",
            "settler violence": "yerleşimci şiddeti",
            "Palestinians": "Filistinliler",
            "the settler dream": "yerleşimci rüyası",
        }
        cleaned = ht.sanitize_glossary_for_turkish(real_settlers_glossary)
        self.assertEqual(cleaned, real_settlers_glossary)

    def test_multiword_proper_noun_reordered_still_kept(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Wynnewood, Oklahoma": "Oklahoma, Wynnewood",
        })
        self.assertEqual(cleaned, {"Wynnewood, Oklahoma": "Oklahoma, Wynnewood"})

    def test_multiword_proper_noun_kept_asis_does_not_itself_leak(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "GW Exotic Animal Park": "GW Exotic Animal Park",
            "West Block": "West Block",
        })
        self.assertEqual(cleaned, {
            "GW Exotic Animal Park": "GW Exotic Animal Park",
            "West Block": "West Block",
        })

    def test_translated_phrase_with_preserved_proper_noun_not_dropped(self):
        """Gerçek olay (2 Louis Theroux belgeseli art arda, 2026-07-20): DÜZGÜN
        çevrilmiş çok kelimeli hedefler ("Milwaukee'nin Kuzey Yakası", "Milwaukee
        Polis Teşkilatı", "SWAT ekibi") içlerinde kaynaktan aynen korunmuş bir
        özel isim (Milwaukee, SWAT) taşıdıkları için R_wqx'i tetikleyip 30-32
        terimlik sözlükleri komple götürüyordu — tek-kelime istisnası apostrof
        yüzünden ("Milwaukee'nin" iki token'a bölünüyor) devreye girmiyordu."""
        real_milwaukee_glossary = {
            "North Side of Milwaukee": "Milwaukee'nin Kuzey Yakası",
            "Milwaukee PD": "Milwaukee Polis Teşkilatı",
            "SWAT team": "SWAT ekibi",
            "gun crime": "silahlı suç",
        }
        cleaned = ht.sanitize_glossary_for_turkish(real_milwaukee_glossary)
        self.assertEqual(cleaned, real_milwaukee_glossary)

    def test_preserved_proper_noun_must_still_be_capitalized(self):
        # Kaynakta geçen kelime hedefte KÜÇÜK harfle çıkarsa istisna uygulanmaz
        # (gerçek özel-isim koruması değil, tesadüfi kelime çakışması olabilir).
        cleaned = ht.sanitize_glossary_for_turkish({
            "Milwaukee thing": "milwaukee gibi bir şey",
        })
        self.assertEqual(cleaned, {})

    def test_plural_source_key_exempts_turkish_suffixed_singular_stem(self):
        """Gerçek olay (rough.treatment.1978, 2026-07-20): "Newsweeks"->
        "Newsweek'ler" -- İngilizce çoğul anahtar ("Newsweeks"), Türkçe ekli tekil
        gövdeye ("Newsweek'ler", apostrof yüzünden "Newsweek"+"ler" iki token'a
        bölünüyor) eşleşmediği için exact-match istisnası tutmuyor ve 50 terimlik
        sözlük komple gidiyordu."""
        real_glossary = {
            "Newsweeks": "Newsweek'ler",
            "trial": "dava/mahkeme süreci",
        }
        cleaned = ht.sanitize_glossary_for_turkish(real_glossary)
        self.assertEqual(cleaned, real_glossary)

    def test_actual_foreign_drift_still_caught_even_if_key_shares_a_word(self):
        # Kaynakla hedef kelime kümesi FARKLIYSA (gerçek çeviri denenmiş ama
        # yabancı dile kaymışsa) istisna devreye girmemeli.
        cleaned = ht.sanitize_glossary_for_turkish({
            "West Bank settler": "Qawweyaha xoogga",
        })
        self.assertEqual(cleaned, {})

    def test_ascii_turkish_target_kept(self):
        clean = {"church": "kilise"}
        self.assertEqual(ht.sanitize_glossary_for_turkish(clean), clean)

    def test_non_turkish_target_language_skips_guard(self):
        dirty = {"Armed Forces": "Qawweyaha Xoogga Dalka"}
        cleaned = ht.sanitize_glossary_for_turkish(dirty, target_language="de")
        self.assertEqual(cleaned, dirty)

    def test_single_bad_term_does_not_drop_whole_glossary_via_older_rules(self):
        """Regresyon koruması: whole-glossary-drop SADECE R_wqx'e bağlı olmalı.
        Turkic-drift-listesi gibi eski 3 kural hâlâ SADECE o terimi düşürür —
        tests/test_source_language_leftover.py:155 ile aynı sözleşme."""
        cleaned = ht.sanitize_glossary_for_turkish({
            "holiday party": "bäýram/holidaý oturylyşyğı",  # Turkic-drift ile düşer
            "taxidermy": "taksidermi",                        # temiz, kalmalı
        })
        self.assertEqual(cleaned, {"taxidermy": "taksidermi"})


class GlossaryGlossOrInstructionGuardTest(unittest.TestCase):
    """bkz. plans/sozluk-gloss-ve-half-sayi-brief.md — Ishanou/Salome/Blood of
    Hussain'de üst üste görülen ayrı sınıf: analiz geçişi hedefe ÇEVİRİ değil
    META-YORUM yazıyor ('Caesar (Sezar)', 'Bembem (özel ad, aynen korunacak)',
    'görümce / yenge bağlama göre'). Bugün eklenen q/w/x guard'ı bunu görmüyordu
    çünkü hiçbirinde q/w/x yok.

    POLİTİKA AYRIMI (en kritik nokta, KARIŞTIRILMASIN):
      - R_wqx (mevcut): TÜM sözlüğü atar -- toplu dil çökmesi sinyali.
      - Bu guard (yeni): YALNIZCA o terimi atar -- model Türkçe üretmiş, sadece
        karar verememiş; diğer terimler sağlam kalabilir.
    """

    def test_paren_gloss_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({"Caesar": "Caesar (Sezar)"})
        self.assertEqual(cleaned, {})

    def test_instruction_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "Bembem": "Bembem (özel ad, aynen korunacak)",
        })
        self.assertEqual(cleaned, {})

    def test_slash_options_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "sister-in-law": "görümce / yenge bağlama göre",
        })
        self.assertEqual(cleaned, {})

    def test_bracket_target_dropped(self):
        cleaned = ht.sanitize_glossary_for_turkish({"X": "Y [açıklama]"})
        self.assertEqual(cleaned, {})

    def test_clean_terms_survive_alongside(self):
        # POLİTİKA TESTİ: bir terim gloss nedeniyle atılırken TÜM sözlük atılmamalı.
        cleaned = ht.sanitize_glossary_for_turkish({
            "Caesar": "Caesar (Sezar)",
            "Armed Forces": "Silahlı Kuvvetler",
        })
        self.assertEqual(cleaned, {"Armed Forces": "Silahlı Kuvvetler"})

    def test_tight_slash_not_dropped(self):
        # Boşluksuz eğik çizgi (gerçek terim) elenmemeli.
        cleaned = ht.sanitize_glossary_for_turkish({"band": "AC/DC"})
        self.assertEqual(cleaned, {"band": "AC/DC"})

    def test_wqx_still_drops_whole_glossary(self):
        # Eski politika (R_wqx) bozulmamalı: Somalice + eğik-çizgi aynı terimde
        # birlikte olsa bile TÜM sözlük atılmalı (whole-glossary-drop kazanır).
        dirty = {
            "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
            "President": "madaxweynaha",
            "Karbala": "Kerbela",
        }
        self.assertEqual(ht.sanitize_glossary_for_turkish(dirty), {})


class GlossaryVerboseMetaCommentaryGuardTest(unittest.TestCase):
    """bkz. hybrid_translate.py'deki '_glossary_verbose_meta_commentary_marker'
    blok yorumu — The Shivering Truth S01E02 (2026-07-19) olayı: 'maggot' için
    analiz geçişi ÇEVİRİ değil paragraf uzunluğunda bir NASIL-ÇEVRİLMELİ notu
    yazdı; notun içindeki kazara "qurt" (kurt yazım kayması) R_wqx'i tetikledi
    ve TÜM sözlük atıldı -- 'sir'->'komutanım', 'Private'->'er', 'Sergeant'->
    'çavuş', 'church'->'kilise' gibi dört tertemiz terim de beraberinde gitti.
    'church' çıktıda 3 kez hiç çevrilmeden kaldı.

    Çözüm: uzunluk kontrolü wqx taramasından ÖNCE çalışır ve tetiklenirse
    `continue` eder -- notun içeriği asla wqx_hits'e ulaşmaz."""

    MAGGOT_NOTE = (
        "qurt/qurtçuk değil; askerî hakaret olarak mecazi 'pislik'/'larva' "
        "yerine doğrudan 'çürük kurt' anlamı vermeden, komik ve aşağılayıcı "
        "askerî hakaret olarak çevrilmeli: \"çürük\" ya da bağlama göre "
        "\"maggot\"un yerleşik karşılığı yoksa açıklamasız bırakılabilir."
    )

    def test_verbose_note_dropped_alone(self):
        cleaned = ht.sanitize_glossary_for_turkish({"maggot": self.MAGGOT_NOTE})
        self.assertEqual(cleaned, {})

    def test_verbose_note_does_not_poison_whole_glossary(self):
        # ASIL REGRESYON TESTİ — gerçek S01E02 sözlüğü, birebir.
        cleaned = ht.sanitize_glossary_for_turkish({
            "maggot": self.MAGGOT_NOTE,
            "sir": "komutanım",
            "Private": "er",
            "Sergeant": "çavuş",
            "church": "kilise",
        })
        self.assertEqual(cleaned, {
            "sir": "komutanım",
            "Private": "er",
            "Sergeant": "çavuş",
            "church": "kilise",
        })

    def test_short_multiword_idiom_not_dropped_by_verbosity(self):
        # Eşiğin altındaki gerçek çok-kelimeli bir deyim çevirisi (7 kelime)
        # yanlışlıkla "uzun not" sayılıp atılmamalı.
        cleaned = ht.sanitize_glossary_for_turkish({
            "ogling": "sarkıntılık etmek / bakışlarıyla dik dik süzmek bağlamına göre",
        })
        # Bu değer zaten eğik-çizgi kuralına takılıp tek-terim atılır (7 kelime,
        # verbosity eşiğinin altında) -- burada asıl kontrol edilen, verbosity
        # kontrolünün kısa/orta uzunluktaki değerlere DOKUNMADIĞI, iki kuralın
        # bağımsız çalıştığıdır.
        self.assertEqual(cleaned, {})

    def test_genuinely_short_idiom_survives(self):
        cleaned = ht.sanitize_glossary_for_turkish({
            "ear-piercing ceremony": "kulak delme töreni",
        })
        self.assertEqual(cleaned, {"ear-piercing ceremony": "kulak delme töreni"})

    def test_wqx_whole_drop_still_works_alongside_verbose_sibling(self):
        # Bir sözlükte HEM uzun-not (tek-terim atılan) HEM gerçek kısa Somalice
        # (whole-glossary-drop tetikleyen) varsa, kısa Somalice yine de TÜM
        # sözlüğü düşürmeli -- uzun not bu sinyali gizlemiyor.
        cleaned = ht.sanitize_glossary_for_turkish({
            "maggot": self.MAGGOT_NOTE,
            "Armed Forces": "Qawweyaha Xoogga Dalka",
            "church": "kilise",
        })
        self.assertEqual(cleaned, {})


class PrecontextGlossaryGuardTest(unittest.TestCase):
    """KRİTİK BOŞLUK (Adım 3): precontext yolu (Yardımcı Analiz KAPALIYKEN) eskiden
    hiç sanitize edilmiyordu."""

    def test_precontext_terms_sanitized(self):
        import subtitle_translator_gui as gui
        data = {
            "summary": "x",
            "terms": {
                "Armed Forces": "Qawweyaha Xoogga Dalka / ciidamada qalabka sida",
                "Karbala": "Kerbela",
            },
        }
        hint = gui.build_precontext_hint(data)
        self.assertNotIn("Qawweyaha", hint)
        self.assertNotIn("Kerbela", hint)  # whole-glossary-drop: temiz terim de gider

    def test_precontext_terms_untouched_when_clean(self):
        import subtitle_translator_gui as gui
        data = {"terms": {"the Precinct": "Karakol"}}
        hint = gui.build_precontext_hint(data)
        self.assertIn("'the Precinct' → 'Karakol'", hint)

    def test_sanitize_precontext_data_does_not_mutate_caller_dict(self):
        import subtitle_translator_gui as gui
        data = {"terms": {"President": "madaxweynaha"}}
        gui.build_precontext_hint(data)
        # build_precontext_hint kendi kopyası üzerinde çalışmalı — orijinal `data`
        # (örn. data_by_fp / series_memory tarafından ayrıca kullanılan) bozulmamalı.
        self.assertEqual(data["terms"], {"President": "madaxweynaha"})


class SeriesMemoryGlossaryGuardTest(unittest.TestCase):
    """Adım 3.3 — en tehlikeli boşluk: precontext'ten series_memory'ye sanitize
    edilmeden kalıcılaştırılıyordu (zehir diziler arası taşınır)."""

    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec("customtkinter") is None:
            raise unittest.SkipTest("customtkinter yüklü değil; GUI testi atlandı")
        import subtitle_translator_gui as gui
        from tests._gui_app import make_app
        cls.app = make_app(gui)  # açılıştaki yarım-batch penceresi kapalı (bkz. _gui_app)
        cls.app.update_idletasks()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def test_series_memory_not_poisoned(self):
        with tempfile.TemporaryDirectory() as td:
            fp = str(Path(td) / "Show.S01E01.srt")
            Path(fp).write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")
            self.app.series_memory_var.set(True)
            self.app.input_var.set(td)
            data = {
                "terms": {
                    "Armed Forces": "Qawweyaha Xoogga Dalka",
                    "Karbala": "Kerbela",
                },
            }
            self.app._update_series_memory_from_precontext(fp, data, target_language="tr")
            sm_obj, _season, _ep = self.app._series_mem_for(fp)
            self.assertIsNotNone(sm_obj)
            self.assertNotIn("Armed Forces", sm_obj._data["terms"])
            self.assertNotIn("Karbala", sm_obj._data["terms"])  # whole-glossary-drop


if __name__ == "__main__":
    unittest.main()
